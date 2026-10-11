//! Typed CSS percentage constraints -> resolved content-box FlexBasis.

use crate::intrinsic::{
    Basis, IntrinsicFlexInput, MainAxis, resolve_automatic_main_minimum,
    resolve_intrinsic_flex_basis,
};
use crate::percentage_box_sizing::{normalize_flex_box_basis, BoxSizing};
use crate::percentage_flex_basis::resolve_percentage_flex_basis;
use crate::sizing::{
    resolve_length, AvailableSize, Length, Property, ResolvedLength,
};
use crate::{FlexBasis, FlexMathError};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PercentageFlexConstraints {
    pub basis: Length,
    pub minimum: Length,
    pub maximum: Length,
    pub containing_inline_size: AvailableSize,
    pub containing_main_axis_size: AvailableSize,
    pub flex_container_main_size: AvailableSize,
    pub padding_border: f64,
    pub sizing: BoxSizing,
    pub grow: f64,
    pub shrink: f64,
    pub intrinsic: Option<IntrinsicFlexInput>,
    pub horizontal: bool,
}

pub fn resolve_percentage_flex_constraints(
    request: PercentageFlexConstraints,
) -> Result<FlexBasis, FlexMathError> {
    let resolve = |length: Length, property: Property| {
        resolve_length(
            length, property, request.containing_inline_size,
            request.containing_main_axis_size, request.flex_container_main_size,
        )
    };
    let min_prop = if request.horizontal { Property::MinWidth } else { Property::MinHeight };
    let max_prop = if request.horizontal { Property::MaxWidth } else { Property::MaxHeight };

    let minimum = match resolve(request.minimum, min_prop)? {
        ResolvedLength::Used(value) => value,
        ResolvedLength::Auto | ResolvedLength::Intrinsic | ResolvedLength::UnresolvedPercent
            if request.intrinsic.is_some() =>
                resolve_automatic_main_minimum(request.intrinsic.expect("checked intrinsic"))?,
        _ => return Err(FlexMathError::InvalidInput("minimum needs measurement/dependency phase")),
    };
    let maximum = match resolve(request.maximum, max_prop)? {
        ResolvedLength::Used(value) => Some(value),
        ResolvedLength::None | ResolvedLength::UnresolvedPercent => None,
        ResolvedLength::Intrinsic if request.intrinsic.is_some() => {
            let intrinsic=request.intrinsic.expect("checked intrinsic");
            let min=matches!(request.maximum,Length::MinContent);
            Some(match (intrinsic.axis,min) {
                (MainAxis::Horizontal,true)=>intrinsic.intrinsic.min_content_width,
                (MainAxis::Horizontal,false)=>intrinsic.intrinsic.max_content_width,
                (MainAxis::Vertical,true)=>intrinsic.intrinsic.min_content_height,
                (MainAxis::Vertical,false)=>intrinsic.intrinsic.max_content_height,
            })
        },
        _ => return Err(FlexMathError::InvalidInput("maximum needs measurement/dependency phase")),
    };
    let basis = match resolve(request.basis, Property::FlexBasis)? {
        ResolvedLength::Used(value) => value,
        ResolvedLength::UnresolvedPercent => match (request.basis, request.intrinsic) {
            (Length::Percent(fraction), Some(intrinsic)) =>
                resolve_percentage_flex_basis(
                    fraction, request.flex_container_main_size, intrinsic
                )?,
            _ => return Err(FlexMathError::InvalidInput("flex basis needs intrinsic measurement")),
        },
        ResolvedLength::Auto | ResolvedLength::Intrinsic if request.intrinsic.is_some() => {
            let mut intrinsic=request.intrinsic.expect("checked intrinsic");
            intrinsic.flex_basis=match request.basis {
                Length::Auto=>Basis::Auto,
                Length::MinContent=>Basis::MinContent,
                Length::MaxContent=>Basis::MaxContent,
                Length::Content=>Basis::Content,
                _=>return Err(FlexMathError::InvalidInput("unsupported intrinsic flex basis")),
            };
            resolve_intrinsic_flex_basis(intrinsic)?
        },
        _ => return Err(FlexMathError::InvalidInput("flex basis needs measurement")),
    };
    normalize_flex_box_basis(
        basis, request.padding_border, request.sizing,
        minimum, maximum, request.grow, request.shrink,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> PercentageFlexConstraints {
        PercentageFlexConstraints {
            basis: Length::Percent(0.5),
            minimum: Length::Percent(0.25),
            maximum: Length::Percent(0.75),
            containing_inline_size: AvailableSize { value: Some(300.0), definite: true },
            containing_main_axis_size: AvailableSize { value: Some(200.0), definite: true },
            flex_container_main_size: AvailableSize { value: Some(200.0), definite: true },
            padding_border: 20.0, sizing: BoxSizing::BorderBox,
            grow: 1.0, shrink: 1.0, intrinsic: None, horizontal: true,
        }
    }

    #[test]
    fn definite_percent_constraints_resolve_to_content_box() {
        let b = resolve_percentage_flex_constraints(fixture()).unwrap();
        assert_eq!(b.basis, 80.0);
        assert_eq!(b.min_size, 30.0);
        assert_eq!(b.max_size, Some(130.0));
        assert_eq!(b.hypothetical, 80.0);
    }

    #[test]
    fn indefinite_minimum_is_not_silently_zero() {
        let mut req = fixture();
        req.containing_main_axis_size.definite = false;
        assert!(resolve_percentage_flex_constraints(req).is_err());
    }

    #[test]
    fn none_max_is_unbounded() {
        let mut req = fixture();
        req.maximum = Length::None;
        let b = resolve_percentage_flex_constraints(req).unwrap();
        assert_eq!(b.max_size, None);
    }

    #[test]
    fn unresolved_basis_requires_snapshot() {
        let mut req = fixture();
        req.flex_container_main_size.definite = false;
        assert!(resolve_percentage_flex_constraints(req).is_err());
    }
}
