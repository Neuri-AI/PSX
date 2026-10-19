//! Closed normal-flow Block/Inline snapshot kernel.
//!
//! Pure geometry only: intrinsic metrics are furnished by the renderer on
//! its UI thread. CSS text shaping, floats, collapsing margins, CSS Grid,
//! native paint and external measurement remain outside this bounded grammar.
use std::collections::HashMap;

use crate::compute::{
    ComputeError, LayoutBox, LayoutInput, LayoutResult, Rect,
};
use crate::flow_layout::{layout_inline_atoms, InlineAtom};
use crate::layout_unit::LayoutUnit;

fn error(code: &'static str, message: impl Into<String>, id: Option<&str>) -> ComputeError {
    ComputeError { code, message: message.into(), node_id: id.map(str::to_owned) }
}
fn unsupported(message: impl Into<String>, id: &str) -> ComputeError {
    error("SFLE_UNSUPPORTED_FEATURE", message, Some(id))
}
fn px(value: f64, id: &str) -> Result<f64, ComputeError> {
    LayoutUnit::from_nearest(value).map(|n| n.to_px()).map_err(|reason| {
        error("SFLE_INVALID_LENGTH", reason, Some(id))
    })
}
fn rect(x: f64, y: f64, w: f64, h: f64, id: &str) -> Result<Rect, ComputeError> {
    Ok(Rect {
        x: px(x, id)?, y: px(y, id)?, width: px(w, id)?, height: px(h, id)?,
    })
}
fn formatting_tag(tag: &str) -> bool {
    matches!(tag,
        "div" | "span" | "p" | "h1" | "h2" | "h3" | "h4"
        | "h5" | "h6" | "section" | "main" | "header" | "footer" | "form" | "label" | "ul" | "li")
}
fn inline_default(tag: &str) -> bool {
    matches!(tag, "span" | "label")
}

struct Flow<'a> {
    input: &'a LayoutInput,
    children: Vec<Vec<usize>>,
    measurements: HashMap<&'a str, &'a crate::compute::IntrinsicSizes>,
    boxes: Vec<Option<Rect>>,
}
impl Flow<'_> {
    fn display(&self, index: usize) -> Result<Option<bool>, ComputeError> {
        let node = &self.input.nodes[index];
        if !formatting_tag(&node.component) {
            return Ok(None);
        }
        if node.style.keys().any(|name| name != "display") {
            return Err(unsupported(
                format!("{} requires a supported Block/Inline flow style.", node.component),
                &node.node_id,
            ));
        }
        let is_inline = match node.style.get("display").and_then(|item| item.as_str()) {
            None => inline_default(&node.component),
            Some("inline") => true,
            Some("block") => false,
            _ => return Err(unsupported("Unsupported flow display value.", &node.node_id)),
        };
        Ok(Some(is_inline))
    }

    fn leaf(&self, index: usize) -> Result<&crate::compute::IntrinsicSizes, ComputeError> {
        let node = &self.input.nodes[index];
        if !self.children[index].is_empty() {
            return Err(unsupported(
                format!("Nested Block/Inline formatting for native child {:?} requires an explicit nested format adapter.", node.node_id),
                &node.node_id,
            ));
        }
        if !node.style.is_empty() {
            return Err(unsupported("Native flow leaf has unresolved layout styles.", &node.node_id));
        }
        self.measurements.get(node.node_id.as_str()).copied().ok_or_else(|| {
            error(
                "SFLE_UNSUPPORTED_MEASUREMENT",
                format!("Native flow child {:?} is missing intrinsic measurements.", node.node_id),
                Some(&node.node_id),
            )
        })
    }

    fn collect_inline(
        &self,
        index: usize,
        atoms: &mut Vec<InlineAtom>,
        leaves: &mut Vec<usize>,
        owners: &mut Vec<usize>,
    ) -> Result<(), ComputeError> {
        match self.display(index)? {
            None => {
                let native = self.leaf(index)?;
                atoms.push(InlineAtom {
                    width: native.preferred_width,
                    height: native.preferred_height,
                    baseline: native.baseline.unwrap_or(native.preferred_height),
                });
                leaves.push(index);
            }
            Some(true) => {
                owners.push(index);
                for &child in &self.children[index] {
                    self.collect_inline(child, atoms, leaves, owners)?;
                }
            }
            Some(false) => {
                return Err(unsupported(
                    "Block children cannot participate inside an Inline formatting run.",
                    &self.input.nodes[index].node_id,
                ))
            }
        }
        Ok(())
    }

    fn inline_run(
        &mut self, nodes: &[usize], x: f64, y: f64, available: f64,
    ) -> Result<f64, ComputeError> {
        let mut atoms = Vec::new();
        let mut leaves = Vec::new();
        let mut owners = Vec::new();
        for &index in nodes {
            self.collect_inline(index, &mut atoms, &mut leaves, &mut owners)?;
        }
        let placements = layout_inline_atoms(available, &atoms).map_err(|reason| {
            error("SFLE_INVALID_LENGTH", reason, None)
        })?;
        let mut line_height = 0.0_f64;
        for (index, placed) in leaves.into_iter().zip(placements.iter()) {
            let id = &self.input.nodes[index].node_id;
            self.boxes[index] = Some(rect(
                x + placed.x, y + placed.y, placed.width, placed.height, id,
            )?);
            line_height = line_height.max(placed.y + placed.height);
        }
        for &owner in owners.iter().rev() {
            let children = &self.children[owner];
            let descendants: Vec<&Rect> = children.iter()
                .filter_map(|&child| self.boxes[child].as_ref())
                .collect();
            let id = &self.input.nodes[owner].node_id;
            if descendants.is_empty() {
                self.boxes[owner] = Some(rect(x, y, 0.0, 0.0, id)?);
                continue;
            }
            let left = descendants.iter().map(|item| item.x).fold(f64::INFINITY, f64::min);
            let top = descendants.iter().map(|item| item.y).fold(f64::INFINITY, f64::min);
            let right = descendants.iter().map(|item| item.x + item.width).fold(f64::NEG_INFINITY, f64::max);
            let bottom = descendants.iter().map(|item| item.y + item.height).fold(f64::NEG_INFINITY, f64::max);
            self.boxes[owner] = Some(rect(left, top, right - left, bottom - top, id)?);
        }
        Ok(line_height)
    }

    fn block(
        &mut self, index: usize, x: f64, y: f64, available: f64,
    ) -> Result<f64, ComputeError> {
        let id = self.input.nodes[index].node_id.clone();
        match self.display(index)? {
            None => {
                let preferred_height = self.leaf(index)?.preferred_height;
                self.boxes[index] = Some(rect(x, y, available, preferred_height, &id)?);
                return Ok(preferred_height);
            }
            Some(true) => return self.inline_run(&[index], x, y, available),
            Some(false) => (),
        }
        let mut cursor = 0.0;
        let mut pending = Vec::new();
        let children = self.children[index].clone();
        for child in children {
            if self.display(child)? == Some(true) {
                pending.push(child);
            } else {
                if !pending.is_empty() {
                    cursor += self.inline_run(&pending, x, y + cursor, available)?;
                    pending.clear();
                }
                cursor += self.block(child, x, y + cursor, available)?;
            }
        }
        if !pending.is_empty() {
            cursor += self.inline_run(&pending, x, y + cursor, available)?;
        }
        self.boxes[index] = Some(rect(x, y, available, cursor, &id)?);
        Ok(cursor)
    }
}

/// Generate CSS-like normal-flow geometry for the supported semantic tags.
/// All output identities and generations match the same v1 Cinnamon wire format.
pub fn compute(input: &LayoutInput) -> Result<LayoutResult, ComputeError> {
    let root = input.nodes.first().ok_or_else(|| {
        error("SFLE_INVALID_TREE", "Flow root is missing.", None)
    })?;
    if !formatting_tag(&root.component) {
        return Err(unsupported("Measured flow requires a semantic formatting root.", &root.node_id));
    }
    if root.parent_id.is_some() {
        return Err(error("SFLE_INVALID_TREE", "Flow root must have no parent.", Some(&root.node_id)));
    }
    let width = input.constraints.width.value.ok_or_else(|| {
        error("SFLE_LAYOUT_CONSTRAINT_ERROR", "Measured flow requires a definite width.", None)
    })?;
    if !input.constraints.width.definite {
        return Err(error("SFLE_LAYOUT_CONSTRAINT_ERROR", "Measured flow requires a definite width.", None));
    }
    let ids: HashMap<&str, usize> = input.nodes.iter().enumerate()
        .map(|(i, node)| (node.node_id.as_str(), i)).collect();
    let mut children = vec![Vec::new(); input.nodes.len()];
    for (index, node) in input.nodes.iter().enumerate().skip(1) {
        let parent = node.parent_id.as_ref().and_then(|id| ids.get(id.as_str())).ok_or_else(|| {
            error("SFLE_INVALID_TREE", "Missing flow parent.", Some(&node.node_id))
        })?;
        if *parent >= index {
            return Err(error("SFLE_INVALID_TREE", "Flow parent must precede child.", Some(&node.node_id)));
        }
        children[*parent].push(index);
    }
    let measurements = input.measurements.iter()
        .map(|item| (item.node_id.as_str(), &item.intrinsic)).collect();
    let mut flow = Flow { input, children, measurements, boxes: vec![None; input.nodes.len()] };
    let content_height = if flow.display(0)? == Some(true) {
        let roots = flow.children[0].clone();
        flow.inline_run(&roots, 0.0, 0.0, width)?
    } else {
        flow.block(0, 0.0, 0.0, width)?
    };
    let height = if input.constraints.height.definite {
        input.constraints.height.value.unwrap_or(content_height)
    } else {
        content_height
    };
    flow.boxes[0] = Some(rect(0.0, 0.0, width, height, &root.node_id)?);
    let boxes = input.nodes.iter().enumerate().map(|(index, node)| {
        let calculated = flow.boxes[index].clone().ok_or_else(|| {
            error("SFLE_INVALID_TREE", "Flow node has no computed geometry.", Some(&node.node_id))
        })?;
        Ok(LayoutBox {
            node_id: node.node_id.clone(),
            content: calculated.clone(),
            padding: calculated.clone(),
            border: calculated.clone(),
            margin: calculated,
        })
    }).collect::<Result<Vec<_>, ComputeError>>()?;
    Ok(LayoutResult {
        schema_version: input.schema_version,
        generation: input.generation,
        boxes,
        diagnostics: Vec::new(),
        measurement_error: None,
        engine_error: None,
        geometry_commit_error: None,
    })
}
