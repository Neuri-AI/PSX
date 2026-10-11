//! F2.2.3 resolved cross alignment without stretch or baseline measurement.

use crate::FlexMathError;
use crate::layout_unit::LayoutUnit;

fn lu(value:f64)->LayoutUnit { LayoutUnit::from_nearest(value).expect("validated finite length") }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CrossAlign {
    Auto, FlexStart, FlexEnd, Center, Stretch, Baseline,
}

pub fn resolve_cross_alignment(
    align_items: CrossAlign,
    align_self: CrossAlign,
    border_cross_size: f64,
    line_cross_size: f64,
    fixed_start_margin: f64,
    fixed_end_margin: f64,
    cross_forward: bool,
) -> Result<f64, FlexMathError> {
    if align_items == CrossAlign::Auto {
        return Err(FlexMathError::InvalidInput("align-items cannot be auto"));
    }
    if ![border_cross_size, line_cross_size, fixed_start_margin, fixed_end_margin]
        .iter().all(|v| v.is_finite()) || border_cross_size < 0.0 || line_cross_size < 0.0
    {
        return Err(FlexMathError::InvalidInput("invalid resolved cross alignment"));
    }
    let chosen = if align_self == CrossAlign::Auto { align_items } else { align_self };
    let line=lu(line_cross_size); let border=lu(border_cross_size);
    let start=lu(fixed_start_margin); let end=lu(fixed_end_margin);
    let free = line - border - start - end;
    let logical = match chosen {
        CrossAlign::FlexStart => start,
        CrossAlign::FlexEnd => start + free,
        CrossAlign::Center => start + lu(free.to_px() / 2.0),
        CrossAlign::Stretch | CrossAlign::Baseline => {
            return Err(FlexMathError::InvalidInput(
                "stretch/baseline requires dedicated sizing/measurement",
            ));
        }
        CrossAlign::Auto => unreachable!("align-items auto was rejected"),
    };
    Ok(if cross_forward { logical } else { line - logical - border }.to_px())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn item_override_wins_over_container() {
        let x = resolve_cross_alignment(
            CrossAlign::FlexStart, CrossAlign::FlexEnd, 20.0, 100.0,
            0.0, 0.0, true,
        ).unwrap();
        assert_eq!(x, 80.0);
    }

    #[test]
    fn center_with_signed_margins_and_reverse_axis() {
        assert_eq!(resolve_cross_alignment(
            CrossAlign::Center, CrossAlign::Auto, 20.0, 100.0,
            -10.0, 0.0, false,
        ).unwrap(), 45.0);
    }

    #[test]
    fn overflow_end_is_not_silently_clamped() {
        assert_eq!(resolve_cross_alignment(
            CrossAlign::FlexEnd, CrossAlign::Auto, 80.0, 50.0,
            0.0, 0.0, true,
        ).unwrap(), -30.0);
    }

    #[test]
    fn stretching_is_gated() {
        assert!(resolve_cross_alignment(
            CrossAlign::Stretch, CrossAlign::Auto, 20.0, 100.0,
            0.0, 0.0, true,
        ).is_err());
    }
}
