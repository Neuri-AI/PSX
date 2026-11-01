//! Resolved cross-axis Flexbox margins, no native measurement/alignment.

use crate::FlexMathError;
use crate::layout_unit::LayoutUnit;

fn unit(value:f64)->f64 { LayoutUnit::from_nearest(value).expect("validated geometry").to_px() }
fn sub(value:f64, values:impl IntoIterator<Item=f64>)->f64 { values.into_iter().fold(LayoutUnit::from_nearest(value).expect("validated geometry"),|a,v|a-LayoutUnit::from_nearest(v).expect("validated geometry")).to_px() }

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
    let border_cross_size=unit(border_cross_size);
    let line_cross_size=unit(line_cross_size);
    let start_fixed = start.map(unit).unwrap_or(0.0);
    let end_fixed = end.map(unit).unwrap_or(0.0);
    let free = sub(line_cross_size,[border_cross_size,start_fixed,end_fixed]);
    let auto_count = usize::from(start.is_none()) + usize::from(end.is_none());

    let (used_start, used_end) = if auto_count > 0 && free > 0.0 {
        let share = unit(free / auto_count as f64);
        (if start.is_none() { share } else { start_fixed },
         if end.is_none() { share } else { end_fixed })
    } else if auto_count > 0 {
        let used_start = if start.is_none() { 0.0 } else { start_fixed };
        (used_start, if end.is_none() {
            sub(line_cross_size,[border_cross_size,used_start])
        } else { end_fixed })
    } else {
        (start_fixed, end_fixed)
    };

    Ok(CrossMarginPosition {
        border_start: if cross_forward {
            used_start
        } else {
            sub(line_cross_size,[used_start,border_cross_size])
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
    fn fixed_fractional_cross_margin_is_quantized_even_with_auto_opposite() {
        let m = position_cross_margins(
            24.0, 80.0, None, Some(3.993317968460473), true,
        ).unwrap();
        assert_eq!(m.used_start_margin, 52.0);
        assert_eq!(m.used_end_margin, 4.0);

        let n = position_cross_margins(
            24.0, 20.0, Some(3.993317968460473), None, true,
        ).unwrap();
        assert_eq!(n.used_start_margin, 4.0);
        assert_eq!(n.used_end_margin, -8.0);
    }

    #[test]
    fn reversed_cross_axis_positions_from_other_side() {
        let p = position_cross_margins(20.0, 100.0, Some(-5.0), Some(0.0), false).unwrap();
        assert_eq!(p.border_start, 85.0);
    }
}
