//! Restricted F2.2.4.5 auto leaf sizes from validated intrinsic snapshots.
//! Indefinite percentage cycles and automatic Flex container sizes remain unsupported.
use crate::measurement_plan::{Constraints, MeasuredRevision, Node, AxisConstraint};
use crate::used_size_tree::UsedSizeTree;
use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AxisKind { Used, Auto, UnresolvedPercent, Intrinsic }

#[derive(Clone, Debug, PartialEq)]
pub struct LeafAutoSizing {
    pub node_id: String,
    pub width_kind: AxisKind,
    pub height_kind: AxisKind,
}

#[derive(Clone, Debug, PartialEq)]
pub struct IntrinsicLeafMeasurement {
    pub node_id: String,
    pub constraints: Constraints,
    pub revision: u64,
    pub preferred_width: f64,
    pub preferred_height: f64,
}

pub fn resolve_measured_auto_leaves(
    generation: u64,
    nodes: &[Node],
    used: &UsedSizeTree,
    declarations: &[LeafAutoSizing],
    measurements: &[IntrinsicLeafMeasurement],
    revisions: &[(String, u64)],
) -> Result<UsedSizeTree, FlexMathError> {
    if used.generation != generation || nodes.len() != used.content.len() {
        return Err(FlexMathError::InvalidInput("stale or mismatched used-size tree"));
    }
    let mut ids = HashSet::new();
    let mut parent_ids = HashSet::new();
    for (i, node) in nodes.iter().enumerate() {
        if !ids.insert(node.id.as_str()) || used.content[i].0 != node.id {
            return Err(FlexMathError::InvalidInput("used-size ordering mismatch"));
        }
        if let Some(parent) = &node.parent { parent_ids.insert(parent.as_str()); }
    }
    let mut styles = HashMap::new();
    for style in declarations {
        if !ids.contains(style.node_id.as_str()) || styles.insert(style.node_id.as_str(), style).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate/unknown auto sizing"));
        }
    }
    let mut versions = HashMap::new();
    for (id, revision) in revisions {
        if !ids.contains(id.as_str()) || versions.insert(id.as_str(), *revision).is_some() {
            return Err(FlexMathError::InvalidInput("invalid revision"));
        }
    }
    let mut measured = HashMap::new();
    for item in measurements {
        if !ids.contains(item.node_id.as_str()) || measured.insert(item.node_id.as_str(), item).is_some()
            || ![item.preferred_width, item.preferred_height].iter().all(|v| v.is_finite() && *v >= 0.0)
        { return Err(FlexMathError::InvalidInput("invalid measurement")); }
    }
    let mut content = Vec::with_capacity(nodes.len());
    let mut deferred = Vec::new();
    for (id, constraints) in &used.content {
        let mut updated = *constraints;
        if let Some(style) = styles.get(id.as_str()) {
            let need_w = style.width_kind == AxisKind::Auto && !updated.width.definite;
            let need_h = style.height_kind == AxisKind::Auto && !updated.height.definite;
            if (need_w || need_h) && parent_ids.contains(id.as_str()) {
                return Err(FlexMathError::InvalidInput("auto container contributions not implemented"));
            }
            let item = measured.get(id.as_str());
            if (need_w || need_h) && item.is_none() {
                return Err(FlexMathError::InvalidInput("missing intrinsic measurement"));
            }
            if let Some(item) = item {
                if (need_w || need_h) && (item.constraints != *constraints
                    || item.revision != *versions.get(id.as_str()).unwrap_or(&0)) {
                    return Err(FlexMathError::InvalidInput("stale intrinsic measurement"));
                }
            }
            if style.width_kind == AxisKind::UnresolvedPercent && !updated.width.definite
                || style.height_kind == AxisKind::UnresolvedPercent && !updated.height.definite {
                return Err(FlexMathError::InvalidInput("indefinite cyclic percentage unsupported"));
            }
            if need_w {
                updated.width = AxisConstraint { value: Some(item.expect("checked").preferred_width), definite: true };
            }
            if need_h {
                updated.height = AxisConstraint { value: Some(item.expect("checked").preferred_height), definite: true };
            }
        }
        if !updated.width.definite || !updated.height.definite { deferred.push(id.clone()); }
        content.push((id.clone(), updated));
    }
    Ok(UsedSizeTree { generation, content, deferred })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn unknown() -> AxisConstraint { AxisConstraint { value: None, definite: false } }
    fn known(n: f64) -> AxisConstraint { AxisConstraint { value: Some(n), definite: true } }
    #[test]
    fn measured_auto_leaf_resolves_both_axes() {
        let nodes = [Node { id: "root".into(), parent: None },
            Node { id: "leaf".into(), parent: Some("root".into()) }];
        let c = Constraints { width: unknown(), height: unknown() };
        let tree = UsedSizeTree { generation: 8, content: vec![
            ("root".into(), Constraints { width: known(200.0), height: known(100.0) }),
            ("leaf".into(), c)], deferred: vec!["leaf".into()] };
        let style = LeafAutoSizing { node_id: "leaf".into(), width_kind: AxisKind::Auto,
            height_kind: AxisKind::Auto };
        let measurement = IntrinsicLeafMeasurement { node_id: "leaf".into(), constraints: c,
            revision: 1, preferred_width: 30.0, preferred_height: 40.0 };
        let out = resolve_measured_auto_leaves(8,&nodes,&tree,&[style],&[measurement],
            &[("leaf".into(),1)]).unwrap();
        assert_eq!(out.content[1].1.width, known(30.0));
        assert_eq!(out.content[1].1.height, known(40.0));
        assert!(out.deferred.is_empty());
    }
}
