//! F2.2.4.5 bounded multi-pass dependency/measurement coordinator.
//! The callbacks are supplied by a caller: this core does not access GUI APIs.
//! CSS semantics must be provided by the pure recompute callback, which may
//! reject unsupported sizing cycles rather than silently inventing geometry.

use crate::convergence::{begin_convergence, RoundStatus};
use crate::measurement_coordinator::complete_measurement_pass;
use crate::measurement_plan::{MeasuredRevision, MeasurementRequest, Node};
use crate::measurement_round::prepare_round;
use crate::remeasurement::plan_remeasurement;
use crate::used_size_tree::UsedSizeTree;
use crate::FlexMathError;

#[derive(Clone, Debug)]
pub struct DependencyResolution {
    pub used_sizes: UsedSizeTree,
    pub measurements: Vec<MeasuredRevision>,
    pub iterations: usize,
}

pub fn resolve_measurement_dependencies<M, R>(
    generation: u64,
    nodes: &[Node],
    initial: UsedSizeTree,
    revisions: &[(String, u64)],
    cached: &[MeasuredRevision],
    max_iterations: usize,
    mut measure: M,
    mut recompute: R,
) -> Result<DependencyResolution, FlexMathError>
where
    M: FnMut(&MeasurementRequest) -> Result<MeasuredRevision, FlexMathError>,
    R: FnMut(&[MeasuredRevision], &UsedSizeTree) -> Result<UsedSizeTree, FlexMathError>,
{
    if initial.generation != generation || initial.content.len() != nodes.len()
        || initial.content.iter().zip(nodes.iter()).any(|((id,_),node)| id != &node.id)
    {
        return Err(FlexMathError::InvalidInput("invalid initial sizing generation/tree"));
    }
    let mut state = begin_convergence(initial.clone(), max_iterations)?;
    let mut previous = initial.clone();
    let mut current = initial;
    let mut measurements = cached.to_vec();
    for _ in 0..max_iterations {
        let delta = plan_remeasurement(generation, nodes, &previous, &current)?;
        let round = prepare_round(
            generation, nodes, &delta, &current.content, revisions, &measurements,
        )?;
        let results: Vec<MeasuredRevision> =
            round.requests.iter().map(&mut measure).collect::<Result<_,_>>()?;
        let accepted = crate::measurement_round::accept_round(&round, &results, generation)?;
        let updated = recompute(&accepted, &current)?;
        let transition = complete_measurement_pass(
            state, &round, &results, updated.clone(), generation,
        )?;
        if transition.status == RoundStatus::Converged {
            return Ok(DependencyResolution {
                used_sizes: updated,
                measurements: accepted,
                iterations: transition.convergence.iterations,
            });
        }
        state = transition.convergence;
        measurements = accepted;
        previous = current;
        current = updated;
    }
    Err(FlexMathError::NoProgress)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::{AxisConstraint, Constraints};

    fn known(n: f64) -> AxisConstraint {
        AxisConstraint { value: Some(n), definite: true }
    }
    fn unknown() -> AxisConstraint {
        AxisConstraint { value: None, definite: false }
    }
    fn tree(width: Option<f64>) -> UsedSizeTree {
        UsedSizeTree {
            generation: 8,
            content: vec![
                ("root".into(), Constraints { width: known(200.0), height: known(100.0) }),
                ("leaf".into(), Constraints {
                    width: width.map_or(unknown(), known),
                    height: known(20.0),
                }),
            ],
            deferred: if width.is_none() { vec!["leaf".into()] } else { vec![] },
        }
    }
    fn nodes() -> Vec<Node> {
        vec![
            Node { id: "root".into(), parent: None },
            Node { id: "leaf".into(), parent: Some("root".into()) },
        ]
    }
    #[test]
    fn two_pass_intrinsic_resolution_converges() {
        let result = resolve_measurement_dependencies(
            8, &nodes(), tree(None), &[], &[], 4,
            |req| Ok(MeasuredRevision {
                node_id: req.node_id.clone(),
                constraints: req.constraints,
                revision: req.revision,
            }),
            |measured, _| {
                assert_eq!(measured.len(), 2);
                Ok(tree(Some(60.0)))
            },
        ).unwrap();
        assert_eq!(result.iterations, 2);
        assert_eq!(result.used_sizes.content[1].1.width, known(60.0));
    }
    #[test]
    fn repeated_unresolved_constraints_fail_closed() {
        let result = resolve_measurement_dependencies(
            8, &nodes(), tree(None), &[], &[], 4,
            |req| Ok(MeasuredRevision {
                node_id: req.node_id.clone(),
                constraints: req.constraints,
                revision: req.revision,
            }),
            |_, tree| Ok(tree.clone()),
        );
        assert!(result.is_err());
    }
}
