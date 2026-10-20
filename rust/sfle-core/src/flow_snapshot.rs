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
    containing_width: Vec<f64>,
}
fn valid_flow_style(name: &str) -> bool {
    matches!(name,
        "display" | "layout_width" | "layout_height"
        | "layout_min_width" | "layout_min_height"
        | "layout_max_width" | "layout_max_height"
    ) || ["layout_margin_", "layout_padding_", "layout_border_"]
        .iter().any(|prefix| {
            name.strip_prefix(prefix).is_some_and(|side|
                matches!(side, "top" | "right" | "bottom" | "left"))
        })
}

impl Flow<'_> {
    fn dimension(&self, index: usize, axis: &str, available: f64) -> Result<Option<f64>, ComputeError> {
        let node = &self.input.nodes[index];
        let key = format!("layout_{axis}");
        let Some(value) = node.style.get(&key) else { return Ok(None); };
        let (kind, raw): (&str, Option<f64>) = if let Some(obj) = value.as_object() {
            (obj.get("kind").and_then(|v| v.as_str()).unwrap_or("invalid"),
             obj.get("value").and_then(|v| v.as_f64()))
        } else if let Some(number) = value.as_f64() {
            ("px", Some(number))
        } else if let Some(text) = value.as_str() {
            if matches!(text, "auto" | "none") {
                return Ok(None);
            }
            if let Some(number) = text.strip_suffix("px").and_then(|s| s.parse::<f64>().ok()) {
                ("px", Some(number))
            } else if let Some(number) = text.strip_suffix('%').and_then(|s| s.parse::<f64>().ok()) {
                ("percent", Some(number / 100.0))
            } else {
                ("invalid", None)
            }
        } else {
            ("invalid", None)
        };
        match (kind, raw) {
            ("px", Some(v)) if v.is_finite() => Ok(Some(v.max(0.0))),
            ("percent", Some(v)) if v.is_finite() => Ok(Some((v * available).max(0.0))),
            ("auto" | "none", _) => Ok(None),
            _ => Err(unsupported(format!("Unsupported flow {axis} dimension."), &node.node_id)),
        }
    }
    fn constrained_dimension(
        &self, index: usize, axis: &str, available: f64, fallback: f64,
    ) -> Result<f64, ComputeError> {
        let mut result = self.dimension(index, axis, available)?.unwrap_or(fallback);
        if let Some(maximum) = self.dimension(index, &format!("max_{axis}"), available)? {
            result = result.min(maximum);
        }
        if let Some(minimum) = self.dimension(index, &format!("min_{axis}"), available)? {
            result = result.max(minimum);
        }
        Ok(result.max(0.0))
    }
    fn edge(&self, index: usize, group: &str, side: &str, available: f64) -> Result<f64, ComputeError> {
        let node = &self.input.nodes[index];
        let name = format!("layout_{group}_{side}");
        let Some(value) = node.style.get(&name) else { return Ok(0.0); };
        let (kind, raw): (&str, Option<f64>) = if let Some(obj) = value.as_object() {
            (obj.get("kind").and_then(|v| v.as_str()).unwrap_or("invalid"),
             obj.get("value").and_then(|v| v.as_f64()))
        } else if let Some(number) = value.as_f64() {
            ("px", Some(number))
        } else if let Some(text) = value.as_str() {
            if let Some(n) = text.strip_suffix("px").and_then(|s| s.parse::<f64>().ok()) {
                ("px", Some(n))
            } else if let Some(n) = text.strip_suffix('%').and_then(|s| s.parse::<f64>().ok()) {
                ("percent", Some(n / 100.0))
            } else {
                ("invalid", None)
            }
        } else {
            ("invalid", None)
        };
        let resolved = match (kind, raw) {
            ("px", Some(n)) if n.is_finite() => n,
            ("percent", Some(n)) if n.is_finite() => n * available,
            _ => return Err(unsupported(format!("Unsupported flow {group} edge keyword."), &node.node_id)),
        };
        if group != "margin" && resolved < 0.0 {
            return Err(unsupported(format!("Flow {group} edges cannot be negative."), &node.node_id));
        }
        Ok(resolved)
    }

    fn box_rect(&self, index: usize, content: Rect, available: f64) -> Result<LayoutBox, ComputeError> {
        let id = &self.input.nodes[index].node_id;
        let expand = |inner: &Rect, group: &str| -> Result<Rect, ComputeError> {
            let top = self.edge(index, group, "top", available)?;
            let right = self.edge(index, group, "right", available)?;
            let bottom = self.edge(index, group, "bottom", available)?;
            let left = self.edge(index, group, "left", available)?;
            rect(inner.x - left, inner.y - top,
                 (inner.width + left + right).max(0.0),
                 (inner.height + top + bottom).max(0.0), id)
        };
        let padding = expand(&content, "padding")?;
        let border = expand(&padding, "border")?;
        let margin = expand(&border, "margin")?;
        Ok(LayoutBox {
            node_id: id.clone(), content, padding, border, margin,
        })
    }
    fn display(&self, index: usize) -> Result<Option<bool>, ComputeError> {
        let node = &self.input.nodes[index];
        if !formatting_tag(&node.component) {
            return Ok(None);
        }
        if node.style.keys().any(|name| !valid_flow_style(name)) {
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
        if node.style.keys().any(|name| !valid_flow_style(name)) {
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
        &mut self,
        index: usize, available: f64,
        atoms: &mut Vec<InlineAtom>,
        leaves: &mut Vec<usize>,
        owners: &mut Vec<usize>,
    ) -> Result<(), ComputeError> {
        self.containing_width[index] = available;
        match self.display(index)? {
            None => {
                let native = self.leaf(index)?;
                let mut horizontal = 0.0;
                let mut vertical = 0.0;
                let mut top = 0.0;
                for group in ["margin", "border", "padding"] {
                    horizontal += self.edge(index, group, "left", available)?
                        + self.edge(index, group, "right", available)?;
                    let edge_top = self.edge(index, group, "top", available)?;
                    top += edge_top;
                    vertical += edge_top + self.edge(index, group, "bottom", available)?;
                }
                atoms.push(InlineAtom {
                    width: self.constrained_dimension(index, "width", available, native.preferred_width)? + horizontal,
                    height: self.constrained_dimension(index, "height", available, native.preferred_height)? + vertical,
                    baseline: native.baseline.unwrap_or(native.preferred_height) + top,
                });
                leaves.push(index);
            }
            Some(true) => {
                owners.push(index);
                for child in self.children[index].clone() {
                    self.collect_inline(child, available, atoms, leaves, owners)?;
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
            self.collect_inline(index, available, &mut atoms, &mut leaves, &mut owners)?;
        }
        let placements = layout_inline_atoms(available, &atoms).map_err(|reason| {
            error("SFLE_INVALID_LENGTH", reason, None)
        })?;
        let mut line_height = 0.0_f64;
        for (index, placed) in leaves.into_iter().zip(placements.iter()) {
            let id = &self.input.nodes[index].node_id;
            let available = self.containing_width[index];
            let mut offset_x = 0.0;
            let mut offset_y = 0.0;
            let mut horizontal = 0.0;
            let mut vertical = 0.0;
            for group in ["margin", "border", "padding"] {
                let left = self.edge(index, group, "left", available)?;
                let right = self.edge(index, group, "right", available)?;
                let top = self.edge(index, group, "top", available)?;
                let bottom = self.edge(index, group, "bottom", available)?;
                offset_x += left;
                offset_y += top;
                horizontal += left + right;
                vertical += top + bottom;
            }
            self.boxes[index] = Some(rect(
                x + placed.x + offset_x, y + placed.y + offset_y,
                (placed.width - horizontal).max(0.0),
                (placed.height - vertical).max(0.0), id,
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
        self.containing_width[index] = available;
        let id = self.input.nodes[index].node_id.clone();
        let mut top = 0.0;
        let mut left = 0.0;
        let mut bottom = 0.0;
        let mut horizontal = 0.0;
        for group in ["margin", "padding", "border"] {
            top += self.edge(index, group, "top", available)?;
            left += self.edge(index, group, "left", available)?;
            bottom += self.edge(index, group, "bottom", available)?;
            horizontal += self.edge(index, group, "left", available)?
                + self.edge(index, group, "right", available)?;
        }
        let content_available = (available - horizontal).max(0.0);
        let content_x = x + left;
        let content_y = y + top;
        match self.display(index)? {
            None => {
                let preferred_height = self.leaf(index)?.preferred_height;
                let used_width = self.constrained_dimension(index, "width", available, content_available)?;
                let used_height = self.constrained_dimension(index, "height", available, preferred_height)?;
                self.boxes[index] = Some(rect(content_x, content_y, used_width, used_height, &id)?);
                return Ok(top + used_height + bottom);
            }
            Some(true) => {
                for group in ["margin", "padding", "border"] {
                    for side in ["top", "right", "bottom", "left"] {
                        if self.edge(index, group, side, available)? != 0.0 {
                            return Err(unsupported(
                                "Inline formatting owners with box edges require fragment-aware layout.",
                                &id,
                            ));
                        }
                    }
                }
                return self.inline_run(&[index], x, y, available);
            }
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
                    cursor += self.inline_run(&pending, content_x, content_y + cursor, content_available)?;
                    pending.clear();
                }
                cursor += self.block(child, content_x, content_y + cursor, content_available)?;
            }
        }
        if !pending.is_empty() {
            cursor += self.inline_run(&pending, content_x, content_y + cursor, content_available)?;
        }
        let used_width = self.constrained_dimension(index, "width", available, content_available)?;
        let used_height = self.constrained_dimension(index, "height", available, cursor)?;
        self.boxes[index] = Some(rect(content_x, content_y, used_width, used_height, &id)?);
        Ok(top + used_height + bottom)
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
    let mut flow = Flow { input, children, measurements, boxes: vec![None; input.nodes.len()], containing_width: vec![width; input.nodes.len()] };
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
    let mut has_root_edges = false;
    let mut vertical = 0.0;
    for group in ["margin", "padding", "border"] {
        for side in ["top", "right", "bottom", "left"] {
            let edge = flow.edge(0, group, side, width)?;
            has_root_edges |= edge != 0.0;
            if matches!(side, "top" | "bottom") {
                vertical += edge;
            }
        }
    }
    if has_root_edges {
        if input.constraints.height.definite && flow.dimension(0, "height", height)?.is_none() {
            let mut content = flow.boxes[0].clone().ok_or_else(|| {
                error("SFLE_INVALID_TREE", "Missing root content geometry.", Some(&root.node_id))
            })?;
            content.height = flow.constrained_dimension(0, "height", height, (height - vertical).max(0.0))?;
            flow.boxes[0] = Some(rect(content.x, content.y, content.width, content.height, &root.node_id)?);
        }
    } else {
        let root_width = flow.constrained_dimension(0, "width", width, width)?;
        let root_height = flow.constrained_dimension(0, "height", height, height)?;
        flow.boxes[0] = Some(rect(0.0, 0.0, root_width, root_height, &root.node_id)?);
    }
    let boxes = input.nodes.iter().enumerate().map(|(index, node)| {
        let calculated = flow.boxes[index].clone().ok_or_else(|| {
            error("SFLE_INVALID_TREE", "Flow node has no computed geometry.", Some(&node.node_id))
        })?;
        flow.box_rect(index, calculated, flow.containing_width[index])
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
