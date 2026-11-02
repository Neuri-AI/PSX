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
    containing_height: Vec<Option<f64>>,
    resolved_block_margins: HashMap<usize, [f64; 4]>,
    // An offscreen text-only formatting context can reuse exact prior
    // boxes when its effective containing width and semantic inputs match.
    // Non-reusable contexts take the original full computation path.
    prior_boxes: Option<Vec<LayoutBox>>,
    reusable: Vec<bool>,
    viewport_height: Option<f64>,
    reused_contexts: Vec<String>,
}
fn valid_flow_style(name: &str) -> bool {
    matches!(name,
        "display" | "layout_width" | "layout_height"
        | "layout_min_width" | "layout_min_height"
        | "layout_max_width" | "layout_max_height"
    ) || ["layout_margin_", "layout_padding_", "layout_border_"]
        .iter().any(|prefix| {
            name.strip_prefix(*prefix).is_some_and(|side|
                matches!(side, "top" | "right" | "bottom" | "left"))
        })
}

impl Flow<'_> {
    fn replay_offscreen(
        &mut self, index:usize, content_x:f64, content_y:f64,
        content_width:f64,
    )->Result<bool,ComputeError>{
        let Some(height)=self.viewport_height else {return Ok(false)};
        if !self.reusable[index] {return Ok(false);}
        let Some(ref prior)=self.prior_boxes else {return Ok(false)};
        let old=&prior[index].content;
        // A changed viewport may still assign a *fixed-width* child the
        // exact same used content width. That child's descendants then have
        // identical wrapping geometry even though its parent changed width.
        // Any responsive child with changed effective width must run the
        // full solver, including when it is far outside the viewport.
        if (old.width-content_width).abs()>1.0/64.0 {
            return Ok(false);
        }
        if content_y <= height+96.0 && content_y+old.height>=-96.0 {
            return Ok(false);
        }
        // The entire subtree has unchanged styles, pure text measurements,
        // and no percent/viewport/auto-margin dependencies. Translate its
        // *previous* exact CSS geometry by the new parent placement.
        // Copies still undergo regular box-edge reconstruction, snapping
        // and complete native readback; no stale or partial LayoutResult.
        let dx=content_x-old.x;
        let dy=content_y-old.y;
        let mut todo=vec![index];
        while let Some(current)=todo.pop(){
            let original=&prior[current].content;
            self.boxes[current]=Some(rect(
                original.x+dx,original.y+dy,original.width,original.height,
                &self.input.nodes[current].node_id,
            )?);
            if current!=index {
                let parent_id=self.input.nodes[current].parent_id.as_ref().unwrap();
                let parent_index=self.input.nodes.iter()
                    .position(|n| &n.node_id==parent_id).unwrap_or(0);
                self.containing_width[current]=prior[parent_index].content.width;
            }
            for &child in &self.children[current] {
                todo.push(child);
            }
        }
        self.reused_contexts.push(self.input.nodes[index].node_id.clone());
        Ok(true)
    }

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
            if text.trim().parse::<f64>().ok().is_some_and(|n| n == 0.0) {
                ("px", Some(0.0))
            } else if let Some(number) = text.strip_suffix("px").and_then(|s| s.parse::<f64>().ok()) {
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
            ("percent", Some(v)) if v.is_finite() => Ok(
                (if axis.ends_with("height") { self.containing_height[index] } else { Some(available) })
                    .map(|reference| (v * reference).max(0.0))
            ),
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
            if group == "margin" && text == "auto" {
                ("auto", None)
            } else if text.trim().parse::<f64>().ok().is_some_and(|n| n == 0.0) {
                ("px", Some(0.0))
            } else if let Some(n) = text.strip_suffix("px").and_then(|s| s.parse::<f64>().ok()) {
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
            // Auto margins on native inline flow atoms consume no intrinsic
            // width. Block-level auto-margin distribution is handled by the
            // block layout path, not by this edge measurement.
            ("auto", None) if group == "margin" => 0.0,
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
            let [top, right, bottom, left] = if group == "margin" {
                self.resolved_block_margins.get(&index).copied().unwrap_or([
                    self.edge(index, group, "top", available)?,
                    self.edge(index, group, "right", available)?,
                    self.edge(index, group, "bottom", available)?,
                    self.edge(index, group, "left", available)?,
                ])
            } else {
                [self.edge(index, group, "top", available)?,
                 self.edge(index, group, "right", available)?,
                 self.edge(index, group, "bottom", available)?,
                 self.edge(index, group, "left", available)?]
            };
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

    /// Position descendants of an intrinsically measured native host in its
    /// content box. The native host retains its measured outer dimensions;
    /// descendants do not inflate a replaced element's intrinsic size.
    fn native_descendants(&mut self, index: usize) -> Result<(), ComputeError> {
        let Some(parent) = self.boxes[index].clone() else {
            return Err(error("SFLE_INVALID_TREE", "Native host has no geometry.", Some(&self.input.nodes[index].node_id)));
        };
        let mut cursor = 0.0;
        for child in self.children[index].clone() {
            self.containing_height[child] = Some(parent.height);
            if self.input.nodes[child].component == "Flex" {
                cursor += self.flex_node(child, parent.x, parent.y + cursor, parent.width)?;
            } else {
                cursor += self.block(child, parent.x, parent.y + cursor, parent.width)?;
            }
        }
        Ok(())
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
                    baseline: native.baseline.unwrap_or(native.preferred_height).max(0.0).min(self.constrained_dimension(index, "height", available, native.preferred_height)?) + top,
                });
                leaves.push(index);
            }
            Some(true) => {
                for group in ["margin", "border", "padding"] {
                    for side in ["top", "right", "bottom", "left"] {
                        if self.edge(index, group, side, available)? != 0.0 {
                            return Err(unsupported(
                                "Inline formatting owners with box edges require fragment-aware layout.",
                                &self.input.nodes[index].node_id,
                            ));
                        }
                    }
                }
                owners.push(index);
                for child in self.children[index].clone() {
                    self.containing_height[child] = self.containing_height[index];
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
            self.native_descendants(index)?;
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

    /// Solve an embedded Flex formatting context through the *native* Rust
    /// Flex solver. This is deliberately not the Python measured_block_snapshot
    /// compositor. Local node/measurement identity and ordering are preserved.
    fn flex_node(
        &mut self, index: usize, x: f64, y: f64, available: f64,
    ) -> Result<f64, ComputeError> {
        let mut indices = Vec::new();
        let mut stack = vec![index];
        while let Some(current) = stack.pop() {
            indices.push(current);
            for &child in self.children[current].iter().rev() {
                stack.push(child);
            }
        }
        let root = &self.input.nodes[index];
        let mut nodes = Vec::with_capacity(indices.len());
        for &original in &indices {
            let mut node = self.input.nodes[original].clone();
            if original == index {
                node.parent_id = None;
                if !node.style.contains_key("layout_width") &&
                   !node.style.contains_key("width") {
                    let mut horizontal = 0.0;
                    for group in ["padding", "border", "margin"] {
                        for side in ["left", "right"] {
                            horizontal += self.edge(index, group, side, available)?;
                        }
                    }
                    node.style.insert(
                        "layout_width".into(),
                        serde_json::Value::String(
                            format!("{}px", (available - horizontal).max(0.0))
                        ),
                    );
                }
            }
            nodes.push(node);
        }
        let ids: std::collections::HashSet<String> =
            nodes.iter().map(|node| node.node_id.clone()).collect();
        let local = crate::compute::LayoutInput {
            schema_version: self.input.schema_version,
            generation: self.input.generation,
            direction: self.input.direction.clone(),
            constraints: crate::compute::LayoutConstraints {
                width: crate::compute::AvailableSize {
                    value: Some(available), definite: true,
                },
                height: crate::compute::AvailableSize {
                    value: None, definite: false,
                },
            },
            nodes,
            measurements: self.input.measurements.iter()
                .filter(|item| ids.contains(item.node_id.as_str()))
                .cloned().collect(),
        };
        let solved = crate::compute_layout::compute_normalized(&local, false)?;
        let root_box = solved.boxes.iter()
            .find(|item| item.node_id == root.node_id)
            .ok_or_else(|| error(
                "SFLE_INVALID_TREE", "Native Flex root missing geometry.",
                Some(&root.node_id),
            ))?;
        let delta_x = x - root_box.border.x;
        let delta_y = y - root_box.border.y;
        let used_height = root_box.margin.height;
        for (original, geometry) in indices.into_iter().zip(solved.boxes.iter()) {
            let id = &self.input.nodes[original].node_id;
            self.containing_width[original] = available;
            self.boxes[original] = Some(rect(
                geometry.content.x + delta_x,
                geometry.content.y + delta_y,
                geometry.content.width,
                geometry.content.height,
                id,
            )?);
        }
        Ok(used_height)
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
        let parent_content_width = self.constrained_dimension(index, "width", available, content_available)?;
        let margin_auto = |side: &str| {
            let key = format!("layout_margin_{side}");
            let value = self.input.nodes[index].style.get(&key);
            value.is_some_and(|v| v.as_str() == Some("auto") ||
                v.as_object().is_some_and(|m| m.get("kind").and_then(|k| k.as_str()) == Some("auto")))
        };
        let auto_left = margin_auto("left");
        let auto_right = margin_auto("right");
        if auto_left || auto_right {
            let share = (content_available - parent_content_width).max(0.0)
                / f64::from(u8::from(auto_left) + u8::from(auto_right));
            let resolved_left = if auto_left { share } else { self.edge(index, "margin", "left", available)? };
            let resolved_right = if auto_right { share } else { self.edge(index, "margin", "right", available)? };
            self.resolved_block_margins.insert(index, [
                self.edge(index, "margin", "top", available)?, resolved_right,
                self.edge(index, "margin", "bottom", available)?, resolved_left,
            ]);
            if auto_left { left += share; }
        }
        let content_x = x + left;
        let content_y = y + top;
        // The root's viewport is only a *priority* hint. A node can be
        // deferred only with a complete previous layout proof, unchanged
        // containing width, and immutable descendant intrinsic metrics.
        // We still return all exact rectangles for native readback.
        if self.replay_offscreen(index, content_x, content_y, parent_content_width)? {
            let old = &self.prior_boxes.as_ref().unwrap()[index].content;
            return Ok(top + old.height + bottom);
        }
        let parent_height = self.dimension(index, "height", available)?;
        for child in self.children[index].clone() {
            self.containing_height[child] = parent_height;
        }
        match self.display(index)? {
            None => {
                let preferred_height = self.leaf(index)?.preferred_height;
                let used_width = self.constrained_dimension(index, "width", available, content_available)?;
                let used_height = self.constrained_dimension(index, "height", available, preferred_height)?;
                self.boxes[index] = Some(rect(content_x, content_y, used_width, used_height, &id)?);
                self.native_descendants(index)?;
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
            let child_component = self.input.nodes[child].component.as_str();
            if child_component == "Flex" {
                if !pending.is_empty() {
                    cursor += self.inline_run(
                        &pending, content_x, content_y + cursor, parent_content_width,
                    )?;
                    pending.clear();
                }
                cursor += self.flex_node(
                    child, content_x, content_y + cursor, parent_content_width,
                )?;
                continue;
            }
            if self.display(child)? == Some(true) ||
                (self.display(child)?.is_none() &&
                 !matches!(child_component, "Text" | "Grid" | "Native")) {
                pending.push(child);
            } else {
                if !pending.is_empty() {
                    cursor += self.inline_run(&pending, content_x, content_y + cursor, parent_content_width)?;
                    pending.clear();
                }
                if self.input.nodes[child].component == "Flex" {
                    cursor += self.flex_node(
                        child, content_x, content_y + cursor, parent_content_width,
                    )?;
                } else {
                    cursor += self.block(
                        child, content_x, content_y + cursor, parent_content_width,
                    )?;
                }
            }
        }
        if !pending.is_empty() {
            cursor += self.inline_run(&pending, content_x, content_y + cursor, parent_content_width)?;
        }
        let used_width = self.constrained_dimension(index, "width", available, content_available)?;
        let used_height = self.constrained_dimension(index, "height", available, cursor)?;
        self.boxes[index] = Some(rect(content_x, content_y, used_width, used_height, &id)?);
        Ok(top + used_height + bottom)
    }

}

/// Prove that a previous Block/Inline subtree has exactly the same
/// dependencies. A changed viewport is permitted, but any changed style,
/// intrinsic metric, percent value, interactive control, Scroll or inline
/// fragment fails closed to the regular full solve.
fn flow_reuse_plan(
    current:&LayoutInput,
    previous:Option<(&LayoutInput,&LayoutResult)>,
    children:&[Vec<usize>],
)->(Option<Vec<LayoutBox>>,Vec<bool>){
    let empty=vec![false;current.nodes.len()];
    let Some((old,prior))=previous else {return (None,empty)};
    if old.schema_version!=current.schema_version
        || old.generation!=prior.generation
        || old.direction!=current.direction
        || old.nodes.len()!=current.nodes.len()
        || prior.boxes.len()!=current.nodes.len()
        || !prior.diagnostics.is_empty()
        || prior.geometry_commit_error.is_some_and(|v|v!=0.0)
        || !current.constraints.height.definite
        || current.constraints.height.value.is_none()
    {return (None,empty);}
    let old_measured:HashMap<&str,&crate::compute::MeasuredBox>=old
        .measurements.iter().map(|m|(m.node_id.as_str(),m)).collect();
    let now_measured:HashMap<&str,&crate::compute::MeasuredBox>=current
        .measurements.iter().map(|m|(m.node_id.as_str(),m)).collect();
    let mut safe=vec![false;current.nodes.len()];
    for i in (0..current.nodes.len()).rev(){
        let node=&current.nodes[i];
        let prev=&old.nodes[i];
        if node.node_id!=prev.node_id || node.parent_id!=prev.parent_id
            || node.component!=prev.component || node.style!=prev.style
            || prior.boxes[i].node_id!=node.node_id {continue;}
        // Only normal-flow blocks with pure native Text leaves. Excluding
        // Scroll and Flex here prevents clipped/scrolled or interactive
        // descendants from being silently deferred.
        if !matches!(node.component.as_str(),
                     "div"|"p"|"section"|"main"|"header"|"footer"|
                     "form"|"ul"|"li"|"Text") {continue;}
        if node.component!="Text" && node.style.get("display")
            .and_then(|v|v.as_str()).is_some_and(|v|v!="block") {
            continue;
        }
        if node.style.iter().any(|(name,value)|{
            let raw=value.to_string().to_ascii_lowercase();
            raw.contains('%') || raw.contains("percent")
                || raw.contains("vw") || raw.contains("vh")
                || raw.contains("vmin") || raw.contains("vmax")
                || (name.starts_with("layout_margin_") && raw.contains("auto"))
        }) {continue;}
        let equivalent_measure=match (
            old_measured.get(node.node_id.as_str()),
            now_measured.get(node.node_id.as_str())
        ){
            (None,None)=>true,
            (Some(a),Some(b))=>a.node_id==b.node_id
                && serde_json::to_value(&a.intrinsic).ok()
                   ==serde_json::to_value(&b.intrinsic).ok()
                && serde_json::to_value(&a.constraints).ok()
                   ==serde_json::to_value(&b.constraints).ok(),
            _=>false,
        };
        safe[i]=equivalent_measure
            && children[i].iter().all(|&child|safe[child]);
    }
    (Some(prior.boxes.clone()),safe)
}

/// Generate CSS-like normal-flow geometry for the supported semantic tags.
/// All output identities and generations match the same v1 Cinnamon wire format.
pub fn compute(input: &LayoutInput) -> Result<LayoutResult, ComputeError> {
    compute_impl(input,None,None)
}

/// Native visibility-aware incremental solve. Only previously certified,
/// fully measured text-only Block contexts beyond the viewport overscan
/// may skip recursive sizing. All geometry is reconstructed exactly.
pub fn compute_incremental(
    input:&LayoutInput, previous:&LayoutInput, previous_result:&LayoutResult,
    report:&mut Vec<String>,
)->Result<LayoutResult,ComputeError>{
    compute_impl(input,Some((previous,previous_result)),Some(report))
}

fn compute_impl(
    input:&LayoutInput,
    previous:Option<(&LayoutInput,&LayoutResult)>,
    report:Option<&mut Vec<String>>,
)->Result<LayoutResult,ComputeError>{
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
    let (prior_boxes,reusable)=flow_reuse_plan(input,previous,&children);
    let mut flow = Flow {
        input, children, measurements,
        boxes: vec![None; input.nodes.len()],
        containing_width: vec![width; input.nodes.len()],
        containing_height: vec![
            if input.constraints.height.definite { input.constraints.height.value }
            else { None }; input.nodes.len()
        ],
        resolved_block_margins: HashMap::new(),
        prior_boxes, reusable,
        viewport_height:input.constraints.height.value
            .filter(|_|input.constraints.height.definite),
        reused_contexts:Vec::new(),
    };
    let content_height = if flow.display(0)? == Some(true) {
        let roots = flow.children[0].clone();
        flow.inline_run(&roots, 0.0, 0.0, width)?
    } else {
        flow.block(0, 0.0, 0.0, width)?
    };
    let height = content_height;
    let mut has_root_edges = false;
    for group in ["margin", "padding", "border"] {
        for side in ["top", "right", "bottom", "left"] {
            let edge = flow.edge(0, group, side, width)?;
            has_root_edges |= edge != 0.0;
        }
    }
    if !has_root_edges {
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
    if let Some(trace)=report {
        trace.extend(flow.reused_contexts.iter().cloned());
    }
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
