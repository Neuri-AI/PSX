//! F2.2.4 pure preorder propagation of definite CSS used content dimensions.
//! No implicit used size for auto, intrinsic, or cyclic percentages.

use crate::constraint_propagation::ChildSizing;
use crate::measurement_plan::{Constraints, Node};
use crate::percentage_box_sizing::BoxSizing;
use crate::used_size::resolve_used_content_size;
use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct NodeUsedSizing {
    pub node_id: String,
    pub sizing: ChildSizing,
    pub box_sizing: BoxSizing,
    pub horizontal_padding_border: f64,
    pub vertical_padding_border: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct UsedSizeTree {
    pub generation: u64,
    pub content: Vec<(String, Constraints)>,
    pub deferred: Vec<String>,
}

pub fn propagate_definite_used_sizes(
    generation: u64,
    nodes: &[Node],
    root_content: Constraints,
    children: &[NodeUsedSizing],
) -> Result<UsedSizeTree, FlexMathError> {
    if nodes.is_empty() {
        if !children.is_empty() {
            return Err(FlexMathError::InvalidInput("styles without tree"));
        }
        return Ok(UsedSizeTree { generation, content: vec![], deferred: vec![] });
    }
    let mut styles = HashMap::new();
    for style in children {
        if style.node_id == nodes[0].id || styles.insert(style.node_id.as_str(), style).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate/root child style"));
        }
    }
    if styles.len() != nodes.len() - 1 {
        return Err(FlexMathError::InvalidInput("missing/unknown child styles"));
    }
    let mut seen = HashSet::new();
    let mut content_map = HashMap::new();
    let mut content = Vec::with_capacity(nodes.len());
    let mut deferred = Vec::new();
    for (index, node) in nodes.iter().enumerate() {
        if node.id.is_empty() || !seen.insert(node.id.as_str()) {
            return Err(FlexMathError::InvalidInput("duplicate/empty node ID"));
        }
        let used = if index == 0 {
            if node.parent.is_some() {
                return Err(FlexMathError::InvalidInput("root has parent"));
            }
            root_content
        } else {
            let parent_id = node.parent.as_ref().ok_or(
                FlexMathError::InvalidInput("child has no parent")
            )?;
            let parent = *content_map.get(parent_id.as_str()).ok_or(
                FlexMathError::InvalidInput("non-preorder/unknown parent")
            )?;
            let style = styles.get(node.id.as_str()).ok_or(
                FlexMathError::InvalidInput("missing/unknown child styles")
            )?;
            resolve_used_content_size(
                parent, style.sizing, style.box_sizing,
                style.horizontal_padding_border, style.vertical_padding_border,
            )?.content
        };
        if !used.width.definite || !used.height.definite {
            deferred.push(node.id.clone());
        }
        content_map.insert(node.id.as_str(), used);
        content.push((node.id.clone(), used));
    }
    if !styles.keys().all(|key| seen.contains(key)) {
        return Err(FlexMathError::InvalidInput("unknown child style"));
    }
    Ok(UsedSizeTree { generation, content, deferred })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::AxisConstraint;
    use crate::sizing::Length;

    fn definite(n: f64) -> AxisConstraint { AxisConstraint { value: Some(n), definite: true } }
    fn unknown() -> AxisConstraint { AxisConstraint { value: None, definite: false } }
    fn pair(w: AxisConstraint, h: AxisConstraint) -> Constraints {
        Constraints { width: w, height: h }
    }
    fn style(id: &str, width: Length, height: Length) -> NodeUsedSizing {
        NodeUsedSizing { node_id: id.into(), sizing: ChildSizing { width, height },
            box_sizing: BoxSizing::ContentBox,
            horizontal_padding_border: 0.0, vertical_padding_border: 0.0 }
    }
    #[test]
    fn nested_definite_percentages_resolve_in_preorder() {
        let nodes = [
            Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) },
            Node { id: "leaf".into(), parent: Some("child".into()) },
        ];
        let r = propagate_definite_used_sizes(
            8, &nodes, pair(definite(200.0), definite(80.0)),
            &[style("child", Length::Percent(0.5), Length::Percent(0.25)),
              style("leaf", Length::Percent(0.5), Length::Px(10.0))],
        ).unwrap();
        assert_eq!(r.content[1].1, pair(definite(100.0), definite(20.0)));
        assert_eq!(r.content[2].1, pair(definite(50.0), definite(10.0)));
        assert!(r.deferred.is_empty());
    }
    #[test]
    fn auto_chain_keeps_percent_height_unresolved() {
        let nodes = [
            Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) },
            Node { id: "leaf".into(), parent: Some("child".into()) },
        ];
        let r = propagate_definite_used_sizes(
            8, &nodes, pair(definite(200.0), definite(80.0)),
            &[style("child", Length::Px(100.0), Length::Auto),
              style("leaf", Length::Percent(0.5), Length::Percent(0.5))],
        ).unwrap();
        assert_eq!(r.content[2].1, pair(definite(50.0), unknown()));
        assert_eq!(r.deferred, vec!["child", "leaf"]);
    }
}
