//! Typed, property-aware sizing resolution mirroring Python SFLE sizing.
//! Unresolved percentages/auto/intrinsic values are retained, not approximated.

use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Length {
    Px(f64),
    Percent(f64),
    Auto,
    MinContent,
    MaxContent,
    FitContent,
    Content,
    None,
    Normal,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Property {
    Width, Height, FlexBasis, MinWidth, MinHeight, MaxWidth, MaxHeight,
    Margin, Padding, Gap, Border,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct AvailableSize {
    pub value: Option<f64>,
    pub definite: bool,
}

impl AvailableSize {
    pub fn validate(self) -> Result<(), FlexMathError> {
        if self.definite && self.value.is_none() {
            return Err(FlexMathError::InvalidInput("definite reference requires value"));
        }
        if let Some(v) = self.value {
            if !v.is_finite() || v < 0.0 {
                return Err(FlexMathError::InvalidInput("invalid available dimension"));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ResolvedLength {
    Used(f64),
    Auto,
    Intrinsic,
    UnresolvedPercent,
    None,
}

pub fn resolve_length(
    length: Length,
    property: Property,
    inline: AvailableSize,
    block_axis: AvailableSize,
    flex_main: AvailableSize,
) -> Result<ResolvedLength, FlexMathError> {
    inline.validate()?;
    block_axis.validate()?;
    flex_main.validate()?;
    use Length::*;
    use Property::*;
    match length {
        Px(v) => {
            if !v.is_finite() || (v < 0.0 && property != Margin) {
                return Err(FlexMathError::InvalidInput("invalid px length"));
            }
            Ok(ResolvedLength::Used(v))
        }
        Percent(v) => {
            if !v.is_finite() || (v < 0.0 && property != Margin) || property == Border {
                return Err(FlexMathError::InvalidInput("invalid percentage length"));
            }
            if property == Gap {
                return Err(FlexMathError::InvalidInput("percentage gap not implemented"));
            }
            let reference = match property {
                Margin | Padding => inline,
                FlexBasis => flex_main,
                _ => block_axis,
            };
            if reference.definite {
                Ok(ResolvedLength::Used(reference.value.unwrap() * v))
            } else {
                Ok(ResolvedLength::UnresolvedPercent)
            }
        }
        Auto if matches!(property, Width | Height | FlexBasis | MinWidth | MinHeight | Margin) =>
            Ok(ResolvedLength::Auto),
        None if matches!(property, MaxWidth | MaxHeight) => Ok(ResolvedLength::None),
        MinContent | MaxContent | FitContent | Content
            if matches!(property, Width | Height | FlexBasis | MinWidth | MinHeight | MaxWidth | MaxHeight) =>
            Ok(ResolvedLength::Intrinsic),
        _ => Err(FlexMathError::InvalidInput("unsupported keyword for CSS property")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn size(value: Option<f64>, definite: bool) -> AvailableSize {
        AvailableSize { value, definite }
    }

    #[test]
    fn margin_and_padding_percent_use_inline_reference() {
        let out = resolve_length(
            Length::Percent(0.1), Property::Padding, size(Some(200.0), true),
            size(Some(700.0), true), size(Some(300.0), true),
        ).unwrap();
        assert_eq!(out, ResolvedLength::Used(20.0));
        let margin = resolve_length(
            Length::Percent(-0.1), Property::Margin, size(Some(200.0), true),
            size(Some(700.0), true), size(Some(300.0), true),
        ).unwrap();
        assert_eq!(margin, ResolvedLength::Used(-20.0));
    }

    #[test]
    fn flex_basis_percent_uses_main_size_not_inline_size() {
        let out = resolve_length(
            Length::Percent(0.5), Property::FlexBasis, size(Some(200.0), true),
            size(Some(700.0), true), size(Some(300.0), true),
        ).unwrap();
        assert_eq!(out, ResolvedLength::Used(150.0));
    }

    #[test]
    fn indefinite_percent_is_not_zero() {
        let out = resolve_length(
            Length::Percent(0.5), Property::Width, size(Some(200.0), true),
            size(None, false), size(None, false),
        ).unwrap();
        assert_eq!(out, ResolvedLength::UnresolvedPercent);
    }

    #[test]
    fn unsupported_percentage_gap_fails() {
        assert!(resolve_length(
            Length::Percent(0.1), Property::Gap, size(Some(200.0), true),
            size(Some(200.0), true), size(Some(200.0), true),
        ).is_err());
    }
}
