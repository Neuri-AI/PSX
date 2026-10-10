//! F2.2.2 already-resolved signed / auto Flexbox main-axis margins.
//! Border boxes are positioned directly; signed margin boxes need not have
//! representable nonnegative widths. Cross-axis margins remain unsupported.

use crate::line_layout::{Direction, WritingDirection};
use crate::main_alignment::{resolve_main_alignment, JustifyContent};
use crate::FlexMathError;
use std::collections::HashSet;

#[derive(Clone, Debug, PartialEq)]
pub struct MarginItem {
    pub id: String,
    pub border_main_size: f64,
    pub start: Option<f64>,
    pub end: Option<f64>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MarginPosition {
    pub id: String,
    pub border_start: f64,
    pub border_main_size: f64,
    pub used_start_margin: f64,
    pub used_end_margin: f64,
}

pub fn position_main_margins(
    items: &[MarginItem],
    container_main_size: f64,
    main_gap: f64,
    direction: Direction,
    writing: WritingDirection,
) -> Result<Vec<MarginPosition>, FlexMathError> {
    position_main_margins_justified(
        items, container_main_size, main_gap, direction, writing,
        JustifyContent::FlexStart,
    )
}

pub fn position_main_margins_justified(
    items: &[MarginItem],
    container_main_size: f64,
    main_gap: f64,
    direction: Direction,
    writing: WritingDirection,
    justify: JustifyContent,
) -> Result<Vec<MarginPosition>, FlexMathError> {
    if !container_main_size.is_finite() || container_main_size < 0.0
        || !main_gap.is_finite() || main_gap < 0.0
    {
        return Err(FlexMathError::InvalidInput("invalid extent or gap"));
    }
    let mut ids = HashSet::new();
    let mut fixed = main_gap * items.len().saturating_sub(1) as f64;
    let mut auto_count: usize = 0;
    for item in items {
        if item.id.is_empty() || !ids.insert(item.id.as_str())
            || !item.border_main_size.is_finite() || item.border_main_size < 0.0
            || item.start.is_some_and(|n| !n.is_finite())
            || item.end.is_some_and(|n| !n.is_finite())
        {
            return Err(FlexMathError::InvalidInput("invalid margin item"));
        }
        fixed += item.border_main_size + item.start.unwrap_or(0.0) + item.end.unwrap_or(0.0);
        auto_count += usize::from(item.start.is_none()) + usize::from(item.end.is_none());
    }
    let share = if auto_count == 0 { 0.0 } else {
        (container_main_size - fixed).max(0.0) / auto_count as f64
    };

    let used_outer: Vec<f64> = items.iter().map(|item| {
        item.border_main_size + item.start.unwrap_or(share)
            + item.end.unwrap_or(share)
    }).collect();
    let effective_justify = if auto_count > 0 && container_main_size > fixed {
        JustifyContent::FlexStart
    } else {
        justify
    };
    let alignment = resolve_main_alignment(
        effective_justify, container_main_size, &used_outer, main_gap,
    )?;
    let horizontal = matches!(direction, Direction::Row | Direction::RowReverse);
    let reversed = matches!(direction, Direction::RowReverse | Direction::ColumnReverse);
    let forward = if horizontal { (writing == WritingDirection::Ltr) != reversed }
                  else { !reversed };
    let mut cursor = if forward { alignment.leading_space }
        else { container_main_size - alignment.leading_space };
    let mut positions = Vec::with_capacity(items.len());
    for item in items {
        let start = item.start.unwrap_or(share);
        let end = item.end.unwrap_or(share);
        let border_start;
        if forward {
            border_start = cursor + start;
            cursor += start + item.border_main_size + end + alignment.between_space;
        } else {
            border_start = cursor - start - item.border_main_size;
            cursor -= start + item.border_main_size + end + main_gap;
        }
        positions.push(MarginPosition {
            id: item.id.clone(), border_start,
            border_main_size: item.border_main_size,
            used_start_margin: start, used_end_margin: end,
        });
    }
    Ok(positions)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(id: &str, start: Option<f64>, end: Option<f64>) -> MarginItem {
        MarginItem { id: id.into(), border_main_size: 20.0, start, end }
    }

    #[test]
    fn positive_space_distributes_equally_across_auto_edges() {
        let result = position_main_margins(
            &[item("a", Some(0.0), None), item("b", None, Some(0.0))],
            100.0, 0.0, Direction::Row, WritingDirection::Ltr,
        ).unwrap();
        assert_eq!(result[0].used_end_margin, 30.0);
        assert_eq!(result[1].used_start_margin, 30.0);
        assert_eq!(result[1].border_start, 80.0);
    }

    #[test]
    fn negative_remaining_space_makes_auto_zero() {
        let result = position_main_margins(
            &[item("a", None, None)], 10.0, 0.0, Direction::Row, WritingDirection::Ltr,
        ).unwrap();
        assert_eq!(result[0].used_start_margin, 0.0);
        assert_eq!(result[0].border_start, 0.0);
    }

    #[test]
    fn signed_margins_can_shift_border_box_outside_container() {
        let result = position_main_margins(
            &[item("a", Some(-15.0), Some(0.0))],
            100.0, 0.0, Direction::RowReverse, WritingDirection::Ltr,
        ).unwrap();
        assert_eq!(result[0].border_start, 95.0);
    }
}
