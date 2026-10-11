//! Restricted zero-edge recursive resolved Flexbox geometry.
//! Reuses existing line formation, grow/shrink, and physical placement.

use crate::line_layout::{Direction, Wrap, WritingDirection, Rect};
use crate::resolved_pipeline::{compute_resolved_flex, ResolvedFlexItem};
use crate::{FlexBasis, FlexMathError};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct ResolvedTreeNode {
    pub id: String,
    pub parent: Option<String>,
    pub width: f64,
    pub height: f64,
    pub flex: Option<FlexBasis>,
    pub direction: Direction,
    pub wrap: Wrap,
    pub main_gap: f64,
    pub cross_gap: f64,
    pub order: i32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ResolvedTreeBox {
    pub node_id: String,
    pub rect: Rect,
}

pub fn compute_resolved_tree(
    nodes: &[ResolvedTreeNode],
    writing: WritingDirection,
) -> Result<Vec<ResolvedTreeBox>, FlexMathError> {
    if nodes.is_empty() { return Ok(vec![]); }
    let mut seen = HashSet::new();
    let mut children: HashMap<&str, Vec<usize>> = HashMap::new();
    for (idx, node) in nodes.iter().enumerate() {
        if node.id.is_empty() || !seen.insert(node.id.as_str())
            || ![node.width, node.height, node.main_gap, node.cross_gap].iter()
                .all(|v| v.is_finite() && *v >= 0.0)
        {
            return Err(FlexMathError::InvalidInput("invalid resolved node"));
        }
        if idx == 0 {
            if node.parent.is_some() { return Err(FlexMathError::InvalidInput("root has parent")); }
        } else {
            let parent = node.parent.as_deref().ok_or(FlexMathError::InvalidInput("missing parent"))?;
            if !children.contains_key(parent) || node.flex.is_none() {
                return Err(FlexMathError::InvalidInput("non-preorder parent or unresolved flex basis"));
            }
            children.get_mut(parent).expect("validated parent").push(idx);
        }
        children.insert(node.id.as_str(), vec![]);
    }
    let mut geometry = HashMap::new();
    geometry.insert(nodes[0].id.as_str(), Rect {
        x: 0.0, y: 0.0, width: nodes[0].width, height: nodes[0].height,
    });
    for node in nodes {
        let origin = *geometry.get(node.id.as_str()).expect("preorder coordinates");
        let child_ids = &children[node.id.as_str()];
        if child_ids.is_empty() { continue; }
        let horizontal = matches!(node.direction, Direction::Row | Direction::RowReverse);
        let items: Vec<_> = child_ids.iter().map(|&index| {
            let child = &nodes[index];
            ResolvedFlexItem {
                id: child.id.clone(),
                flex: child.flex.expect("validated flex basis"),
                cross_size: if horizontal { child.height } else { child.width },
                order: child.order,
            }
        }).collect();
        let positioned = compute_resolved_flex(
            &items, origin.width, origin.height,
            node.direction, writing, node.wrap, node.main_gap, node.cross_gap,
        )?;
        for item in positioned.items {
            geometry.insert(
                nodes.iter().find(|n| n.id == item.id).expect("known child").id.as_str(),
                Rect { x: origin.x + item.rect.x, y: origin.y + item.rect.y,
                       width: item.rect.width, height: item.rect.height },
            );
        }
    }
    Ok(nodes.iter().map(|node| ResolvedTreeBox {
        node_id: node.id.clone(), rect: geometry[node.id.as_str()],
    }).collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn basis(n: f64) -> FlexBasis {
        FlexBasis { basis: n, hypothetical: n, min_size: 0.0,
                    max_size: None, grow: 0.0, shrink: 1.0 }
    }
    fn node(id: &str, parent: Option<&str>, w: f64, h: f64, flex: Option<FlexBasis>) -> ResolvedTreeNode {
        ResolvedTreeNode { id: id.into(), parent: parent.map(str::to_string),
            width: w, height: h, flex, direction: Direction::Row, wrap: Wrap::NoWrap,
            main_gap: 0.0, cross_gap: 0.0, order: 0 }
    }
    #[test]
    fn nested_absolute_coordinates_include_parent_position() {
        let mut root = node("root", None, 200.0, 80.0, None);
        root.main_gap = 10.0;
        let a = node("a", Some("root"), 40.0, 20.0, Some(basis(40.0)));
        let b = node("b", Some("root"), 100.0, 40.0, Some(basis(100.0)));
        let c = node("c", Some("b"), 30.0, 10.0, Some(basis(30.0)));
        let result = compute_resolved_tree(&[root, a, b, c], WritingDirection::Ltr).unwrap();
        assert_eq!(result[2].rect.x, 50.0);
        assert_eq!(result[3].rect.x, 50.0);
    }
}
