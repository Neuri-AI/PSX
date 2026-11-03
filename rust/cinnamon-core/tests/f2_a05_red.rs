mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a05_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A05");
    let result = compute(&snapshot).expect("A05: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    for key in ["a","b"] {
        let actual = result.boxes.iter().find(|b| b.node_id==key).unwrap().content.width;
        assert!((actual-case["expected"][format!("{key}.width")].as_f64().unwrap()).abs()<=0.01);
    }
}
