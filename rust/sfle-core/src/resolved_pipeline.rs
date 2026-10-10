//! A restricted end-to-end resolved flex geometry slice.
//!
//! Runs line formation against hypothetical sizes, flexes each line with
//! CSS §9.7, then maps resulting sizes to physical coordinates. Input
//! items are pre-normalized, content-box = border-box = margin-box, and
//! intrinsic/percentage/auto sizing is explicitly out of scope.

use crate::line_layout::{
    form_flex_lines, place_resolved_lines, Direction, LinePlacement, ResolvedItem,
    Wrap, WritingDirection,
};
use crate::{resolve_flexible_lengths, FlexBasis, FlexMathError};
use std::collections::HashMap;

#[derive(Clone, Debug, PartialEq)]
pub struct ResolvedFlexItem {
    pub id: String,
    pub flex: FlexBasis,
    pub cross_size: f64,
    pub order: i32,
}

impl ResolvedFlexItem {
    fn validate(&self) -> Result<(), FlexMathError> {
        if self.id.is_empty() || !self.cross_size.is_finite() || self.cross_size < 0.0 {
            return Err(FlexMathError::InvalidInput("invalid item id or cross size"));
        }
        self.flex.validate()
    }
}

/// Compute an integrated line/size/position result for already resolved boxes.
pub fn compute_resolved_flex(
    items: &[ResolvedFlexItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
) -> Result<LinePlacement, FlexMathError> {
    if ![width, height, main_gap, cross_gap]
        .iter().all(|n| n.is_finite() && *n >= 0.0)
    {
        return Err(FlexMathError::InvalidInput("invalid container extent or gap"));
    }

    let mut lookup: HashMap<&str, usize> = HashMap::new();
    let mut hypothetical = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        item.validate()?;
        if lookup.insert(item.id.as_str(), index).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate resolved item id"));
        }
        hypothetical.push(ResolvedItem {
            id: item.id.clone(),
            main_size: item.flex.hypothetical,
            cross_size: item.cross_size,
            order: item.order,
        });
    }

    let horizontal = matches!(direction, Direction::Row | Direction::RowReverse);
    let main_extent = if horizontal { width } else { height };
    let lines = form_flex_lines(&hypothetical, main_extent, main_gap, wrap)?;
    let mut sized_lines = Vec::with_capacity(lines.len());

    for line in lines {
        let bases: Vec<FlexBasis> = line.iter().map(|item| {
            items[*lookup.get(item.id.as_str()).expect("validated lookup")].flex
        }).collect();
        let targets = resolve_flexible_lengths(&bases, main_extent, main_gap)?;
        let resolved = line.into_iter().zip(targets.into_iter()).map(|(mut item, target)| {
            item.main_size = target;
            item
        }).collect();
        sized_lines.push(resolved);
    }
    place_resolved_lines(
        &sized_lines, width, height, direction, writing, wrap, main_gap, cross_gap,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(name: &str, basis: f64, grow: f64) -> ResolvedFlexItem {
        ResolvedFlexItem {
            id: name.to_owned(),
            flex: FlexBasis {
                basis,
                hypothetical: basis,
                grow,
                shrink: 1.0,
                min_size: 0.0,
                max_size: None,
            },
            cross_size: 10.0,
            order: 0,
        }
    }

    #[test]
    fn grow_changes_positions_before_geometry_output() {
        let items = [item("a", 20.0, 1.0), item("b", 20.0, 2.0)];
        let result = compute_resolved_flex(
            &items, 100.0, 30.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 10.0, 0.0,
        ).unwrap();
        assert_eq!(result.lines, vec![vec!["a", "b"]]);
        assert!((result.items[0].rect.width - 36.66666666666667).abs() < 1e-9);
        assert!((result.items[1].rect.x - 46.66666666666667).abs() < 1e-9);
    }

    #[test]
    fn wrapping_uses_hypothetical_sizes_before_flexing() {
        let items = [item("a", 60.0, 1.0), item("b", 60.0, 1.0)];
        let result = compute_resolved_flex(
            &items, 100.0, 70.0, Direction::Row, WritingDirection::Ltr,
            Wrap::Wrap, 0.0, 5.0,
        ).unwrap();
        assert_eq!(result.lines, vec![vec!["a"], vec!["b"]]);
        assert_eq!(result.items[0].rect.width, 100.0);
        assert_eq!(result.items[1].rect.width, 100.0);
        assert_eq!(result.items[1].rect.y, 15.0);
    }

    #[test]
    fn rtl_keeps_right_to_left_coordinates_after_sizing() {
        let items = [item("a", 20.0, 0.0), item("b", 20.0, 0.0)];
        let result = compute_resolved_flex(
            &items, 100.0, 30.0, Direction::Row, WritingDirection::Rtl,
            Wrap::NoWrap, 15.0, 0.0,
        ).unwrap();
        assert_eq!(result.items[0].rect.x, 80.0);
        assert_eq!(result.items[1].rect.x, 45.0);
    }
}
