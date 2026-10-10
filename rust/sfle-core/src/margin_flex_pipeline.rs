//! Integrated Flex lines, resolved sizing and signed/auto logical main margins.
//! Outputs border/padding/content boxes (not an invalid signed-margin Rect).
//! Cross margins now use established flex-line cross sizes; alignment deferred.

use crate::edge_pipeline::{BoxEdges, Edges};
use crate::cross_margins::position_cross_margins;
use crate::cross_alignment::{CrossAlign, resolve_cross_alignment};
use crate::align_content::{AlignContent, distribute_cross_lines};
use crate::line_layout::{
    Direction, Rect, Wrap, WritingDirection,
};
use crate::main_margins::{position_main_margins_justified, MarginItem};
use crate::main_alignment::JustifyContent;
use crate::{resolve_flexible_lengths, FlexBasis, FlexMathError};
use std::collections::HashSet;

#[derive(Clone, Debug, PartialEq)]
pub struct MarginFlexItem {
    pub id: String,
    pub flex: FlexBasis,
    pub cross_content_size: f64,
    pub edges: BoxEdges,
    pub main_start: Option<f64>,
    pub main_end: Option<f64>,
    pub order: i32,
    pub cross_start: Option<f64>,
    pub cross_end: Option<f64>,
    pub align_self: CrossAlign,
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
    pub used_cross_start_margin: f64,
    pub used_cross_end_margin: f64,
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
            || self.cross_start.is_some_and(|v| !v.is_finite())
            || self.cross_end.is_some_and(|v| !v.is_finite())
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
    compute_margin_flex_layout_content(
        items, width, height, direction, writing, wrap, main_gap,
        cross_gap, justify, align_items, AlignContent::FlexStart,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compute_margin_flex_layout_content(
    items: &[MarginFlexItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
    justify: JustifyContent,
    align_items: CrossAlign,
    align_content: AlignContent,
) -> Result<MarginFlexLayout, FlexMathError> {
    compute_margin_flex_layout_justified(
        items, width, height, direction, writing, wrap, main_gap, cross_gap,
        JustifyContent::FlexStart,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compute_margin_flex_layout_justified(
    items: &[MarginFlexItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
    justify: JustifyContent,
) -> Result<MarginFlexLayout, FlexMathError> {
    compute_margin_flex_layout_aligned(
        items, width, height, direction, writing, wrap, main_gap,
        cross_gap, justify, CrossAlign::FlexStart,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn compute_margin_flex_layout_aligned(
    items: &[MarginFlexItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
    justify: JustifyContent,
    align_items: CrossAlign,
) -> Result<MarginFlexLayout, FlexMathError> {
    if align_items == CrossAlign::Auto {
        return Err(FlexMathError::InvalidInput("align-items cannot be auto"));
    }
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

    let cross_extent = if horizontal { height } else { width };
    let line_cross_sizes: Vec<f64> = lines.iter().map(|line| {
        if wrap == Wrap::NoWrap { return cross_extent; }
        line.iter().map(|i| {
            let item = &items[*i];
            item.cross_border(horizontal) + item.cross_start.unwrap_or(0.0)
                + item.cross_end.unwrap_or(0.0)
        }).fold(0.0, f64::max)
    }).collect();
    let mut cross_forward = if horizontal { true } else { writing == WritingDirection::Ltr };
    if wrap == Wrap::WrapReverse { cross_forward = !cross_forward; }
    let distributed = distribute_cross_lines(
        align_content, cross_extent, &line_cross_sizes,
        cross_gap, cross_forward, wrap == Wrap::NoWrap,
    )?;
    let line_cross_sizes = distributed.sizes;
    let line_starts = distributed.starts;
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
        let positions = position_main_margins_justified(
            &border_items, main_extent, main_gap, direction, writing, justify,
        )?;
        for (i, position) in line.iter().zip(positions.iter()) {
            let item = &items[*i];
            let cross_size = item.cross_border(horizontal);
            let cross_margin = position_cross_margins(
                cross_size, line_cross_sizes[line_index],
                item.cross_start, item.cross_end, cross_forward,
            )?;
            let cross_origin = line_starts[line_index];
            let cross_offset = if item.cross_start.is_none() || item.cross_end.is_none() {
                cross_margin.border_start
            } else {
                resolve_cross_alignment(
                    align_items, item.align_self, cross_size,
                    line_cross_sizes[line_index],
                    item.cross_start.expect("checked fixed margin"),
                    item.cross_end.expect("checked fixed margin"), cross_forward,
                )?
            };
            let cross_start = cross_origin + cross_offset;
            let border = if horizontal {
                Rect {
                    x: position.border_start, y: cross_start,
                    width: position.border_main_size, height: cross_size,
                }
            } else {
                Rect {
                    x: cross_start, y: position.border_start,
                    width: cross_size, height: position.border_main_size,
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
                used_cross_start_margin: cross_margin.used_start_margin,
                used_cross_end_margin: cross_margin.used_end_margin,
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
            cross_start: Some(0.0), cross_end: Some(0.0),
            align_self: CrossAlign::Auto,
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
    #[test]
    fn cross_auto_margins_center_in_nowrap_line() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.cross_start = None;
        a.cross_end = None;
        let out = compute_margin_flex_layout(
            &[a], 100.0, 100.0, Direction::Row,
            WritingDirection::Ltr, Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 45.0);
        assert_eq!(out.boxes[0].used_cross_start_margin, 45.0);
        assert_eq!(out.boxes[0].used_cross_end_margin, 45.0);
    }

    #[test]
    fn cross_auto_overflow_preserves_negative_end_margin() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.cross_content_size = 80.0;
        a.cross_start = None;
        a.cross_end = None;
        let out = compute_margin_flex_layout(
            &[a], 100.0, 50.0, Direction::Row,
            WritingDirection::Ltr, Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 0.0);
        assert_eq!(out.boxes[0].used_cross_end_margin, -30.0);
    }

    #[test]
    fn signed_cross_margins_affect_wrapped_line_cross_extent() {
        let mut a = item("a", 60.0, Some(0.0), Some(0.0));
        a.cross_start = Some(5.0);
        a.cross_end = Some(10.0);
        let mut b = item("b", 60.0, Some(0.0), Some(0.0));
        b.cross_start = Some(-3.0);
        let out = compute_margin_flex_layout(
            &[a, b], 90.0, 100.0, Direction::Row,
            WritingDirection::Ltr, Wrap::Wrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 5.0);
        assert_eq!(out.boxes[1].border.y, 22.0);
    }

    #[test]
    fn wrap_reverse_uses_cross_end_side() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.cross_start = Some(3.0);
        let out = compute_margin_flex_layout(
            &[a], 100.0, 100.0, Direction::Row,
            WritingDirection::Ltr, Wrap::WrapReverse, 0.0, 0.0,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 87.0);
    }

    #[test]
    fn justify_space_between_changes_real_border_positions() {
        let out = compute_margin_flex_layout_justified(
            &[item("a", 20.0, Some(0.0), Some(0.0)),
              item("b", 20.0, Some(0.0), Some(0.0))],
            100.0, 40.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 10.0, 0.0, JustifyContent::SpaceBetween,
        ).unwrap();
        assert_eq!(out.boxes[0].border.x, 0.0);
        assert_eq!(out.boxes[1].border.x, 80.0);
    }

    #[test]
    fn rtl_and_reverse_justify_preserve_logical_start() {
        for (direction, writing) in [
            (Direction::Row, WritingDirection::Rtl),
            (Direction::RowReverse, WritingDirection::Ltr),
        ] {
            let out = compute_margin_flex_layout_justified(
                &[item("a", 20.0, Some(0.0), Some(0.0)),
                  item("b", 20.0, Some(0.0), Some(0.0))],
                100.0, 40.0, direction, writing, Wrap::NoWrap,
                10.0, 0.0, JustifyContent::SpaceBetween,
            ).unwrap();
            assert_eq!(out.boxes[0].border.x, 80.0);
            assert_eq!(out.boxes[1].border.x, 0.0);
        }
    }

    #[test]
    fn positive_auto_margin_precedes_justify_end() {
        let out = compute_margin_flex_layout_justified(
            &[item("a", 20.0, Some(0.0), None),
              item("b", 20.0, Some(0.0), Some(0.0))],
            100.0, 40.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0, JustifyContent::FlexEnd,
        ).unwrap();
        assert_eq!(out.boxes[0].used_main_end_margin, 60.0);
        assert_eq!(out.boxes[0].border.x, 0.0);
        assert_eq!(out.boxes[1].border.x, 80.0);
    }

    #[test]
    fn column_main_axis_justify_centers_y() {
        let out = compute_margin_flex_layout_justified(
            &[item("a", 20.0, Some(0.0), Some(0.0))],
            40.0, 100.0, Direction::Column, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0, JustifyContent::Center,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 40.0);
    }

    #[test]
    fn align_items_center_positions_cross_border() {
        let out = compute_margin_flex_layout_aligned(
            &[item("a", 20.0, Some(0.0), Some(0.0))],
            100.0, 100.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0,
            JustifyContent::FlexStart, CrossAlign::Center,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 45.0);
    }

    #[test]
    fn align_self_end_overrides_container_start() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.align_self = CrossAlign::FlexEnd;
        let out = compute_margin_flex_layout_aligned(
            &[a], 100.0, 100.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0,
            JustifyContent::FlexStart, CrossAlign::FlexStart,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 90.0);
    }

    #[test]
    fn auto_cross_margins_override_align_self_end() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.cross_start = None;
        a.cross_end = None;
        a.align_self = CrossAlign::FlexEnd;
        let out = compute_margin_flex_layout_aligned(
            &[a], 100.0, 100.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0,
            JustifyContent::FlexStart, CrossAlign::FlexStart,
        ).unwrap();
        assert_eq!(out.boxes[0].border.y, 45.0);
    }

    #[test]
    fn column_rtl_align_end_maps_to_physical_right() {
        let mut a = item("a", 20.0, Some(0.0), Some(0.0));
        a.align_self = CrossAlign::FlexEnd;
        let out = compute_margin_flex_layout_aligned(
            &[a], 100.0, 40.0, Direction::Column, WritingDirection::Rtl,
            Wrap::NoWrap, 0.0, 0.0,
            JustifyContent::FlexStart, CrossAlign::FlexStart,
        ).unwrap();
        assert_eq!(out.boxes[0].border.x, 0.0);
    }

    #[test]
    fn stretch_is_not_silently_treated_as_start() {
        assert!(compute_margin_flex_layout_aligned(
            &[item("a", 20.0, Some(0.0), Some(0.0))],
            100.0, 100.0, Direction::Row, WritingDirection::Ltr,
            Wrap::NoWrap, 0.0, 0.0,
            JustifyContent::FlexStart, CrossAlign::Stretch,
        ).is_err());
    }

}
