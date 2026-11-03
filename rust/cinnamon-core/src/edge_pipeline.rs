//! Restricted used-edge CSS Flexbox pipeline, counterpart to Python edge_pipeline.
//!
//! Fixed physical margin/border/padding consume outer main space. Negative and
//! automatic margins, intrinsic measurements, CSS percentages and automatic
//! minimum sizes are not accepted by this pure resolved-input slice.

use crate::line_layout::{
    form_flex_lines, place_resolved_lines, Direction, ResolvedItem, Wrap, WritingDirection,
};
use crate::{resolve_flexible_lengths, FlexBasis, FlexMathError};
use std::collections::HashMap;
use crate::layout_unit::LayoutUnit;

fn unit(value:f64)->LayoutUnit{
    LayoutUnit::from_nearest(value).expect("validated finite resolved edge geometry")
}
fn sum_units(values:impl IntoIterator<Item=f64>)->f64{
    values.into_iter().fold(LayoutUnit::from_raw(0),|total,v|total+unit(v)).to_px()
}
fn subtract_units(value:f64,deductions:impl IntoIterator<Item=f64>)->f64{
    deductions.into_iter().fold(unit(value),|total,v|total-unit(v)).to_px()
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Edges { pub top: f64, pub right: f64, pub bottom: f64, pub left: f64 }

impl Edges {
    fn horizontal(self) -> f64 { sum_units([self.left, self.right]) }
    fn vertical(self) -> f64 { sum_units([self.top, self.bottom]) }
    fn finite(self) -> bool {
        [self.top, self.right, self.bottom, self.left].iter().all(|v| v.is_finite())
    }
    fn nonnegative(self) -> bool {
        [self.top, self.right, self.bottom, self.left].iter().all(|v| *v >= 0.0)
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct BoxEdges { pub margin: Edges, pub border: Edges, pub padding: Edges }

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BoxRect {
    pub content: crate::line_layout::Rect,
    pub padding: crate::line_layout::Rect,
    pub border: crate::line_layout::Rect,
    pub margin: crate::line_layout::Rect,
}

#[derive(Clone, Debug, PartialEq)]
pub struct EdgeItem {
    pub id: String,
    pub flex: FlexBasis,
    pub cross_content_size: f64,
    pub edges: BoxEdges,
    pub order: i32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct EdgeLayout {
    pub lines: Vec<Vec<String>>,
    pub boxes: Vec<(String, BoxRect)>,
}

fn inset(
    rect: crate::line_layout::Rect,
    edges: Edges,
) -> Result<crate::line_layout::Rect, FlexMathError> {
    let width = subtract_units(rect.width,[edges.horizontal()]);
    let height = subtract_units(rect.height,[edges.vertical()]);
    if width < 0.0 || height < 0.0 {
        return Err(FlexMathError::InvalidInput("edges exceed box dimensions"));
    }
    Ok(crate::line_layout::Rect {
        x: sum_units([rect.x,edges.left]), y: sum_units([rect.y,edges.top]),
        width, height,
    })
}

impl EdgeItem {
    fn validate(&self) -> Result<(), FlexMathError> {
        if self.id.is_empty()
            || !self.cross_content_size.is_finite() || self.cross_content_size < 0.0
            || !self.edges.margin.finite() || !self.edges.margin.nonnegative()
            || !self.edges.border.finite() || !self.edges.border.nonnegative()
            || !self.edges.padding.finite() || !self.edges.padding.nonnegative()
        {
            return Err(FlexMathError::InvalidInput("invalid item edges or sizes"));
        }
        self.flex.validate()
    }

    fn main_edges(&self, horizontal: bool) -> f64 {
        let e = self.edges;
        if horizontal {
            sum_units([e.margin.horizontal(),e.padding.horizontal(),e.border.horizontal()])
        } else {
            sum_units([e.margin.vertical(),e.padding.vertical(),e.border.vertical()])
        }
    }

    fn cross_edges(&self, horizontal: bool) -> f64 {
        let e = self.edges;
        if horizontal {
            sum_units([e.margin.vertical(),e.padding.vertical(),e.border.vertical()])
        } else {
            sum_units([e.margin.horizontal(),e.padding.horizontal(),e.border.horizontal()])
        }
    }
}

pub fn compute_edge_layout(
    items: &[EdgeItem],
    width: f64,
    height: f64,
    direction: Direction,
    writing: WritingDirection,
    wrap: Wrap,
    main_gap: f64,
    cross_gap: f64,
) -> Result<EdgeLayout, FlexMathError> {
    if ![width, height, main_gap, cross_gap].iter().all(|v| v.is_finite() && *v >= 0.0) {
        return Err(FlexMathError::InvalidInput("invalid container extents or gaps"));
    }
    let mut lookup = HashMap::new();
    let horizontal = matches!(direction, Direction::Row | Direction::RowReverse);
    let main_extent = if horizontal { width } else { height };
    let mut hypothetical = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        item.validate()?;
        if lookup.insert(item.id.as_str(), index).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate item ID"));
        }
        hypothetical.push(ResolvedItem {
            id: item.id.clone(), main_size: sum_units([item.flex.hypothetical,item.main_edges(horizontal)]),
            cross_size: sum_units([item.cross_content_size,item.cross_edges(horizontal)]), order: item.order,
        });
    }
    let lines = form_flex_lines(&hypothetical, main_extent, main_gap, wrap)?;
    let mut sized_lines = Vec::with_capacity(lines.len());

    for line in lines {
        let fixed=sum_units(line.iter().map(|i|items[*lookup.get(i.id.as_str()).unwrap()]
            .main_edges(horizontal)));
        let available_content=subtract_units(main_extent,[fixed]).max(0.0);
        let bases: Vec<FlexBasis> = line.iter().map(|i| {
            items[*lookup.get(i.id.as_str()).unwrap()].flex
        }).collect();
        let target = resolve_flexible_lengths(&bases, available_content, main_gap)?;
        let sized: Vec<ResolvedItem> = line.into_iter().zip(target.into_iter())
            .map(|(mut item, content)| {
                let edges = items[*lookup.get(item.id.as_str()).unwrap()].main_edges(horizontal);
                item.main_size = sum_units([content,edges]);
                item
            }).collect();
        sized_lines.push(sized);
    }
    let positioned = place_resolved_lines(
        &sized_lines, width, height, direction, writing, wrap, main_gap, cross_gap,
    )?;
    let mut boxes = Vec::with_capacity(positioned.items.len());
    for placed in positioned.items {
        let item = &items[*lookup.get(placed.id.as_str()).unwrap()];
        let margin = placed.rect;
        let border = inset(margin, item.edges.margin)?;
        let padding = inset(border, item.edges.border)?;
        let content = inset(padding, item.edges.padding)?;
        boxes.push((placed.id, BoxRect { content, padding, border, margin }));
    }
    Ok(EdgeLayout { lines: positioned.lines, boxes })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extreme_inset_geometry_saturates_signed_layout_coordinates() {
        let max=crate::layout_unit::LayoutUnit::from_raw(i32::MAX).to_px();
        let min=crate::layout_unit::LayoutUnit::from_raw(i32::MIN).to_px();
        let rect=crate::line_layout::Rect {
            x:max,y:min,width:max,height:max,
        };
        let edges=Edges{left:32.0,top:16.0,..Edges::default()};
        let inner=inset(rect,edges).unwrap();
        assert_eq!(inner.x,max);
        assert_eq!(inner.y,min+16.0);
        assert_eq!(inner.width,max-32.0);
        assert_eq!(inner.height,max-16.0);
        for coordinate in [inner.x,inner.y,inner.width,inner.height] {
            assert_eq!(coordinate*64.0,(coordinate*64.0).trunc());
            assert!((min..=max).contains(&coordinate));
        }
    }

    #[test]
    fn edges_reduce_available_flex_content_and_preserve_geometry() {
        let e = BoxEdges {
            margin: Edges { left: 5.0, right: 5.0, ..Edges::default() },
            border: Edges { left: 1.0, right: 1.0, ..Edges::default() },
            padding: Edges { left: 5.0, right: 5.0, ..Edges::default() },
        };
        let make = |id: &str| EdgeItem {
            id: id.to_owned(),
            flex: FlexBasis { basis: 20.0, hypothetical: 20.0, grow: 1.0,
                              shrink: 1.0, min_size: 0.0, max_size: None },
            cross_content_size: 10.0, edges: e, order: 0,
        };
        let result = compute_edge_layout(
            &[make("a"), make("b")], 100.0, 30.0,
            Direction::Row, WritingDirection::Ltr, Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(result.lines, vec![vec!["a", "b"]]);
        assert_eq!(result.boxes[0].1.margin.width, 50.0);
        assert_eq!(result.boxes[0].1.content.width, 28.0);
        assert_eq!(result.boxes[1].1.content.x, 61.0);
    }

    #[test]
    fn right_to_left_positions_keep_edge_offsets() {
        let item = EdgeItem {
            id: "a".into(),
            flex: FlexBasis { basis: 20.0, hypothetical: 20.0, grow: 0.0,
                              shrink: 1.0, min_size: 0.0, max_size: None },
            cross_content_size: 10.0,
            edges: BoxEdges {
                margin: Edges { left: 2.0, right: 3.0, ..Edges::default() },
                padding: Edges { left: 5.0, right: 1.0, ..Edges::default() },
                border: Edges::default(),
            }, order: 0,
        };
        let result = compute_edge_layout(
            &[item], 100.0, 30.0, Direction::Row, WritingDirection::Rtl,
            Wrap::NoWrap, 0.0, 0.0,
        ).unwrap();
        assert_eq!(result.boxes[0].1.margin.x, 69.0);
        assert_eq!(result.boxes[0].1.content.x, 76.0);
    }
}
