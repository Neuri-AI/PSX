//! F2.2.4 definite used-content preparation for recursive Flex children.
//! This step does not perform flex allocation or resolve auto/intrinsic cycles.

use crate::constraint_propagation::{resolve_child_constraints, ChildSizing};
use crate::measurement_plan::{AxisConstraint, Constraints};
use crate::percentage_box_sizing::{normalize_box_size, BoxSizing};
use crate::sizing::ResolvedLength;
use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct UsedContentResolution {
    pub content: Constraints,
    pub width_kind: ResolvedLength,
    pub height_kind: ResolvedLength,
}

pub fn resolve_used_content_size(
    parent_content: Constraints,
    sizing: ChildSizing,
    box_sizing: BoxSizing,
    horizontal_padding_border: f64,
    vertical_padding_border: f64,
) -> Result<UsedContentResolution, FlexMathError> {
    let specified = resolve_child_constraints(parent_content, sizing)?;

    let axis = |reference: AxisConstraint, edges: f64| -> Result<AxisConstraint, FlexMathError> {
        // Invalid edges must fail even if this axis cannot yet be resolved.
        normalize_box_size(0.0, edges, box_sizing)?;
        if !reference.definite {
            return Ok(AxisConstraint { value: None, definite: false });
        }
        let specified_value = reference.value.ok_or(
            FlexMathError::InvalidInput("definite specified axis lacks value")
        )?;
        let used = normalize_box_size(specified_value, edges, box_sizing)?;
        Ok(AxisConstraint { value: Some(used.content), definite: true })
    };

    Ok(UsedContentResolution {
        content: Constraints {
            width: axis(specified.constraints.width, horizontal_padding_border)?,
            height: axis(specified.constraints.height, vertical_padding_border)?,
        },
        width_kind: specified.width_kind,
        height_kind: specified.height_kind,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sizing::Length;

    fn definite(n: f64) -> AxisConstraint { AxisConstraint { value: Some(n), definite: true } }
    fn indefinite() -> AxisConstraint { AxisConstraint { value: None, definite: false } }

    #[test]
    fn border_box_percent_resolves_from_parent_content_not_border() {
        let parent = Constraints { width: definite(200.0), height: definite(80.0) };
        let used = resolve_used_content_size(
            parent, ChildSizing {
                width: Length::Percent(0.5), height: Length::Percent(0.25),
            }, BoxSizing::BorderBox, 20.0, 10.0,
        ).unwrap();
        assert_eq!(used.content.width, definite(80.0));
        assert_eq!(used.content.height, definite(10.0));
    }

    #[test]
    fn auto_and_indefinite_percentage_do_not_become_zero() {
        let parent = Constraints { width: definite(200.0), height: indefinite() };
        let used = resolve_used_content_size(
            parent, ChildSizing {
                width: Length::Auto, height: Length::Percent(0.5),
            }, BoxSizing::ContentBox, 5.0, 10.0,
        ).unwrap();
        assert_eq!(used.content.width, indefinite());
        assert_eq!(used.content.height, indefinite());
    }

    #[test]
    fn invalid_edges_fail_even_on_indefinite_axes() {
        let parent = Constraints { width: indefinite(), height: indefinite() };
        assert!(resolve_used_content_size(
            parent, ChildSizing { width: Length::Auto, height: Length::Auto },
            BoxSizing::ContentBox, -1.0, 0.0,
        ).is_err());
    }
}
