//! Resolved cross-axis Flexbox margins, no native measurement/alignment.

use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CrossMarginPosition {
    pub border_start: f64,
    pub used_start_margin: f64,
    pub used_end_margin: f64,
}

pub fn position_cross_margins(
    border_cross_size: f64,
    line_cross_size: f64,
    start: Option<f64>,
    end: Option<f64>,
    cross_forward: bool,
) -> Result<CrossMarginPosition, FlexMathError> {
    if !border_cross_size.is_finite() || !line_cross_size.is_finite()
        || border_cross_size < 0.0 || line_cross_size < 0.0
        || start.is_some_and(|v| !v.is_finite())
        || end.is_some_and(|v| !v.is_finite())
    {
        return Err(FlexMathError::InvalidInput("invalid resolved cross margins"));
    }
    let start_fixed = start.unwrap_or(0.0);
    let end_fixed = end.unwrap_or(0.0);
    let free = line_cross_size - border_cross_size - start_fixed - end_fixed;
    let auto_count = usize::from(start.is_none()) + usize::from(end.is_none());

    let (used_start, used_end) = if auto_count > 0 && free > 0.0 {
        let share = free / auto_count as f64;
        (start.unwrap_or(share), end.unwrap_or(share))
    } else if auto_count > 0 {
        let used_start = start.unwrap_or(0.0);
        (used_start, end.unwrap_or(line_cross_size - border_cross_size - used_start))
    } else {
        (start_fixed, end_fixed)
    };

    Ok(CrossMarginPosition {
        border_start: if cross_forward {
            used_start
        } else {
            line_cross_size - used_start - border_cross_size
        },
        used_start_margin: used_start,
        used_end_margin: used_end,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_auto_margins_center() {
        assert_eq!(position_cross_margins(20.0, 100.0, None, None, true).unwrap(),
            CrossMarginPosition { border_start: 40.0,
                used_start_margin: 40.0, used_end_margin: 40.0 });
    }

    #[test]
    fn overflow_auto_end_absorbs_negative_space() {
        let p = position_cross_margins(80.0, 50.0, None, None, true).unwrap();
        assert_eq!(p.used_start_margin, 0.0);
        assert_eq!(p.used_end_margin, -30.0);
        assert_eq!(p.border_start, 0.0);
    }

    #[test]
    fn reversed_cross_axis_positions_from_other_side() {
        let p = position_cross_margins(20.0, 100.0, Some(-5.0), Some(0.0), false).unwrap();
        assert_eq!(p.border_start, 85.0);
    }
}
