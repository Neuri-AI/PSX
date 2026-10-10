//! Pre-resolved CSS Flexbox line formation and physical placement.
//!
//! Mirrors the limited Python `psx.sfle.line_layout` contract. Items have
//! already-resolved outer main/cross sizes. This is NOT full CSS layout.

use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Direction { Row, RowReverse, Column, ColumnReverse }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WritingDirection { Ltr, Rtl }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Wrap { NoWrap, Wrap, WrapReverse }

#[derive(Clone, Debug, PartialEq)]
pub struct ResolvedItem {
    pub id: String,
    pub main_size: f64,
    pub cross_size: f64,
    pub order: i32,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect { pub x: f64, pub y: f64, pub width: f64, pub height: f64 }

#[derive(Clone, Debug, PartialEq)]
pub struct PositionedItem {
    pub id: String,
    pub rect: Rect,
    pub line_index: usize,
}

#[derive(Clone, Debug, PartialEq)]
pub struct LinePlacement {
    pub lines: Vec<Vec<String>>,
    pub items: Vec<PositionedItem>,
}

fn finite_nonnegative(value: f64) -> bool { value.is_finite() && value >= 0.0 }

fn validate_items(items: &[ResolvedItem]) -> Result<(), FlexMathError> {
    let mut ids = std::collections::HashSet::new();
    for item in items {
        if item.id.is_empty() || !ids.insert(item.id.as_str())
            || !finite_nonnegative(item.main_size)
            || !finite_nonnegative(item.cross_size)
        {
            return Err(FlexMathError::InvalidInput("invalid or duplicate resolved item"));
        }
    }
    Ok(())
}

/// Determine order-modified flex lines before any flex grow/shrink distribution.
pub fn form_flex_lines(
    items: &[ResolvedItem],
    available_main: f64,
    gap: f64,
    wrap: Wrap,
) -> Result<Vec<Vec<ResolvedItem>>, FlexMathError> {
    if !finite_nonnegative(available_main) || !finite_nonnegative(gap) {
        return Err(FlexMathError::InvalidInput("invalid main size or gap"));
    }
    validate_items(items)?;
    if items.is_empty() { return Ok(vec![]); }
    let mut order: Vec<usize> = (0..items.len()).collect();
    order.sort_by_key(|&idx| (items[idx].order, idx));
    if wrap == Wrap::NoWrap {
        return Ok(vec![order.into_iter().map(|idx| items[idx].clone()).collect()]);
    }
    let mut lines: Vec<Vec<ResolvedItem>> = Vec::new();
    let mut current: Vec<ResolvedItem> = Vec::new();
    let mut used = 0.0;
    for idx in order {
        let item = &items[idx];
        let candidate = used + if current.is_empty() { 0.0 } else { gap } + item.main_size;
        if !current.is_empty() && candidate > available_main {
            lines.push(current);
            current = vec![item.clone()];
            used = item.main_size;
        } else {
            current.push(item.clone());
            used = candidate;
        }
    }
    if !current.is_empty() { lines.push(current); }
    Ok(lines)
}

/// Position previously flex-sized item *outer boxes*, without CSS alignment.
pub fn place_resolved_lines(
    lines: &[Vec<ResolvedItem>],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
) -> Result<LinePlacement, FlexMathError> {
    if ![width, height, main_gap, cross_gap].iter().all(|&n| finite_nonnegative(n)) {
        return Err(FlexMathError::InvalidInput("invalid extent or gap"));
    }
    if wrap == Wrap::NoWrap && lines.len() > 1 {
        return Err(FlexMathError::InvalidInput("nowrap cannot have multiple lines"));
    }
    let all: Vec<ResolvedItem> = lines.iter().flat_map(|line| line.iter().cloned()).collect();
    validate_items(&all)?;
    let horizontal = matches!(direction, Direction::Row | Direction::RowReverse);
    let reversed = matches!(direction, Direction::RowReverse | Direction::ColumnReverse);
    let main_forward = if horizontal { (writing == WritingDirection::Ltr) != reversed }
                       else { !reversed };
    let mut cross_forward = if horizontal { true } else { writing == WritingDirection::Ltr };
    if wrap == Wrap::WrapReverse { cross_forward = !cross_forward; }
    let main_extent = if horizontal { width } else { height };
    let cross_extent = if horizontal { height } else { width };
    let mut cross_cursor = if cross_forward { 0.0 } else { cross_extent };
    let mut output = Vec::new();
    let mut memberships = Vec::new();

    for (index, line) in lines.iter().enumerate() {
        let line_cross = line.iter().map(|item| item.cross_size).fold(0.0, f64::max);
        if !cross_forward { cross_cursor -= line_cross; }
        let mut main_cursor = if main_forward { 0.0 } else { main_extent };
        let mut members = Vec::new();
        for item in line {
            if !main_forward { main_cursor -= item.main_size; }
            let rect = if horizontal {
                Rect { x: main_cursor, y: cross_cursor,
                       width: item.main_size, height: item.cross_size }
            } else {
                Rect { x: cross_cursor, y: main_cursor,
                       width: item.cross_size, height: item.main_size }
            };
            output.push(PositionedItem {
                id: item.id.clone(), rect, line_index: index,
            });
            members.push(item.id.clone());
            if main_forward { main_cursor += item.main_size; }
            main_cursor += if main_forward { main_gap } else { -main_gap };
        }
        memberships.push(members);
        if cross_forward {
            cross_cursor += line_cross;
            if index + 1 < lines.len() { cross_cursor += cross_gap; }
        } else if index + 1 < lines.len() {
            cross_cursor -= cross_gap;
        }
    }
    Ok(LinePlacement { lines: memberships, items: output })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(id: &str, main: f64, cross: f64) -> ResolvedItem {
        ResolvedItem { id: id.to_owned(), main_size: main, cross_size: cross, order: 0 }
    }

    #[test]
    fn ltr_rtl_and_reverse_main_axes() {
        let inputs = vec![item("a", 20.0, 10.0), item("b", 20.0, 10.0)];
        let lines = form_flex_lines(&inputs, 100.0, 15.0, Wrap::NoWrap).unwrap();
        let cases = [
            (Direction::Row, WritingDirection::Ltr, 0.0, 35.0),
            (Direction::Row, WritingDirection::Rtl, 80.0, 45.0),
            (Direction::RowReverse, WritingDirection::Ltr, 80.0, 45.0),
            (Direction::RowReverse, WritingDirection::Rtl, 0.0, 35.0),
        ];
        for (direction, writing, first, second) in cases {
            let out = place_resolved_lines(
                &lines, 100.0, 100.0, direction, writing, Wrap::NoWrap, 15.0, 0.0
            ).unwrap();
            assert_eq!(out.items[0].rect.x, first);
            assert_eq!(out.items[1].rect.x, second);
        }
    }

    #[test]
    fn wrap_reverse_and_oversized_item() {
        let inputs = vec![item("a", 60.0, 20.0), item("b", 120.0, 30.0)];
        let lines = form_flex_lines(&inputs, 100.0, 10.0, Wrap::WrapReverse).unwrap();
        assert_eq!(lines.len(), 2);
        let out = place_resolved_lines(
            &lines, 100.0, 100.0, Direction::Row, WritingDirection::Ltr,
            Wrap::WrapReverse, 10.0, 10.0
        ).unwrap();
        assert_eq!(out.items[0].rect.y, 80.0);
        assert_eq!(out.items[1].rect.y, 40.0);
        assert_eq!(out.items[1].rect.width, 120.0);
    }
}
