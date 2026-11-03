//! F2.2.4.5 pure generation-safe measurement round handshake.

use crate::measurement_plan::{accept_measurement, Constraints, MeasuredRevision, MeasurementRequest, Node};
use crate::remeasurement::RemeasurementDelta;
use crate::FlexMathError;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug, PartialEq)]
pub struct MeasurementRound {
    pub generation: u64,
    pub requests: Vec<MeasurementRequest>,
    pub retained: Vec<MeasuredRevision>,
    pub deferred: Vec<String>,
}

#[allow(clippy::too_many_arguments)]
pub fn prepare_round(
    generation: u64,
    nodes: &[Node],
    delta: &RemeasurementDelta,
    constraints: &[(String, Constraints)],
    revisions: &[(String, u64)],
    cached: &[MeasuredRevision],
) -> Result<MeasurementRound, FlexMathError> {
    if delta.generation != generation {
        return Err(FlexMathError::InvalidInput("stale remeasurement delta"));
    }
    let ids: HashSet<&str> = nodes.iter().map(|n| n.id.as_str()).collect();
    if ids.len() != nodes.len() {
        return Err(FlexMathError::InvalidInput("duplicate node IDs"));
    }
    let mut affected = HashSet::new();
    for id in &delta.remeasure {
        if !ids.contains(id.as_str()) || !affected.insert(id.as_str()) {
            return Err(FlexMathError::InvalidInput("invalid affected node"));
        }
    }
    let mut deferred = HashSet::new();
    for id in &delta.deferred {
        if !ids.contains(id.as_str()) || !deferred.insert(id.as_str()) {
            return Err(FlexMathError::InvalidInput("invalid deferred node"));
        }
    }
    let mut values = HashMap::new();
    for (id, constraint) in constraints {
        if !ids.contains(id.as_str()) || values.insert(id.as_str(), *constraint).is_some() {
            return Err(FlexMathError::InvalidInput("invalid constraints"));
        }
    }
    if values.len() != nodes.len() {
        return Err(FlexMathError::InvalidInput("missing constraints"));
    }
    for id in deferred {
        let axis = values[id];
        if axis.width.definite && axis.height.definite {
            return Err(FlexMathError::InvalidInput("deferred node is definite"));
        }
    }
    let mut versions = HashMap::new();
    for (id, revision) in revisions {
        if !ids.contains(id.as_str()) || versions.insert(id.as_str(), *revision).is_some() {
            return Err(FlexMathError::InvalidInput("invalid revision"));
        }
    }
    let mut old = HashMap::new();
    for item in cached {
        if !ids.contains(item.node_id.as_str()) || old.insert(item.node_id.as_str(), item).is_some() {
            return Err(FlexMathError::InvalidInput("invalid cached measurement"));
        }
    }
    let mut requests = Vec::new();
    let mut retained = Vec::new();
    for node in nodes.iter().rev() {
        let constraint = values[node.id.as_str()];
        let revision = *versions.get(node.id.as_str()).unwrap_or(&0);
        match old.get(node.id.as_str()) {
            Some(item) if !affected.contains(node.id.as_str())
                && item.constraints == constraint && item.revision == revision => retained.push((*item).clone()),
            _ => requests.push(MeasurementRequest {
                node_id: node.id.clone(), constraints: constraint, generation, revision,
            }),
        }
    }
    Ok(MeasurementRound { generation, requests, retained, deferred: delta.deferred.clone() })
}

pub fn accept_round(
    round: &MeasurementRound,
    measured: &[MeasuredRevision],
    current_generation: u64,
) -> Result<Vec<MeasuredRevision>, FlexMathError> {
    if round.generation != current_generation {
        return Err(FlexMathError::InvalidInput("stale measurement round"));
    }
    let mut supplied = HashMap::new();
    for item in measured {
        if supplied.insert(item.node_id.as_str(), item).is_some() {
            return Err(FlexMathError::InvalidInput("duplicate measurement"));
        }
    }
    if supplied.len() != round.requests.len() {
        return Err(FlexMathError::InvalidInput("incomplete measurement round"));
    }
    for req in &round.requests {
        let item = supplied.get(req.node_id.as_str()).ok_or(
            FlexMathError::InvalidInput("missing measurement")
        )?;
        accept_measurement(req, item, current_generation)?;
    }
    let mut result = round.retained.clone();
    result.extend(round.requests.iter().map(|req| supplied[req.node_id.as_str()].clone()));
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::AxisConstraint;
    fn size(w: f64) -> Constraints {
        Constraints { width: AxisConstraint { value: Some(w), definite: true },
            height: AxisConstraint { value: Some(20.0), definite: true } }
    }
    #[test]
    fn round_rejects_stale_and_incomplete_measurements() {
        let nodes = [Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) }];
        let delta = RemeasurementDelta { generation: 8, changed: vec!["child".into()],
            remeasure: vec!["child".into(), "root".into()], deferred: vec![] };
        let round = prepare_round(8, &nodes, &delta,
            &[("root".into(), size(200.0)), ("child".into(), size(100.0))],
            &[], &[]).unwrap();
        assert_eq!(round.requests[0].node_id, "child");
        assert!(accept_round(&round, &[], 8).is_err());
        let results: Vec<_> = round.requests.iter().map(|r| MeasuredRevision {
            node_id: r.node_id.clone(), constraints: r.constraints, revision: r.revision,
        }).collect();
        assert_eq!(accept_round(&round, &results, 8).unwrap().len(), 2);
        assert!(accept_round(&round, &results, 9).is_err());
    }
}
