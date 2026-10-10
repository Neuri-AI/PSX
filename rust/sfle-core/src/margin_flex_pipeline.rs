//! Integrated Flex lines, resolved sizing and signed/auto logical main margins.
//! Outputs border/padding/content boxes (not an invalid signed-margin Rect).
//! Cross-axis margins and alignment remain explicitly unsupported.

use crate::edge_pipeline::{BoxEdges, Edges};
use crate::line_layout::{
    place_resolved_lines, Direction, Rect, ResolvedItem, Wrap, WritingDirection,
};
use crate::main_margins::{position_main_margins, MarginItem};
use crate::{resolve_flexible_lengths, FlexBasis, FlexMathError};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct MarginFlexItem {
    pub id: String,
    pub flex: FlexBasis,
    pub cross_content_size: f64,
    pub edges: BoxEdges,
    pub main_start: Option<f64>,
    pub main_end: Option<f64>,
    pub order: i32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MarginFlexBox {
    pub id: String,
    pub content: Rect,
    pub padding: Rect,
    pub border: Rect,
    pub used_main_start_margin: f64,
    pub used_main_end_margin: f64,
    pub line_index: usize,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MarginFlexLayout {
    pub lines: Vec<Vec<String>>,
    pub boxes: Vec<MarginFlexBox>,
}

impl MarginFlexItem {
    fn validate(&self) -> Result<(), FlexMathError> {
        self.flex.validate()?;
        let edges = self.edges;
        let values = [
            edges.border.top, edges.border.right, edges.border.bottom, edges.border.left,
            edges.padding.top, edges.padding.right, edges.padding.bottom, edges.padding.left,
        ];
        if self.id.is_empty()
            || !self.cross_content_size.is_finite() || self.cross_content_size < 0.0
            || !values.iter().all(|v| v.is_finite() && *v >= 0.0)
            || edges.margin != Edges::default()
            || self.main_start.is_some_and(|v| !v.is_finite())
            || self.main_end.is_some_and(|v| !v.is_finite())
        {
            return Err(FlexMathError::InvalidInput("invalid margin flex item"));
        }
        Ok(())
    }

    fn main_pb(&self, horizontal: bool) -> f64 {
        let e = self.edges;
        if horizontal {
            e.border.left + e.border.right + e.padding.left + e.padding.right
        } else {
            e.border.top + e.border.bottom + e.padding.top + e.padding.bottom
        }
    }

    fn main_fixed(&self, horizontal: bool) -> f64 {
        self.main_pb(horizontal) + self.main_start.unwrap_or(0.0)
            + self.main_end.unwrap_or(0.0)
    }

    fn cross_border(&self, horizontal: bool) -> f64 {
        let e = self.edges;
        if horizontal {
            self.cross_content_size + e.border.top + e.border.bottom
                + e.padding.top + e.padding.bottom
        } else {
            self.cross_content_size + e.border.left + e.border.right
                + e.padding.left + e.padding.right
        }
    }
}

pub fn compute_margin_flex_layout(
    items: &[MarginFlexItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
) -> Result<MarginFlexLayout, FlexMathError> {
    if ![width, height, main_gap, cross_gap]
        .iter().all(|v| v.is_finite() && *v >= 0.0)
    {
        return Err(FlexMathError::InvalidInput("invalid layout dimensions"));
    }
    let mut ids = HashSet::new();
    for item in items {
        item.validate()?;
        if !ids.insert(item.id.as_str()) {
            return Err(FlexMathError::InvalidInput("duplicate node IDs"));
        }
    }
    let horizontal = matches!(direction, Direction::Row | Direction::RowReverse);
    let main_extent = if horizontal { width } else { height };
    let mut order: Vec<usize> = (0..items.len()).collect();
    order.sort_by_key(|&index| (items[index].order, index));

    let mut lines: Vec<Vec<usize>> = Vec::new();
    let mut current = Vec::new();
    let mut occupied = 0.0;
    for index in order {
        let item = &items[index];
        let outer = item.flex.hypothetical + item.main_fixed(horizontal);
        let candidate = occupied + if current.is_empty() { 0.0 } else { main_gap } + outer;
        if wrap != Wrap::NoWrap && !current.is_empty() && candidate > main_extent {
            lines.push(current);
            current = vec![index];
            occupied = outer;
        } else {
            current.push(index);
            occupied = candidate;
        }
    }
    if !current.is_empty() { lines.push(current); }

    let cross_lines: Vec<Vec<ResolvedItem>> = lines.iter().map(|line|
        line.iter().map(|index| {
            let item = &items[*index];
            ResolvedItem {
                id: item.id.clone(), main_size: 0.0,
                cross_size: item.cross_border(horizontal), order: item.order,
            }
        }).collect()
    ).collect();
    let cross_placement = place_resolved_lines(
        &cross_lines, width, height, direction, writing, wrap, 0.0, cross_gap,
    )?;
    let cross_by_id: HashMap<&str, Rect> = cross_placement.items.iter()
        .map(|item| (item.id.as_str(), item.rect)).collect();
    let mut boxes = Vec::new();

    for (line_index, line) in lines.iter().enumerate() {
        let fixed: f64 = line.iter().map(|i| items[*i].main_fixed(horizontal)).sum();
        let available = (main_extent - fixed).max(0.0);
        let bases: Vec<FlexBasis> = line.iter().map(|i| items[*i].flex).collect();
        let targets = resolve_flexible_lengths(&bases, available, main_gap)?;
        let border_items: Vec<MarginItem> = line.iter().zip(targets.iter()).map(|(i, target)| {
            let item = &items[*i];
            MarginItem {
                id: item.id.clone(), border_main_size: target + item.main_pb(horizontal),
                start: item.main_start, end: item.main_end,
            }
        }).collect();
        let positions = position_main_margins(
            &border_items, main_extent, main_gap, direction, writing,
        )?;
        for (i, position) in line.iter().zip(positions.iter()) {
            let item = &items[*i];
            let cross = cross_by_id[item.id.as_str()];
            let border = if horizontal {
                Rect {
                    x: position.border_start, y: cross.y,
                    width: position.border_main_size, height: cross.height,
                }
            } else {
                Rect {
                    x: cross.x, y: position.border_start,
                    width: cross.width, height: position.border_main_size,
                }
            };
            let e = item.edges;
            let padding = Rect {
                x: border.x + e.border.left, y: border.y + e.border.top,
                width: border.width - e.border.left - e.border.right,
                height: border.height - e.border.top - e.border.bottom,
            };
            let content = Rect {
                x: padding.x + e.padding.left, y: padding.y + e.padding.top,
                width: padding.width - e.padding.left - e.padding.right,
                height: padding.height - e.padding.top - e.padding.bottom,
            };
            boxes.push(MarginFlexBox {
                id: item.id.clone(), content, padding, border,
                used_main_start_margin: position.used_start_margin,
                used_main_end_margin: position.used_end_margin, line_index,
            });
        }
    }

    Ok(MarginFlexLayout {
        lines: lines.into_iter().map(|line|
            line.into_iter().map(|i| items[i].id.clone()).collect()
        ).collect(),
        boxes,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(id: &str, basis: f64, start: Option<f64>, end: Option<f64>) -> MarginFlexItem {
        MarginFlexItem {
            id: id.to_string(), flex: FlexBasis {
                basis, hypothetical: basis, grow: 0.0, shrink: 0.0,
                min_size: 0.0, max_size: None,
            },
            cross_content_size: 10.0, edges: BoxEdges::default(),
            main_start: start, main_end: end, order: 0,
        }
    }

    #[test]
    fn auto_margins_fill_remaining_space_after_size_resolution() {
        let out = compute_margin_flex_layout(
            &[item("a", 20.0, Some(0.0), None),
              item("b", 20.0, None, Some(0.0))],
            100.0, 40.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[1].border.x, 80.0);
        assert_eq!(out.boxes[0].used_main_end_margin, 30.0);
    }

    #[test]
    fn signed_margins_affect_line_breaks() {
        let out = compute_margin_flex_layout(
            &[item("a", 60.0, Some(-20.0), Some(0.0)),
              item("b", 60.0, Some(-20.0), Some(0.0))],
            90.0, 60.0, Direction::Row, WritingDirection::Ltr,
            Wrap::Wrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.lines, vec![vec!["a", "b"]]);
        assert_eq!(out.boxes[0].border.x, -20.0);
        assert_eq!(out.boxes[1].border.x, 20.0);
    }

    #[test]
    fn rtl_start_margin_maps_to_right_side() {
        let out = compute_margin_flex_layout(
            &[item("a", 20.0, Some(-10.0), Some(0.0))],
            100.0, 30.0, Direction::Row, WritingDirection::Rtl,
            Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[0].border.x, 90.0);
    }
}
