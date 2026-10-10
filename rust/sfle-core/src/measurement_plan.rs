//! F2.2.4 measurement worklist for prevalidated preorder layout trees.
//!
//! This module never infers CSS child constraints. An upstream style/layout
//! stage must supply each child's constraints before native measurement.

use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AxisConstraint {
    pub value: Option<f64>,
    pub definite: bool,
}

impl AxisConstraint {
    fn validate(self) -> Result<(), FlexMathError> {
        if self.definite && self.value.is_none()
            || self.value.is_some_and(|value| !value.is_finite() || value < 0.0)
        {
            return Err(FlexMathError::InvalidInput("invalid available dimension"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Constraints {
    pub width: AxisConstraint,
    pub height: AxisConstraint,
}
impl Constraints {
    fn validate(self) -> Result<(), FlexMathError> {
        self.width.validate()?;
        self.height.validate()
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Node {
    pub id: String,
    pub parent: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MeasuredRevision {
    pub node_id: String,
    pub constraints: Constraints,
    pub revision: u64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MeasurementRequest {
    pub node_id: String,
    pub constraints: Constraints,
    pub generation: u64,
    pub revision: u64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MeasurementPlan {
    pub generation: u64,
    pub requests: Vec<MeasurementRequest>,
    pub reusable: Vec<MeasuredRevision>,
}

pub fn plan_measurements(
    generation: u64,
    nodes: &[Node],
    root_constraints: Constraints,
    child_constraints: &[(String, Constraints)],
    measurements: &[MeasuredRevision],
    revisions: &[(String, u64)],
) -> Result<MeasurementPlan, FlexMathError> {
    root_constraints.validate()?;
    if nodes.is_empty() {
        if !child_constraints.is_empty() || !measurements.is_empty() || !revisions.is_empty() {
            return Err(FlexMathError::InvalidInput("metadata without tree nodes"));
        }
        return Ok(MeasurementPlan { generation, requests: vec![], reusable: vec![] });
    }
    let mut seen = HashSet::new();
    for (index, node) in nodes.iter().enumerate() {
        if node.id.is_empty() || !seen.insert(node.id.clone()) {
            return Err(FlexMathError::InvalidInput("duplicate/empty node ID"));
        }
        if index == 0 {
            if node.parent.is_some() {
                return Err(FlexMathError::InvalidInput("first node must be root"));
            }
        } else if node.parent.as_ref().is_none_or(|parent| !seen.contains(parent)) {
            return Err(FlexMathError::InvalidInput("tree must be validated preorder"));
        }
    }
    let root = &nodes[0].id;
    let mut constraints = HashMap::new();
    constraints.insert(root.clone(), root_constraints);
    for (id, value) in child_constraints {
        value.validate()?;
        if !seen.contains(id) {
            return Err(FlexMathError::InvalidInput("unknown child constraint"));
        }
        if id == root {
            if *value != root_constraints {
                return Err(FlexMathError::InvalidInput("root constraint conflict"));
            }
        } else if constraints.insert(id.clone(), *value).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate child constraint"));
        }
    }
    let mut versions = HashMap::new();
    for (id, revision) in revisions {
        if !seen.contains(id) || versions.insert(id.as_str(), *revision).is_some() {
            return Err(FlexMathError::InvalidInput("unknown/duplicate revision"));
        }
    }
    let mut old = HashMap::new();
    for measured in measurements {
        if !seen.contains(&measured.node_id)
            || old.insert(measured.node_id.as_str(), measured).is_some() {
            return Err(FlexMathError::InvalidInput("unknown/duplicate measured node"));
        }
        measured.constraints.validate()?;
    }
    if constraints.len() != nodes.len() {
        return Err(FlexMathError::InvalidInput("unresolved child constraints"));
    }
    let mut requests = Vec::new();
    let mut reusable = Vec::new();
    let mut dirty_ancestors: HashSet<String> = HashSet::new();
    for node in nodes.iter().rev() {
        let requested = *constraints.get(&node.id).expect("complete constraints");
        let revision = *versions.get(node.id.as_str()).unwrap_or(&0);
        match old.get(node.id.as_str()) {
            Some(cached) if !dirty_ancestors.contains(&node.id)
                && cached.constraints == requested && cached.revision == revision =>
                reusable.push((*cached).clone()),
            _ => {
                requests.push(MeasurementRequest {
                    node_id: node.id.clone(), constraints: requested, generation, revision,
                });
                if let Some(parent) = &node.parent {
                    dirty_ancestors.insert(parent.clone());
                }
            }
        }
    }
    Ok(MeasurementPlan { generation, requests, reusable })
}

pub fn accept_measurement(
    request: &MeasurementRequest,
    measured: &MeasuredRevision,
    current_generation: u64,
) -> Result<(), FlexMathError> {
    if request.generation != current_generation
        || request.node_id != measured.node_id
        || request.revision != measured.revision
        || request.constraints != measured.constraints {
        return Err(FlexMathError::InvalidInput("stale or mismatched measurement"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn definite(x: f64) -> AxisConstraint {
        AxisConstraint { value: Some(x), definite: true }
    }
    fn pair(w: f64, h: f64) -> Constraints {
        Constraints { width: definite(w), height: definite(h) }
    }
    fn nodes() -> Vec<Node> {
        vec![
            Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) },
            Node { id: "leaf".into(), parent: Some("child".into()) },
        ]
    }
    #[test]
    fn plans_postorder_and_reuses_exact_snapshot() {
        let cached = MeasuredRevision {
            node_id: "child".into(), constraints: pair(50.0, 40.0), revision: 1,
        };
        let leaf = MeasuredRevision {
            node_id: "leaf".into(), constraints: pair(20.0, 10.0), revision: 0,
        };
        let plan = plan_measurements(
            8, &nodes(), pair(100.0, 100.0),
            &[("child".into(), pair(50.0, 40.0)), ("leaf".into(), pair(20.0, 10.0))],
            &[cached.clone(), leaf.clone()], &[("child".into(), 1)],
        ).unwrap();
        assert_eq!(plan.requests.iter().map(|r| r.node_id.as_str()).collect::<Vec<_>>(),
                   vec!["root"]);
        assert_eq!(plan.reusable, vec![leaf, cached]);
    }
    #[test]
    fn rejects_unresolved_children_and_stale_generation() {
        assert!(plan_measurements(
            8, &nodes(), pair(100.0, 100.0), &[], &[], &[],
        ).is_err());
        let request = MeasurementRequest {
            node_id: "x".into(), constraints: pair(10.0, 10.0),
            generation: 8, revision: 0,
        };
        let measured = MeasuredRevision {
            node_id: "x".into(), constraints: pair(10.0, 10.0), revision: 0,
        };
        assert!(accept_measurement(&request, &measured, 9).is_err());
    }
    #[test]
    fn dirty_leaf_forces_remeasurement_of_cached_parents() {
        let root = MeasuredRevision {
            node_id: "root".into(), constraints: pair(100.0, 100.0), revision: 0,
        };
        let child = MeasuredRevision {
            node_id: "child".into(), constraints: pair(50.0, 40.0), revision: 1,
        };
        let plan = plan_measurements(
            8, &nodes(), pair(100.0, 100.0),
            &[("child".into(), pair(50.0, 40.0)), ("leaf".into(), pair(20.0, 10.0))],
            &[root, child], &[("child".into(), 1)],
        ).unwrap();
        assert_eq!(plan.requests.iter().map(|r| r.node_id.as_str()).collect::<Vec<_>>(),
                   vec!["leaf", "child", "root"]);
        assert!(plan.reusable.is_empty());
    }

}
