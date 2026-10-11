//! Canonical fixtures consumed directly from the same JSON as Python/browser.
//! Parsing the shared corpus is a schema gate, not yet computational parity.
use serde_json::Value;
use std::collections::HashSet;

#[test]
fn f2_shared_acceptance_trees_have_preorder_identity() {
    let text = include_str!("../../../tests/sfle/fixtures/f2_alpha_acceptance.json");
    let corpus: Value = serde_json::from_str(text).expect("valid corpus JSON");
    assert_eq!(corpus["schema_version"], 1);
    let cases = corpus["cases"].as_array().expect("cases array");
    let expected: HashSet<&str> = [
        "A01", "A02", "A03", "A04", "A05", "A06", "A07",
        "C01", "C02", "C03", "C04", "C05", "C06", "C99",
        "A08", "A09-LTR", "A09-RTL", "A10", "N01", "N02", "N03", "N04",
    ].into_iter().collect();
    let mut seen_cases = HashSet::new();
    for case in cases {
        let id = case["id"].as_str().expect("case ID");
        assert!(seen_cases.insert(id), "duplicate case {id}");
        let mut seen_nodes = HashSet::new();
        for node in case["nodes"].as_array().expect("nodes") {
            let node_id = node["node_id"].as_str().expect("node ID");
            let parent = node["parent_id"].as_str();
            assert!(parent.is_none() || seen_nodes.contains(parent.unwrap()),
                "parent must precede node");
            assert!(seen_nodes.insert(node_id), "duplicate node {node_id}");
        }
        assert!(case["expected"].is_object());
    }
    assert_eq!(seen_cases, expected);
}
