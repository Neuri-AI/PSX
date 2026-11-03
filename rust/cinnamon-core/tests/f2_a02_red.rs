mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a02_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A02");
    let result = compute(&snapshot).expect("A02: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    let actual = result.boxes.iter().find(|b| b.node_id=="root").unwrap().content.width;
    assert!((actual-case["expected"]["root.width"].as_f64().unwrap()).abs()<=0.01);
}
