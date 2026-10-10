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
