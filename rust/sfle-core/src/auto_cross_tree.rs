//! Restricted bottom-up nowrap auto cross sizing, matching Python's
//! auto_cross_tree boundary. Unsupported wrapping and orthogonal dependent
//! containers are explicit errors, never approximate CSS dimensions.
use crate::margin_tree::{compute_margin_tree, MarginTreeLayout, MarginTreeNode};
use crate::line_layout::{Direction, Wrap, WritingDirection};
use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

fn horizontal(direction: Direction) -> bool {
    matches!(direction, Direction::Row | Direction::RowReverse)
}

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
        if node.wrap != Wrap::NoWrap || children[node.id.as_str()].is_empty() {
            return Err(FlexMathError::InvalidInput("auto cross requires nonempty nowrap container"));
        }
        let is_horizontal = horizontal(node.direction);
        let mut used = 0.0_f64;
        for &child_index in &children[node.id.as_str()] {
            let item = adapted[child_index].item.as_ref().ok_or(
                FlexMathError::InvalidInput("auto cross child requires Flex item"),
            )?;
            if item.cross_size_auto || item.cross_start.is_none() || item.cross_end.is_none() {
                return Err(FlexMathError::InvalidInput("auto cross requires definite child cross sizes"));
            }
            let edges = item.edges;
            let cross_edges = if is_horizontal {
                edges.padding.top + edges.padding.bottom + edges.border.top + edges.border.bottom
            } else {
                edges.padding.left + edges.padding.right + edges.border.left + edges.border.right
            };
            used = used.max(item.cross_content_size + cross_edges
                + item.cross_start.expect("checked") + item.cross_end.expect("checked"));
        }
        let parent_id = node.parent.clone();
        if let Some(parent) = parent_id {
            let parent_index = *indices.get(parent.as_str()).ok_or(
                FlexMathError::InvalidInput("missing auto cross parent"),
            )?;
            if horizontal(adapted[parent_index].direction) != is_horizontal {
                return Err(FlexMathError::InvalidInput("orthogonal auto cross contribution unsupported"));
            }
            let item = adapted[index].item.as_mut().ok_or(
                FlexMathError::InvalidInput("missing container flex item"),
            )?;
            item.cross_content_size = used;
            item.cross_size_auto = false;
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
    fn wrapping_auto_cross_is_rejected() {
        let mut root = node("root", None, 0.0);
        root.wrap = Wrap::Wrap;
        let nodes = vec![root, node("leaf", Some("root"), 10.0)];
        assert!(compute_auto_cross_tree(
            &nodes, &["root".into()], WritingDirection::Ltr,
        ).is_err());
    }
}
