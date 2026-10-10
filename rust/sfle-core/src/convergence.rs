//! Bounded pure convergence bookkeeping; no CSS cycle approximation.
use crate::used_size_tree::UsedSizeTree;
use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoundStatus { Continue, Converged }

#[derive(Clone, Debug)]
pub struct ConvergenceState {
    pub generation: u64,
    pub iterations: usize,
    pub previous: UsedSizeTree,
    history: Vec<Vec<(String, crate::measurement_plan::Constraints)>>,
    pub max_iterations: usize,
}

pub fn begin_convergence(tree: UsedSizeTree, max_iterations: usize) -> Result<ConvergenceState, FlexMathError> {
    if max_iterations == 0 {
        return Err(FlexMathError::InvalidInput("positive iteration limit required"));
    }
    Ok(ConvergenceState {
        generation: tree.generation, iterations: 0, history: vec![tree.content.clone()],
        previous: tree, max_iterations,
    })
}

pub fn advance_convergence(
    mut state: ConvergenceState, current: UsedSizeTree,
) -> Result<(RoundStatus, ConvergenceState), FlexMathError> {
    if state.generation != current.generation
        || state.previous.content.len() != current.content.len()
        || state.previous.content.iter().zip(current.content.iter()).any(|(a,b)| a.0 != b.0)
    {
        return Err(FlexMathError::InvalidInput("stale generation or changed layout identity"));
    }
    if state.iterations >= state.max_iterations {
        return Err(FlexMathError::NoProgress);
    }
    state.iterations += 1;
    let definite = current.content.iter().all(|(_, size)| size.width.definite && size.height.definite);
    if current.content == state.previous.content && definite {
        state.previous = current;
        return Ok((RoundStatus::Converged, state));
    }
    if state.history.contains(&current.content) || state.iterations >= state.max_iterations {
        return Err(FlexMathError::NoProgress);
    }
    state.history.push(current.content.clone());
    state.previous = current;
    Ok((RoundStatus::Continue, state))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::{AxisConstraint, Constraints};
    fn tree(generation: u64, value: Option<f64>) -> UsedSizeTree {
        UsedSizeTree {
            generation,
            content: vec![("root".into(), Constraints {
                width: AxisConstraint { value, definite: value.is_some() },
                height: AxisConstraint { value: Some(20.0), definite: true },
            })],
            deferred: vec![],
        }
    }
    #[test]
    fn stable_definite_converges() {
        let state = begin_convergence(tree(8, Some(100.0)), 4).unwrap();
        assert_eq!(advance_convergence(state, tree(8, Some(100.0))).unwrap().0, RoundStatus::Converged);
    }
    #[test]
    fn repeated_indefinite_fails_closed() {
        let state = begin_convergence(tree(8, None), 4).unwrap();
        assert!(advance_convergence(state, tree(8, None)).is_err());
    }
    #[test]
    fn oscillation_fails_closed() {
        let state = begin_convergence(tree(8, Some(100.0)), 4).unwrap();
        let (_, state) = advance_convergence(state, tree(8, Some(120.0))).unwrap();
        assert!(advance_convergence(state, tree(8, Some(100.0))).is_err());
    }
}
