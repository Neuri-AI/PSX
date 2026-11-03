mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a06_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A06");
    let result = compute(&snapshot).expect("A06: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    assert_eq!(case["expected"]["commits_from_stale_generation"].as_u64().unwrap(),0);
    assert_eq!(result.generation, 17);
}
