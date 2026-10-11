mod common;
use sfle_core::compute::compute;

#[test]
fn f01_percent_basis_layout_unit_matches_chromium() {
    let (case, snapshot) = common::fixture("F01");
    let result = compute(&snapshot).expect("Rust must compute F01 without approximation");
    let box_ = result.boxes.iter().find(|b| b.node_id == "n1").unwrap();
    let expected = case["expected"]["n1.width"].as_f64().unwrap();
    assert!((box_.content.width - expected).abs() <= 0.01,
        "F01 Chromium expected {expected}, Rust computed {}", box_.content.width);
}

#[test]
fn f02_flex_remainder_and_position_match_chromium() {
    let (case, snapshot) = common::fixture("F02");
    let result = compute(&snapshot).expect("Rust must compute F02 without approximation");
    for (node, axis) in [("n1", "width"), ("n2", "x")] {
        let box_ = result.boxes.iter().find(|b| b.node_id == node).unwrap();
        let actual = if axis == "width" {box_.content.width} else {box_.content.x};
        let expected = case["expected"][format!("{node}.{axis}")].as_f64().unwrap();
        assert!((actual - expected).abs() <= 0.01,
            "F02 {node}.{axis} Chromium {expected}, Rust {actual}");
    }
}

#[test]
fn f04_f05_reverse_flex_remainder_matches_chromium() {
    for id in ["F04", "F05"] {
        let (case, snapshot) = common::fixture(id);
        let result = compute(&snapshot).expect("Rust pure geometry must produce F04/F05");
        for (key, value) in case["expected"].as_object().unwrap() {
            let (node, axis) = key.split_once('.').unwrap();
            let box_ = result.boxes.iter().find(|b| b.node_id == node).unwrap();
            let actual = if axis == "width" {box_.content.width} else {box_.content.x};
            let expected = value.as_f64().unwrap();
            assert!((actual - expected).abs() <= 0.01,
                "{id} {key}: Chromium {expected}, Rust {actual}");
        }
    }
}
