//! Pure F2.2.4.5 dependency-based measurement invalidation, no native calls.

use crate::measurement_plan::Node;
use crate::used_size_tree::UsedSizeTree;
use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct RemeasurementDelta {
    pub generation: u64,
    pub changed: Vec<String>,
    pub remeasure: Vec<String>,
    pub deferred: Vec<String>,
}

pub fn plan_remeasurement(
    generation: u64,
    nodes: &[Node],
    previous: &UsedSizeTree,
    current: &UsedSizeTree,
) -> Result<RemeasurementDelta, FlexMathError> {
    if current.generation != generation || previous.generation > generation
        || previous.content.len() != nodes.len() || current.content.len() != nodes.len()
    {
        return Err(FlexMathError::InvalidInput("stale or mismatched used-size tree"));
    }
    let mut parents: HashMap<&str, Option<&str>> = HashMap::new();
    let mut old = HashMap::new();
    let mut new = HashMap::new();
    for (index, node) in nodes.iter().enumerate() {
        if previous.content[index].0 != node.id || current.content[index].0 != node.id
            || node.id.is_empty() || parents.contains_key(node.id.as_str())
        {
            return Err(FlexMathError::InvalidInput("used-size node order mismatch"));
        }
        if index == 0 && node.parent.is_some() {
            return Err(FlexMathError::InvalidInput("root has parent"));
        }
        if index > 0 && node.parent.as_ref().is_none_or(|id| !parents.contains_key(id.as_str())) {
            return Err(FlexMathError::InvalidInput("invalid preorder parent"));
        }
        parents.insert(node.id.as_str(), node.parent.as_deref());
        old.insert(node.id.as_str(), previous.content[index].1);
        new.insert(node.id.as_str(), current.content[index].1);
    }
    let mut changed = HashSet::new();
    for node in nodes {
        if old.get(node.id.as_str()) != new.get(node.id.as_str()) {
            changed.insert(node.id.as_str());
        }
    }
    let mut affected = changed.clone();
    for node in nodes {
        if node.parent.as_deref().is_some_and(|parent| affected.contains(parent)) {
            affected.insert(node.id.as_str());
        }
    }
    let descendants: Vec<&str> = affected.iter().copied().collect();
    for id in descendants {
        let mut cursor = *parents.get(id).ok_or(FlexMathError::InvalidInput("unknown node"))?;
        while let Some(parent) = cursor {
            affected.insert(parent);
            cursor = *parents.get(parent).ok_or(FlexMathError::InvalidInput("unknown ancestor"))?;
        }
    }
    let deferred = nodes.iter().filter(|n| {
        let c = new[n.id.as_str()];
        !c.width.definite || !c.height.definite
    }).map(|n| n.id.clone()).collect();
    Ok(RemeasurementDelta {
        generation,
        changed: nodes.iter().filter(|n| changed.contains(n.id.as_str())).map(|n| n.id.clone()).collect(),
        remeasure: nodes.iter().rev().filter(|n| affected.contains(n.id.as_str())).map(|n| n.id.clone()).collect(),
        deferred,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::{AxisConstraint, Constraints};

    fn size(v: f64) -> Constraints {
        Constraints {
            width: AxisConstraint { value: Some(v), definite: true },
            height: AxisConstraint { value: Some(20.0), definite: true },
        }
    }

    #[test]
    fn changed_child_invalidates_ancestors_and_descendants() {
        let nodes = vec![
            Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) },
            Node { id: "leaf".into(), parent: Some("child".into()) },
        ];
        let previous = UsedSizeTree { generation: 7,
            content: vec![("root".into(), size(200.0)), ("child".into(), size(100.0)), ("leaf".into(), size(50.0))],
            deferred: vec![] };
        let mut current = previous.clone();
        current.generation = 8;
        current.content[1].1 = size(120.0);
        let delta = plan_remeasurement(8, &nodes, &previous, &current).unwrap();
        assert_eq!(delta.changed, vec!["child"]);
        assert_eq!(delta.remeasure, vec!["leaf", "child", "root"]);
    }
}
