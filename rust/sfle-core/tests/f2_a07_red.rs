mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a07_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A07");
    let result = compute(&snapshot).expect("A07: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    assert!(case["expected"]["max_iterations"].as_u64().unwrap()>0);
    assert!(result.boxes[0].content.height.is_finite());
}

#[test]
fn acceptance_a07_bounded_oscillation_is_rejected() {
    use sfle_core::convergence::{advance_convergence,begin_convergence};
    use sfle_core::used_size_tree::UsedSizeTree;
    use sfle_core::measurement_plan::{AxisConstraint,Constraints};
    fn tree(width:f64)->UsedSizeTree {
        UsedSizeTree {generation:17,
            content:vec![("root".into(),Constraints{
                width:AxisConstraint{value:Some(width),definite:true},
                height:AxisConstraint{value:Some(60.0),definite:true},
            })],deferred:vec![],
        }
    }
    let (case,_) = common::fixture("A07");
    let maximum = case["expected"]["max_iterations"].as_u64().unwrap() as usize;
    let state=begin_convergence(tree(100.0),maximum).unwrap();
    let (_,state)=advance_convergence(state,tree(120.0)).unwrap();
    assert!(advance_convergence(state,tree(100.0)).is_err(),
        "A07 must reject A -> B -> A oscillation without commit");
}
