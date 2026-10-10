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
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Rect {
    pub x: f64, pub y: f64, pub width: f64, pub height: f64,
}
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct LayoutBox {
    pub node_id: String,
    pub content: Rect,
    pub padding: Rect,
    pub border: Rect,
    pub margin: Rect,
}
#[derive(Clone, Debug, PartialEq, Serialize)]
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

pub fn compute(input: &LayoutInput) -> Result<LayoutResult, ComputeError> {
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
    crate::compute_layout::compute_normalized(input,false)
}

/// Noncommittable provisional geometry for width-dependent text measurement.
pub fn compute_provisional(input:&LayoutInput)->Result<LayoutResult,ComputeError>{
    crate::compute_layout::compute_normalized(input,true)
}

