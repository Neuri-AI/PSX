//! Percentage flex-basis resolution with an explicit premeasured content fallback.
//! No cyclic measurement or aspect-ratio transfer is inferred.

use crate::intrinsic::{resolve_intrinsic_flex_basis, Basis, IntrinsicFlexInput};
use crate::sizing::AvailableSize;
use crate::FlexMathError;

pub fn resolve_percentage_flex_basis(
    fraction: f64,
    flex_main_size: AvailableSize,
    content: IntrinsicFlexInput,
) -> Result<f64, FlexMathError> {
    flex_main_size.validate()?;
    if !fraction.is_finite() || fraction < 0.0 {
        return Err(FlexMathError::InvalidInput("invalid percentage flex basis"));
    }
    if flex_main_size.definite {
        return Ok(flex_main_size.value.expect("validated definite dimension") * fraction);
    }
    resolve_intrinsic_flex_basis(IntrinsicFlexInput {
        flex_basis: Basis::Content,
        ..content
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::intrinsic::{IntrinsicSizes, MainAxis, OverflowMode};

    fn fixture() -> IntrinsicFlexInput {
        IntrinsicFlexInput {
            intrinsic: IntrinsicSizes {
                min_content_width: 30.0, max_content_width: 120.0,
                min_content_height: 10.0, max_content_height: 70.0,
                preferred_width: 100.0, preferred_height: 60.0,
            },
            axis: MainAxis::Horizontal,
            flex_basis: Basis::Auto,
            grow: 0.0,
            shrink: 1.0,
            preferred_main_size: Some(80.0),
            max_main_size: None,
            min_main_size: None,
            overflow: OverflowMode::Visible,
            scroll_container: false,
            has_aspect_ratio_transfer: false,
        }
    }

    #[test]
    fn definite_percent_uses_main_size() {
        assert_eq!(
            resolve_percentage_flex_basis(
                0.5, AvailableSize { value: Some(200.0), definite: true }, fixture(),
            ).unwrap(),
            100.0
        );
    }

    #[test]
    fn indefinite_main_size_uses_content_not_auto_preferred_size() {
        assert_eq!(
            resolve_percentage_flex_basis(
                0.0, AvailableSize { value: Some(200.0), definite: false }, fixture(),
            ).unwrap(),
            120.0
        );
    }

    #[test]
    fn column_uses_vertical_content() {
        let content = IntrinsicFlexInput { axis: MainAxis::Vertical, ..fixture() };
        assert_eq!(
            resolve_percentage_flex_basis(
                0.4, AvailableSize { value: None, definite: false }, content,
            ).unwrap(),
            70.0
        );
    }

    #[test]
    fn unsupported_aspect_transfer_fails_without_inventing_geometry() {
        let content = IntrinsicFlexInput {
            has_aspect_ratio_transfer: true, ..fixture()
        };
        assert!(resolve_percentage_flex_basis(
            0.5, AvailableSize { value: None, definite: false }, content
        ).is_err());
    }
}
