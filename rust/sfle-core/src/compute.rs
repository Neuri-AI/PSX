//! Versioned Rust F2 computation input and output boundary.
//!
//! This is the production-facing contract, not a fixture-specific algorithm.
//! Unsupported semantics must fail explicitly until implemented.
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AvailableSize {
    pub value: Option<f64>,
    pub definite: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct LayoutConstraints {
    pub width: AvailableSize,
    pub height: AvailableSize,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct LayoutNode {
    pub node_id: String,
    pub parent_id: Option<String>,
    pub component: String,
    pub style: serde_json::Map<String,serde_json::Value>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct IntrinsicSizes {
    pub min_content_width: f64,
    pub max_content_width: f64,
    pub min_content_height: f64,
    pub max_content_height: f64,
    pub preferred_width: f64,
    pub preferred_height: f64,
    pub baseline: Option<f64>,
    pub orthogonal_baseline: Option<f64>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct MeasuredBox {
    pub node_id: String,
    pub intrinsic: IntrinsicSizes,
    pub constraints: LayoutConstraints,
    pub revision: u64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct LayoutInput {
    pub schema_version: u32,
    pub generation: u64,
    pub direction: String,
    pub constraints: LayoutConstraints,
    pub nodes: Vec<LayoutNode>,
    pub measurements: Vec<MeasuredBox>,
}
#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
pub struct Rect {
    pub x: f64, pub y: f64, pub width: f64, pub height: f64,
}
#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
pub struct LayoutBox {
    pub node_id: String,
    pub content: Rect,
    pub padding: Rect,
    pub border: Rect,
    pub margin: Rect,
}
#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
pub struct LayoutResult {
    pub schema_version: u32,
    pub generation: u64,
    pub boxes: Vec<LayoutBox>,
    pub diagnostics: Vec<String>,
    pub measurement_error: Option<f64>,
    pub engine_error: Option<f64>,
    pub geometry_commit_error: Option<f64>,
}
#[derive(Clone, Debug, PartialEq)]
pub struct ComputeError {
    pub code: &'static str,
    pub message: String,
    pub node_id: Option<String>,
}

fn validate_input(input: &LayoutInput) -> Result<(), ComputeError> {
    let invalid = |message: &str| ComputeError {
        code: "SFLE_INVALID_SNAPSHOT", message: message.to_string(), node_id: None,
    };
    if input.schema_version != 1 || !matches!(input.direction.as_str(),"ltr"|"rtl") {
        return Err(invalid("Invalid schema version or writing direction."));
    }
    let mut ids = HashSet::new();
    for (index,node) in input.nodes.iter().enumerate() {
        if node.node_id.is_empty() || !ids.insert(node.node_id.as_str()) {
            return Err(invalid("Duplicate or empty node IDs."));
        }
        if (index == 0 && node.parent_id.is_some()) ||
           (index > 0 && node.parent_id.as_deref().is_none_or(|p| !ids.contains(p))) {
            return Err(invalid("Expected a single parent-first tree."));
        }
    }
    Ok(())
}

fn is_flow_root(tag: &str) -> bool {
    matches!(tag, "div" | "span" | "p" | "h1" | "h2" | "h3" | "h4" |
                   "h5" | "h6" | "section" | "main" | "header" | "footer")
}

pub fn compute(input: &LayoutInput) -> Result<LayoutResult, ComputeError> {
    validate_input(input)?;
    if input.nodes.first().is_some_and(|node| is_flow_root(&node.component)) {
        return crate::flow_snapshot::compute(input);
    }
    crate::compute_layout::compute_normalized(input,false)
}

/// Reuse unchanged, definitely-sized subtrees while preserving full placement.
pub fn compute_incremental(
    input:&LayoutInput, previous:&LayoutInput, previous_result:&LayoutResult,
)->Result<LayoutResult,ComputeError>{
    validate_input(input)?;
    if input.nodes.first().is_some_and(|node| is_flow_root(&node.component)) {
        return crate::flow_snapshot::compute(input);
    }
    crate::compute_layout::compute_normalized_incremental(
        input,false,Some((previous,previous_result))
    )
}

/// Noncommittable provisional geometry for width-dependent text measurement.
pub fn compute_provisional(input:&LayoutInput)->Result<LayoutResult,ComputeError>{
    if input.nodes.first().is_some_and(|node| is_flow_root(&node.component)) {
        return crate::flow_snapshot::compute(input);
    }
    crate::compute_layout::compute_normalized(input,true)
}



#[cfg(test)]
mod incremental_sizing_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn independent_flex_sibling_matches_complete_layout() {
        let previous_json=json!({
            "schema_version":1,"generation":1,"direction":"ltr",
            "constraints":{
                "width":{"value":300.0,"definite":true},
                "height":{"value":100.0,"definite":true}
            },
            "nodes":[
                {"node_id":"root","parent_id":null,"component":"Flex",
                 "style":{"direction":"row","width":"300px","height":"100px"}},
                {"node_id":"left","parent_id":"root","component":"Flex",
                 "style":{"width":"40px","height":"25px","flex_shrink":0}},
                {"node_id":"left_leaf","parent_id":"left","component":"Flex",
                 "style":{"width":"20px","height":"10px"}},
                {"node_id":"right","parent_id":"root","component":"Flex",
                 "style":{"width":"50px","height":"25px","flex_shrink":0}},
                {"node_id":"right_leaf","parent_id":"right","component":"Flex",
                 "style":{"width":"20px","height":"10px"}}
            ],
            "measurements":[]
        });
        let previous:LayoutInput=serde_json::from_value(previous_json.clone()).unwrap();
        let previous_result=compute(&previous).unwrap();
        let mut next_json=previous_json;
        next_json["generation"]=json!(2);
        next_json["nodes"][1]["style"]["width"]=json!("60px");
        let next:LayoutInput=serde_json::from_value(next_json).unwrap();
        let complete=compute(&next).unwrap();
        let incremental=compute_incremental(&next,&previous,&previous_result).unwrap();
        assert_eq!(incremental.boxes,complete.boxes);
        assert_eq!(incremental.generation,2);
    }

    #[test]
    fn changed_viewport_falls_back_to_equivalent_geometry() {
        let initial:LayoutInput=serde_json::from_value(json!({
            "schema_version":1,"generation":1,"direction":"ltr",
            "constraints":{
                "width":{"value":100.0,"definite":true},
                "height":{"value":80.0,"definite":true}
            },
            "nodes":[{"node_id":"root","parent_id":null,"component":"Flex",
                      "style":{"direction":"row","width":"100px","height":"80px"}}],
            "measurements":[]
        })).unwrap();
        let result=compute(&initial).unwrap();
        let mut next:serde_json::Value=serde_json::to_value(&initial).unwrap();
        next["generation"]=json!(2);
        next["constraints"]["width"]["value"]=json!(300.0);
        let changed:LayoutInput=serde_json::from_value(next).unwrap();
        assert_eq!(compute_incremental(&changed,&initial,&result).unwrap().boxes,
                   compute(&changed).unwrap().boxes);
    }
}
