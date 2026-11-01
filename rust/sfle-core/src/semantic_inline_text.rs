//! Deterministic 1/64 px inline line layout, independent of the Python engine.
//!
//! The renderer owns font shaping/measurement and the shared frontend supplies
//! source-addressed word and collapsed-space atoms. Both Rust and Python
//! kernels consume the *same* measured atom wire; no VNodes are produced here.
//!
//! This intentionally implements the bounded LTR / white-space:normal kernel,
//! not the complete CSS inline formatting model.
use crate::layout_unit::LayoutUnit;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize)]
pub struct InlineAtom {
    pub node_id: String,
    pub text: String,
    pub start: usize,
    pub end: usize,
    pub space: bool,
    pub width: f64,
    pub height: f64,
    pub baseline: f64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct InlineRequest {
    pub width: f64,
    pub text_align: String,
    pub atoms: Vec<InlineAtom>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct InlineFragment {
    pub node_id: String,
    pub text: String,
    pub start: usize,
    pub end: usize,
    pub line_index: usize,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
    pub baseline: f64,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct InlineResult {
    pub fragments: Vec<InlineFragment>,
    pub width: f64,
    pub height: f64,
    pub line_count: usize,
}

fn px(value: f64) -> Result<f64, String> {
    LayoutUnit::from_nearest(value)
        .map(LayoutUnit::to_px)
        .map_err(str::to_string)
}

pub fn layout_inline(request: &InlineRequest) -> Result<InlineResult, String> {
    if !request.width.is_finite() || request.width < 0.0 {
        return Err("Inline containing width must be finite and nonnegative.".into());
    }
    if !matches!(request.text_align.as_str(), "left" | "center" | "right") {
        return Err("Unsupported inline text alignment.".into());
    }
    for atom in &request.atoms {
        if atom.node_id.is_empty() || atom.start >= atom.end || atom.text.is_empty() {
            return Err("Inline atoms need source identity and positive offsets.".into());
        }
        if !atom.width.is_finite() || !atom.height.is_finite()
            || !atom.baseline.is_finite() || atom.width < 0.0
            || atom.height < 0.0 || atom.baseline < 0.0 || atom.baseline > atom.height
        {
            return Err("Invalid inline metrics.".into());
        }
        if atom.space && atom.text != " " {
            return Err("Whitespace atom must be one collapsed space.".into());
        }
    }

    let limit = px(request.width)?;
    let mut lines: Vec<Vec<InlineAtom>> = Vec::new();
    let mut line: Vec<InlineAtom> = Vec::new();
    let mut cursor: f64 = 0.0;
    let mut pending: Option<InlineAtom> = None;

    for atom in &request.atoms {
        if atom.space {
            // Shared tokenization already drops leading/trailing whitespace.
            // Keep the first pending gap if repeated whitespace is supplied.
            if pending.is_none() { pending = Some(atom.clone()); }
            continue;
        }

        let word_width = px(atom.width)?;
        let mut gap = if !line.is_empty() { pending.take() } else {
            pending = None;
            None
        };
        let mut gap_width = if let Some(ref g) = gap { px(g.width)? } else { 0.0 };

        // A span boundary without whitespace is not a break opportunity.
        if !line.is_empty() && gap.is_some()
            && px(cursor + gap_width + word_width)? > limit
        {
            lines.push(std::mem::take(&mut line));
            cursor = 0.0;
            gap = None;
            gap_width = 0.0;
        }

        if let Some(g) = gap {
            line.push(g);
            cursor = px(cursor + gap_width)?;
        }
        line.push(atom.clone());
        cursor = px(cursor + word_width)?;
    }
    if !line.is_empty() { lines.push(line); }

    let mut fragments = Vec::new();
    let mut y: f64 = 0.0;
    let mut widest: f64 = 0.0;
    for (line_index, atoms) in lines.iter().enumerate() {
        let ascent = atoms.iter().map(|a| px(a.baseline))
            .collect::<Result<Vec<_>, _>>()?
            .into_iter().fold(0.0f64, f64::max);
        let descent = atoms.iter().map(|a| px(a.height - a.baseline))
            .collect::<Result<Vec<_>, _>>()?
            .into_iter().fold(0.0f64, f64::max);
        let widths = atoms.iter().map(|a| px(a.width))
            .collect::<Result<Vec<_>, _>>()?;
        let used = px(widths.iter().sum::<f64>())?;
        widest = widest.max(used);
        let slack = (limit - used).max(0.0);
        let offset = px(match request.text_align.as_str() {
            "center" => slack * 0.5,
            "right" => slack,
            _ => 0.0,
        })?;
        let mut x = offset;
        for atom in atoms {
            fragments.push(InlineFragment {
                node_id: atom.node_id.clone(),
                text: atom.text.clone(),
                start: atom.start,
                end: atom.end,
                line_index,
                x,
                y: px(y + ascent - atom.baseline)?,
                width: px(atom.width)?,
                height: px(atom.height)?,
                baseline: px(atom.baseline)?,
            });
            x = px(x + atom.width)?;
        }
        y = px(y + ascent + descent)?;
    }

    Ok(InlineResult {
        fragments,
        width: widest,
        height: y,
        line_count: lines.len(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn atom(node: &str, value: &str, start: usize, space: bool, w: f64) -> InlineAtom {
        InlineAtom {
            node_id: node.to_owned(), text: value.to_owned(),
            start, end: start + value.len(), space,
            width: w, height: 20.0, baseline: 15.0,
        }
    }
    #[test]
    fn wraps_on_space_not_span_boundary() {
        let input = InlineRequest {
            width: 90.0, text_align: "left".into(),
            atoms: vec![
                atom("a", "Edit", 0, false, 40.0),
                atom("a", " ", 4, true, 10.0),
                atom("span", "main.py", 0, false, 70.0),
                atom("post", " ", 0, true, 10.0),
                atom("post", "and", 1, false, 30.0),
            ],
        };
        let out = layout_inline(&input).unwrap();
        assert_eq!(out.line_count, 3);
        assert_eq!(out.fragments.iter().filter(|f| f.text == " ").count(), 0);
        assert_eq!(out.fragments[0].x, 0.0);
        assert_eq!(out.fragments[1].line_index, 1);
        assert_eq!(out.fragments[2].line_index, 2);
        assert_eq!(out.height, 60.0);
    }
    #[test]
    fn does_not_break_at_unspaced_run_boundary() {
        let result = layout_inline(&InlineRequest {
            width: 35.0, text_align: "left".into(),
            atoms: vec![atom("a", "hel", 0, false, 30.0),
                        atom("b", "lo", 0, false, 20.0)],
        }).unwrap();
        assert_eq!(result.line_count, 1);
        assert_eq!(result.width, 50.0);
    }
    #[test]
    fn centers_with_fixed_point_half_away_from_zero() {
        let out = layout_inline(&InlineRequest {
            width: 100.0, text_align: "center".into(),
            atoms: vec![atom("a", "Hi", 0, false, 50.0)],
        }).unwrap();
        assert_eq!(out.fragments[0].x, 25.0);
    }
    #[test]
    fn rejects_nonfinite_inputs() {
        let invalid = InlineRequest {
            width: f64::NAN, text_align: "left".into(), atoms: vec![],
        };
        assert!(layout_inline(&invalid).is_err());
    }
}
