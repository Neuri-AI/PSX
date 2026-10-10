//! Used CSS stretch cross-size for an explicitly auto-sized flex item.
use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct UsedCrossStretch {
    pub content_size: f64,
    pub border_size: f64,
}

pub fn resolve_cross_stretch(
    line_cross_size: f64,
    padding_border: f64,
    start_margin: f64,
    end_margin: f64,
    min_content_size: f64,
    max_content_size: Option<f64>,
) -> Result<UsedCrossStretch, FlexMathError> {
    let inputs = [line_cross_size, padding_border, start_margin, end_margin, min_content_size];
    if !inputs.iter().all(|n| n.is_finite()) || line_cross_size < 0.0
        || padding_border < 0.0 || min_content_size < 0.0
        || max_content_size.is_some_and(|n| !n.is_finite() || n < 0.0)
    {
        return Err(FlexMathError::InvalidInput("invalid cross stretch inputs"));
    }
    let maximum = max_content_size.map(|n| n.max(min_content_size));
    let mut content = (line_cross_size - padding_border - start_margin - end_margin)
        .max(0.0).max(min_content_size);
    if let Some(maximum) = maximum {
        content = content.min(maximum);
    }
    Ok(UsedCrossStretch { content_size: content, border_size: content + padding_border })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn auto_stretch_fills_line_but_preserves_edges() {
        let used = resolve_cross_stretch(100.0, 10.0, 5.0, 5.0, 0.0, None).unwrap();
        assert_eq!(used, UsedCrossStretch { content_size: 80.0, border_size: 90.0 });
    }
    #[test]
    fn clamps_definite_bounds() {
        let used = resolve_cross_stretch(100.0, 10.0, 0.0, 0.0, 0.0, Some(30.0)).unwrap();
        assert_eq!(used.border_size, 40.0);
    }
    #[test]
    fn minimum_wins_over_smaller_maximum() {
        let used = resolve_cross_stretch(10.0, 2.0, 0.0, 0.0, 20.0, Some(5.0)).unwrap();
        assert_eq!(used.content_size, 20.0);
    }
}
