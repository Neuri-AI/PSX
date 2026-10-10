//! Pure measured-round / convergence transition. No native toolkit access.
use crate::convergence::{advance_convergence, ConvergenceState, RoundStatus};
use crate::measurement_round::{accept_round, MeasurementRound};
use crate::measurement_plan::MeasuredRevision;
use crate::used_size_tree::UsedSizeTree;
use crate::FlexMathError;

#[derive(Clone, Debug)]
pub struct RoundTransition {
    pub status: RoundStatus,
    pub convergence: ConvergenceState,
    pub measurements: Vec<MeasuredRevision>,
}

pub fn complete_measurement_pass(
    state: ConvergenceState,
    round: &MeasurementRound,
    results: &[MeasuredRevision],
    updated_tree: UsedSizeTree,
    current_generation: u64,
) -> Result<RoundTransition, FlexMathError> {
    if state.generation != current_generation || round.generation != current_generation {
        return Err(FlexMathError::InvalidInput("cross-generation measurement pass"));
    }
    let measurements = accept_round(round, results, current_generation)?;
    let (status, convergence) = advance_convergence(state, updated_tree)?;
    if status == RoundStatus::Converged && !round.deferred.is_empty() {
        return Err(FlexMathError::InvalidInput("deferred axes cannot converge"));
    }
    Ok(RoundTransition { status, convergence, measurements })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::convergence::begin_convergence;
    use crate::measurement_plan::{AxisConstraint, Constraints, MeasurementRequest};
    fn tree() -> UsedSizeTree {
        UsedSizeTree { generation: 8, deferred: vec![],
            content: vec![("root".into(), Constraints {
                width: AxisConstraint { value: Some(100.0), definite: true },
                height: AxisConstraint { value: Some(20.0), definite: true },
            })] }
    }
    #[test]
    fn completed_round_advances_only_if_all_results_match() {
        let r = MeasurementRequest {
            node_id: "root".into(), constraints: tree().content[0].1,
            generation: 8, revision: 0,
        };
        let round = MeasurementRound {
            generation: 8, requests: vec![r.clone()], retained: vec![], deferred: vec![],
        };
        let state = begin_convergence(tree(), 4).unwrap();
        assert!(complete_measurement_pass(state.clone(), &round, &[], tree(), 8).is_err());
        let measured = MeasuredRevision {
            node_id: r.node_id, constraints: r.constraints, revision: r.revision,
        };
        let outcome = complete_measurement_pass(state, &round, &[measured], tree(), 8).unwrap();
        assert_eq!(outcome.status, RoundStatus::Converged);
    }
}
