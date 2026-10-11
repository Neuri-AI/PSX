//! F2.2.2 explicit CSS cyclic intrinsic percentage gap and used box sizing.
//! Indefinite used-layout gaps are NOT silently coerced to intrinsic zero.

use crate::FlexMathError;
use crate::sizing::{AvailableSize, Length};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BoxSizing { ContentBox, BorderBox }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GapPhase { IntrinsicContribution, UsedLayout }

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct UsedBoxSize {
    pub content: f64,
    pub border_box: f64,
    pub padding_border: f64,
}

pub fn resolve_percentage_gap(
    length: Length,
    reference: AvailableSize,
    phase: GapPhase,
) -> Result<f64, FlexMathError> {
    reference.validate()?;
    match length {
        Length::Px(v) if v.is_finite() && v >= 0.0 => Ok(v),
        Length::Percent(v) if v.is_finite() && v >= 0.0 => {
            if reference.definite {
                Ok(v * reference.value.expect("validated definite reference"))
            } else if phase == GapPhase::IntrinsicContribution {
                Ok(0.0)
            } else {
                Err(FlexMathError::InvalidInput("indefinite used percentage gap"))
            }
        }
        _ => Err(FlexMathError::InvalidInput("invalid or unsupported gap length")),
    }
}

pub fn normalize_box_size(
    specified: f64,
    padding_border: f64,
    sizing: BoxSizing,
) -> Result<UsedBoxSize, FlexMathError> {
    if !specified.is_finite() || !padding_border.is_finite()
        || specified < 0.0 || padding_border < 0.0
    {
        return Err(FlexMathError::InvalidInput("invalid specified size or box edges"));
    }
    let content = match sizing {
        BoxSizing::ContentBox => specified,
        BoxSizing::BorderBox => (specified - padding_border).max(0.0),
    };
    Ok(UsedBoxSize {
        content,
        border_box: content + padding_border,
        padding_border,
    })
}


#[allow(clippy::too_many_arguments)]
pub fn normalize_flex_box_basis(
    basis: f64,
    padding_border: f64,
    sizing: BoxSizing,
    min_size: f64,
    max_size: Option<f64>,
    grow: f64,
    shrink: f64,
) -> Result<crate::FlexBasis, FlexMathError> {
    let used_basis = normalize_box_size(basis, padding_border, sizing)?.content;
    let used_minimum = normalize_box_size(min_size, padding_border, sizing)?.content;
    let mut used_maximum = match max_size {
        Some(value) => Some(normalize_box_size(value, padding_border, sizing)?.content),
        None => None,
    };
    if let Some(maximum) = used_maximum {
        if maximum < used_minimum {
            used_maximum = Some(used_minimum);
        }
    }
    let hypothetical = used_maximum.map_or(
        used_basis.max(used_minimum),
        |maximum| used_basis.max(used_minimum).min(maximum),
    );
    let result = crate::FlexBasis {
        basis: used_basis,
        hypothetical,
        grow,
        shrink,
        min_size: used_minimum,
        max_size: used_maximum,
    };
    result.validate()?;
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cyclic_gap_is_zero_only_during_intrinsic_contribution() {
        let reference = AvailableSize { value: None, definite: false };
        assert_eq!(resolve_percentage_gap(
            Length::Percent(0.1), reference, GapPhase::IntrinsicContribution
        ).unwrap(), 0.0);
        assert!(resolve_percentage_gap(
            Length::Percent(0.1), reference, GapPhase::UsedLayout
        ).is_err());
    }

    #[test]
    fn definite_percentage_gap_resolves_in_both_phases() {
        let reference = AvailableSize { value: Some(200.0), definite: true };
        assert_eq!(resolve_percentage_gap(
            Length::Percent(0.1), reference, GapPhase::UsedLayout
        ).unwrap(), 20.0);
    }

    #[test]
    fn border_box_cannot_be_smaller_than_fixed_edges() {
        assert_eq!(normalize_box_size(10.0, 20.0, BoxSizing::BorderBox).unwrap(),
            UsedBoxSize { content: 0.0, border_box: 20.0, padding_border: 20.0 });
        assert_eq!(normalize_box_size(10.0, 20.0, BoxSizing::ContentBox).unwrap(),
            UsedBoxSize { content: 10.0, border_box: 30.0, padding_border: 20.0 });
    }
    #[test]
    fn border_box_flex_min_max_are_converted_to_content_units() {
        let basis = normalize_flex_box_basis(
            100.0, 30.0, BoxSizing::BorderBox, 80.0, Some(90.0), 1.0, 1.0,
        ).unwrap();
        assert_eq!(basis.basis, 70.0);
        assert_eq!(basis.min_size, 50.0);
        assert_eq!(basis.max_size, Some(60.0));
        assert_eq!(basis.hypothetical, 60.0);
    }

    #[test]
    fn css_min_wins_when_definite_max_is_smaller() {
        let basis = normalize_flex_box_basis(
            100.0, 30.0, BoxSizing::BorderBox, 90.0, Some(50.0), 0.0, 1.0,
        ).unwrap();
        assert_eq!(basis.min_size, 60.0);
        assert_eq!(basis.max_size, Some(60.0));
        assert_eq!(basis.hypothetical, 60.0);
    }

    #[test]
    fn border_box_fixed_edges_are_an_implicit_floor() {
        let basis = normalize_flex_box_basis(
            10.0, 20.0, BoxSizing::BorderBox, 0.0, Some(10.0), 0.0, 1.0,
        ).unwrap();
        assert_eq!(basis.basis, 0.0);
        assert_eq!(basis.max_size, Some(0.0));
    }

}
