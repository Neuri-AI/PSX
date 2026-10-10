//! F2.2.1 immutable intrinsic content sizing; no native font/widget access.
//! Only non-replaced, no-aspect-ratio-transfer items are supported so far.

use crate::{FlexBasis, FlexMathError};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MainAxis { Horizontal, Vertical }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OverflowMode { Visible, Clip, Hidden, Auto, Scroll }
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Basis { Px(f64), Auto, MinContent, MaxContent, Content, Unsupported }

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct IntrinsicSizes {
    pub min_content_width: f64,
    pub max_content_width: f64,
    pub min_content_height: f64,
    pub max_content_height: f64,
    pub preferred_width: f64,
    pub preferred_height: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct IntrinsicFlexInput {
    pub intrinsic: IntrinsicSizes,
    pub axis: MainAxis,
    pub flex_basis: Basis,
    pub grow: f64,
    pub shrink: f64,
    pub preferred_main_size: Option<f64>,
    pub max_main_size: Option<f64>,
    pub min_main_size: Option<f64>,
    pub overflow: OverflowMode,
    pub scroll_container: bool,
    pub has_aspect_ratio_transfer: bool,
}

impl IntrinsicFlexInput {
    fn validate(self) -> Result<(), FlexMathError> {
        let i = self.intrinsic;
        let values = [
            i.min_content_width, i.max_content_width,
            i.min_content_height, i.max_content_height,
            i.preferred_width, i.preferred_height, self.grow, self.shrink,
        ];
        if !values.iter().all(|v| v.is_finite() && *v >= 0.0)
            || self.preferred_main_size.is_some_and(|v| !v.is_finite() || v < 0.0)
            || self.max_main_size.is_some_and(|v| !v.is_finite() || v < 0.0)
            || self.min_main_size.is_some_and(|v| !v.is_finite() || v < 0.0)
            || self.min_main_size.zip(self.max_main_size).is_some_and(|(min, max)| min > max)
        {
            return Err(FlexMathError::InvalidInput("invalid intrinsic sizing input"));
        }
        if (self.scroll_container && !matches!(self.overflow, OverflowMode::Auto | OverflowMode::Scroll))
            || (self.overflow == OverflowMode::Scroll && !self.scroll_container)
        {
            return Err(FlexMathError::InvalidInput("scroll-container state is inconsistent"));
        }
        Ok(())
    }

    fn metrics(self) -> (f64, f64) {
        match self.axis {
            MainAxis::Horizontal =>
                (self.intrinsic.min_content_width, self.intrinsic.max_content_width),
            MainAxis::Vertical =>
                (self.intrinsic.min_content_height, self.intrinsic.max_content_height),
        }
    }
}

pub fn resolve_intrinsic_flex_basis(req: IntrinsicFlexInput) -> Result<f64, FlexMathError> {
    req.validate()?;
    if req.has_aspect_ratio_transfer {
        return Err(FlexMathError::InvalidInput("aspect-ratio transfer not implemented"));
    }
    let (minimum, maximum) = req.metrics();
    match req.flex_basis {
        Basis::Px(value) if value.is_finite() && value >= 0.0 => Ok(value),
        Basis::MinContent => Ok(minimum),
        Basis::MaxContent | Basis::Content => Ok(maximum),
        Basis::Auto => Ok(req.preferred_main_size.unwrap_or(maximum)),
        _ => Err(FlexMathError::InvalidInput("unsupported intrinsic flex-basis")),
    }
}

pub fn resolve_automatic_main_minimum(req: IntrinsicFlexInput) -> Result<f64, FlexMathError> {
    req.validate()?;
    if let Some(minimum) = req.min_main_size { return Ok(minimum); }
    if req.scroll_container { return Ok(0.0); }
    if req.has_aspect_ratio_transfer {
        return Err(FlexMathError::InvalidInput("aspect-ratio transfer not implemented"));
    }
    let (min_content, _) = req.metrics();
    let with_suggestion = req.preferred_main_size.map_or(
        min_content, |suggestion| min_content.min(suggestion),
    );
    Ok(req.max_main_size.map_or(
        with_suggestion, |maximum| with_suggestion.min(maximum),
    ))
}

pub fn build_intrinsic_flex_basis(req: IntrinsicFlexInput) -> Result<FlexBasis, FlexMathError> {
    let basis = resolve_intrinsic_flex_basis(req)?;
    let mut minimum = resolve_automatic_main_minimum(req)?;
    if let Some(maximum) = req.max_main_size { minimum = minimum.min(maximum); }
    let mut hypothetical = basis.max(minimum);
    if let Some(maximum) = req.max_main_size { hypothetical = hypothetical.min(maximum); }
    let result = FlexBasis {
        basis, hypothetical, grow: req.grow, shrink: req.shrink,
        min_size: minimum, max_size: req.max_main_size,
    };
    result.validate()?;
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> IntrinsicFlexInput {
        IntrinsicFlexInput {
            intrinsic: IntrinsicSizes {
                min_content_width: 40.0, max_content_width: 130.0,
                min_content_height: 20.0, max_content_height: 70.0,
                preferred_width: 90.0, preferred_height: 40.0,
            },
            axis: MainAxis::Horizontal, flex_basis: Basis::Auto,
            grow: 1.0, shrink: 1.0, preferred_main_size: None,
            max_main_size: None, min_main_size: None,
            overflow: OverflowMode::Visible,
            scroll_container: false, has_aspect_ratio_transfer: false,
        }
    }

    #[test]
    fn auto_basis_uses_max_content_and_auto_min_uses_min_content() {
        let result = build_intrinsic_flex_basis(fixture()).unwrap();
        assert_eq!(result.basis, 130.0);
        assert_eq!(result.min_size, 40.0);
        assert_eq!(result.hypothetical, 130.0);
    }

    #[test]
    fn specified_size_caps_auto_minimum() {
        let mut req = fixture();
        req.preferred_main_size = Some(25.0);
        assert_eq!(resolve_automatic_main_minimum(req).unwrap(), 25.0);
        assert_eq!(resolve_intrinsic_flex_basis(req).unwrap(), 25.0);
    }

    #[test]
    fn scroll_container_auto_minimum_is_zero() {
        let mut req = fixture();
        req.overflow = OverflowMode::Scroll;
        req.scroll_container = true;
        assert_eq!(resolve_automatic_main_minimum(req).unwrap(), 0.0);
    }

    #[test]
    fn vertical_axis_uses_vertical_content_metrics() {
        let mut req = fixture();
        req.axis = MainAxis::Vertical;
        req.flex_basis = Basis::MinContent;
        assert_eq!(resolve_intrinsic_flex_basis(req).unwrap(), 20.0);
    }

    #[test]
    fn aspect_ratio_transfer_is_rejected() {
        let mut req = fixture();
        req.has_aspect_ratio_transfer = true;
        assert!(build_intrinsic_flex_basis(req).is_err());
    }
}
