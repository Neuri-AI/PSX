//! F2.2.3 CSS justify-content main-axis distribution for already-sized flex items.
//! Auto margins must be consumed upstream; this module only computes spacing.

use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum JustifyContent {
    FlexStart, FlexEnd, Center, SpaceBetween, SpaceAround, SpaceEvenly,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct MainAlignment {
    pub leading_space: f64,
    pub between_space: f64,
    pub remaining_free_space: f64,
}

pub fn resolve_main_alignment(
    justify: JustifyContent,
    available_main: f64,
    outer_sizes: &[f64],
    gap: f64,
) -> Result<MainAlignment, FlexMathError> {
    if !available_main.is_finite() || available_main < 0.0
        || !gap.is_finite() || gap < 0.0
        || outer_sizes.iter().any(|size| !size.is_finite())
    {
        return Err(FlexMathError::InvalidInput("invalid resolved main alignment input"));
    }
    let count = outer_sizes.len();
    let free = available_main - outer_sizes.iter().sum::<f64>()
        - gap * count.saturating_sub(1) as f64;
    if count == 0 {
        return Ok(MainAlignment {
            leading_space: 0.0, between_space: gap, remaining_free_space: free,
        });
    }
    let (leading, extra) = match justify {
        JustifyContent::FlexStart => (0.0, 0.0),
        JustifyContent::FlexEnd => (free, 0.0),
        JustifyContent::Center => (free / 2.0, 0.0),
        JustifyContent::SpaceBetween => (
            0.0, if count > 1 { free.max(0.0) / (count - 1) as f64 } else { 0.0 },
        ),
        JustifyContent::SpaceAround => {
            if free < 0.0 { (0.0, 0.0) } else {
                let extra = free / count as f64;
                (extra / 2.0, extra)
            }
        }
        JustifyContent::SpaceEvenly => {
            if free < 0.0 { (0.0, 0.0) } else {
                let extra = free / (count + 1) as f64;
                (extra, extra)
            }
        }
    };
    Ok(MainAlignment {
        leading_space: leading,
        between_space: gap + extra,
        remaining_free_space: free,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn positive_free_space_variants() {
        let sizes = [20.0, 20.0];
        assert_eq!(resolve_main_alignment(
            JustifyContent::SpaceBetween, 100.0, &sizes, 10.0
        ).unwrap().between_space, 60.0);
        assert_eq!(resolve_main_alignment(
            JustifyContent::SpaceAround, 100.0, &sizes, 10.0
        ).unwrap().leading_space, 12.5);
        assert_eq!(resolve_main_alignment(
            JustifyContent::SpaceEvenly, 100.0, &sizes, 10.0
        ).unwrap().leading_space, 50.0 / 3.0);
    }

    #[test]
    fn unsafe_center_preserves_negative_overflow() {
        let alignment = resolve_main_alignment(
            JustifyContent::Center, 30.0, &[40.0], 0.0
        ).unwrap();
        assert_eq!(alignment.leading_space, -5.0);
    }

    #[test]
    fn distribution_modes_fallback_on_overflow() {
        for variant in [
            JustifyContent::SpaceBetween,
            JustifyContent::SpaceAround,
            JustifyContent::SpaceEvenly,
        ] {
            let value = resolve_main_alignment(
                variant, 30.0, &[40.0], 0.0
            ).unwrap();
            assert_eq!(value.leading_space, 0.0);
        }
    }

    #[test]
    fn signed_outer_contributions_are_allowed() {
        let value = resolve_main_alignment(
            JustifyContent::FlexEnd, 100.0, &[20.0, -10.0], 10.0
        ).unwrap();
        assert_eq!(value.leading_space, 90.0);
    }
}
