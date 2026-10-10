mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a03_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A03");
    let result = compute(&snapshot).expect("A03: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    assert!(case["expected"]["diagnostic"].is_string());
    assert!(result.boxes[0].content.height.is_finite());
}
