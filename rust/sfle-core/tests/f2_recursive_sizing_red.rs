//! Shared immutable vectors for recursive minima and per-line flex sizing.
use sfle_core::compute::{compute, LayoutInput};
use serde_json::{json, Value};

#[test]
fn recursive_minima_and_line_sizing() {
    let cases: Vec<Value> = serde_json::from_str(include_str!(
        "../../../tests/sfle/fixtures/f2_recursive_sizing.json"
    )).unwrap();
    for case in cases {
        let nodes: Vec<Value> = case["nodes"].as_array().unwrap().iter().map(|node| {
            let mut node = node.clone();
            node["component"] = json!("Flex");
            node
        }).collect();
        let unknown = json!({"value":null,"definite":false});
        let constraints = json!({"width":unknown,"height":unknown});
        let measurements: Vec<Value> = case["measurements"].as_array().map(|entries|
            entries.iter().map(|entry| json!({
                "node_id":entry["node_id"], "intrinsic":entry["intrinsic"],
                "constraints":constraints, "revision":0,
            })).collect()
        ).unwrap_or_default();
        let input: LayoutInput = serde_json::from_value(json!({
            "schema_version":1,"generation":23,
            "direction":case.get("direction").unwrap_or(&json!("ltr")),
            "constraints":constraints,"nodes":nodes,"measurements":measurements,
        })).unwrap();
        let result = compute(&input).unwrap_or_else(|error| panic!("{}: {:?}", case["id"], error));
        assert_eq!(result.generation, 23);
        assert_eq!(result.boxes.iter().map(|b| &b.node_id).collect::<Vec<_>>(),
                   input.nodes.iter().map(|n| &n.node_id).collect::<Vec<_>>());
        for (id, expected) in case["expected"].as_object().unwrap() {
            let rect = &result.boxes.iter().find(|b| b.node_id == *id).unwrap().content;
            for (axis, wanted) in expected.as_object().unwrap() {
                let actual = match axis.as_str() {
                    "x" => rect.x, "y" => rect.y, "width" => rect.width, "height" => rect.height,
                    _ => panic!("Invalid expected axis"),
                };
                assert_eq!(actual, wanted.as_f64().unwrap(), "{} {id}.{axis}", case["id"]);
            }
        }
    }
}
