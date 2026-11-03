mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_a01_full_tree_60px_parent_height() {
    let (case,snapshot) = common::fixture("A01");
    let layout = compute(&snapshot).expect("A01 must compute rather than reject supported orthogonal auto");
    assert_eq!(layout.boxes.len(), case["nodes"].as_array().unwrap().len());
    for name in ["root","column","text"] {
        let actual = layout.boxes.iter().find(|b|b.node_id==name).unwrap().content.height;
        let expected=case["expected"][format!("{name}.height")].as_f64().unwrap();
        assert!((actual-expected).abs()<=0.01,"{name}: {actual} vs {expected}");
    }
}
