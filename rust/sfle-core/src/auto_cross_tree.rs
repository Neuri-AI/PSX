//! Bottom-up wrapped auto cross sizing for recursive Flex containers.
use crate::margin_tree::{compute_margin_tree, MarginTreeLayout, MarginTreeNode};
use crate::line_layout::{Direction, Wrap, WritingDirection};
use crate::FlexMathError;
use crate::layout_unit::LayoutUnit;
use std::collections::{HashMap, HashSet};

fn horizontal(direction: Direction) -> bool {
    matches!(direction, Direction::Row | Direction::RowReverse)
}
fn lu(value:f64)->LayoutUnit { LayoutUnit::from_nearest(value).expect("validated finite length") }

pub fn compute_auto_cross_tree(
    nodes: &[MarginTreeNode],
    auto_cross: &[String],
    writing: WritingDirection,
) -> Result<MarginTreeLayout, FlexMathError> {
    let mut indices: HashMap<&str, usize> = HashMap::new();
    let mut children: HashMap<&str, Vec<usize>> = HashMap::new();
    for (index, node) in nodes.iter().enumerate() {
        if node.id.is_empty() || indices.insert(&node.id, index).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate or empty auto tree node"));
        }
        children.insert(&node.id, Vec::new());
        if let Some(parent) = node.parent.as_deref() {
            let siblings = children.get_mut(parent).ok_or(
                FlexMathError::InvalidInput("auto sizing requires preorder ancestry"),
            )?;
            siblings.push(index);
        }
    }
    let mut selected = HashSet::new();
    for id in auto_cross {
        if !indices.contains_key(id.as_str()) || !selected.insert(id.as_str()) {
            return Err(FlexMathError::InvalidInput("invalid auto cross declaration"));
        }
    }
    let mut adapted = nodes.to_vec();
    for index in (0..nodes.len()).rev() {
        let node = &adapted[index];
        if !selected.contains(node.id.as_str()) { continue; }
        if children[node.id.as_str()].is_empty() {
            return Err(FlexMathError::InvalidInput("auto cross requires nonempty container"));
        }
        let is_horizontal = horizontal(node.direction);
        // A column's auto main height can be the cross contribution of
        // its row parent (A01). Select the axis required by that parent,
        // not unconditionally this container's own flex cross axis.
        let auto_width=if let Some(parent)=node.parent.as_deref(){
            let pidx=*indices.get(parent).ok_or(
                FlexMathError::InvalidInput("missing auto cross parent"),
            )?;
            !horizontal(adapted[pidx].direction)
        }else{!is_horizontal};
        let resolves_own_cross=auto_width!=is_horizontal;
        let main_limit=lu(if is_horizontal {node.width}else{node.height});
        let mut lines:Vec<(LayoutUnit,LayoutUnit)>=Vec::new();
        let mut line_main=LayoutUnit::from_raw(0);
        let mut line_cross=LayoutUnit::from_raw(0);
        for &child_index in &children[node.id.as_str()] {
            let item = adapted[child_index].item.as_ref().ok_or(
                FlexMathError::InvalidInput("auto cross child requires Flex item"),
            )?;
            if item.cross_size_auto || item.cross_start.is_none() || item.cross_end.is_none()
                || item.main_start.is_none() || item.main_end.is_none() {
                return Err(FlexMathError::InvalidInput("auto cross requires resolved child sizes and margins"));
            }
            let edges = item.edges;
            let cross_values = if is_horizontal {
                [edges.padding.top,edges.padding.bottom,edges.border.top,edges.border.bottom]
            } else {
                [edges.padding.left,edges.padding.right,edges.border.left,edges.border.right]
            };
            let main_values=if is_horizontal {
                [edges.padding.left,edges.padding.right,edges.border.left,edges.border.right]
            } else {
                [edges.padding.top,edges.padding.bottom,edges.border.top,edges.border.bottom]
            };
            let outer_main=main_values.into_iter()
                .chain([item.main_start.expect("checked"),item.main_end.expect("checked")])
                .fold(lu(item.flex.hypothetical),|a,v|a+lu(v));
            let outer_cross=cross_values.into_iter()
                .chain([item.cross_start.expect("checked"),item.cross_end.expect("checked")])
                .fold(lu(item.cross_content_size),|a,v|a+lu(v));
            let separator=if line_main.raw()!=0 {lu(node.main_gap)}else{LayoutUnit::from_raw(0)};
            let candidate=line_main+separator+outer_main;
            if node.wrap!=Wrap::NoWrap && line_main.raw()!=0 && candidate>main_limit {
                lines.push((line_main,line_cross));
                line_main=outer_main; line_cross=outer_cross;
            } else {
                line_main=candidate; line_cross=line_cross.max(outer_cross);
            }
        }
        lines.push((line_main,line_cross));
        let mut used_u=LayoutUnit::from_raw(0);
        if resolves_own_cross {
            for (line,(_,cross)) in lines.iter().enumerate() {
                if line>0 {used_u=used_u+lu(node.cross_gap);}
                used_u=used_u+*cross;
            }
        } else {
            // For an orthogonal nowrap descendant, auto main size is the
            // intrinsic extent occupied by its children along that axis.
            for (main,_) in &lines {used_u=used_u.max(*main);}
        }
        let used=used_u.to_px();
        let parent_id = node.parent.clone();
        if let Some(parent) = parent_id {
            let parent_index = *indices.get(parent.as_str()).ok_or(
                FlexMathError::InvalidInput("missing auto cross parent"),
            )?;
            let parent_horizontal=horizontal(adapted[parent_index].direction);
            let item = adapted[index].item.as_mut().ok_or(
                FlexMathError::InvalidInput("missing container flex item"),
            )?;
            let parent_cross_width=!parent_horizontal;
            if auto_width==parent_cross_width {
                item.cross_content_size = used;
                item.cross_size_auto = false;
            } else {
                item.flex.basis=used;
                item.flex.hypothetical=used.max(item.flex.min_size)
                    .min(item.flex.max_size.unwrap_or(f64::INFINITY));
            }
        }
        if is_horizontal { adapted[index].height = used; }
        else { adapted[index].width = used; }
    }
    compute_margin_tree(&adapted, writing)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::align_content::AlignContent;
    use crate::cross_alignment::CrossAlign;
    use crate::edge_pipeline::BoxEdges;
    use crate::main_alignment::JustifyContent;
    use crate::margin_flex_pipeline::MarginFlexItem;
    use crate::FlexBasis;

    fn node(id: &str, parent: Option<&str>, cross: f64) -> MarginTreeNode {
        MarginTreeNode {
            id: id.into(), parent: parent.map(str::to_string),
            width: 20.0, height: cross, item: parent.map(|_| MarginFlexItem {
                id: id.into(), flex: FlexBasis {
                    basis: 20.0, hypothetical: 20.0, grow: 0.0,
                    shrink: 0.0, min_size: 0.0, max_size: None,
                }, cross_content_size: cross, edges: BoxEdges::default(),
                main_start: Some(0.0), main_end: Some(0.0),
                cross_start: Some(0.0), cross_end: Some(0.0),
                order: 0, align_self: CrossAlign::Auto,
                cross_size_auto: false, min_cross_content_size: 0.0,
                max_cross_content_size: None, baseline_from_cross_start: None,
            }),
            edges: BoxEdges::default(), direction: Direction::Row,
            wrap: Wrap::NoWrap, main_gap: 0.0, cross_gap: 0.0,
            justify: JustifyContent::FlexStart,
            align_items: CrossAlign::FlexStart,
            align_content: AlignContent::FlexStart, intrinsic_basis: None,
        }
    }

    #[test]
    fn nested_auto_cross_uses_largest_definite_child() {
        let nodes = vec![
            node("root", None, 80.0),
            node("container", Some("root"), 0.0),
            node("a", Some("container"), 15.0),
            node("b", Some("container"), 30.0),
        ];
        let result = compute_auto_cross_tree(
            &nodes, &["container".into()], WritingDirection::Ltr,
        ).unwrap();
        assert_eq!(result.boxes[1].content.height, 30.0);
    }

    #[test]
    fn acceptance_a01_orthogonal_auto_column_and_parent_height() {
        let mut root = node("root", None, 0.0);
        root.width = 120.0;
        root.height = 0.0;
        let mut fixed = node("fixed", Some("root"), 10.0);
        fixed.width = 40.0;
        fixed.item.as_mut().unwrap().flex.basis = 40.0;
        fixed.item.as_mut().unwrap().flex.hypothetical = 40.0;
        let mut column = node("column", Some("root"), 0.0);
        column.width = 80.0;
        column.direction = Direction::Column;
        column.item.as_mut().unwrap().flex.basis = 80.0;
        column.item.as_mut().unwrap().flex.hypothetical = 80.0;
        let mut text = node("text", Some("column"), 60.0);
        text.width = 80.0;
        text.item.as_mut().unwrap().flex.basis = 60.0;
        text.item.as_mut().unwrap().flex.hypothetical = 60.0;
        text.item.as_mut().unwrap().cross_content_size = 80.0;
        let result = compute_auto_cross_tree(&[root,fixed,column,text],
            &["column".into(),"root".into()],WritingDirection::Ltr).unwrap();
        assert!((result.boxes[0].content.height-60.0).abs()<0.01);
        assert!((result.boxes[2].content.height-60.0).abs()<0.01);
    }

    #[test]
    fn wrapping_auto_cross_is_rejected() {
        let mut root = node("root", None, 0.0);
        root.wrap = Wrap::Wrap;
        let nodes = vec![root, node("leaf", Some("root"), 10.0)];
        assert!(compute_auto_cross_tree(
            &nodes, &["root".into()], WritingDirection::Ltr,
        ).is_err());
    }
}
