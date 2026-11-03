mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a03_normalized_rust_engine() {
    let (case, snapshot) = common::fixture("A03");
    let result = compute(&snapshot).expect("A03: Rust compute must support this fixture");
    assert_eq!(result.generation, snapshot.generation);
    assert_eq!(result.boxes.len(), snapshot.nodes.len());
    for node in ["root","inner"] {
        let actual=result.boxes.iter().find(|b|b.node_id==node).unwrap().content.height;
        let expected=case["expected"][format!("{node}.height")].as_f64().unwrap();
        assert!((actual-expected).abs()<=0.01,"{node}: {actual} vs {expected}");
    }
}
