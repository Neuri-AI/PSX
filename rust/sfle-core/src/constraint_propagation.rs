//! F2.2.4 property-aware child constraints from explicit parent content boxes.
//! Available parent constraints are *not* parent used content dimensions.

use crate::measurement_plan::{
    plan_measurements, Constraints, MeasurementPlan, MeasuredRevision, Node,
};
use crate::sizing::{resolve_length, AvailableSize, Length, Property, ResolvedLength};
use crate::FlexMathError;
use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ChildSizing {
    pub width: Length,
    pub height: Length,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ChildConstraintResolution {
    pub constraints: Constraints,
    pub width_kind: ResolvedLength,
    pub height_kind: ResolvedLength,
}

pub fn resolve_child_constraints(
    parent_content: Constraints,
    child: ChildSizing,
) -> Result<ChildConstraintResolution, FlexMathError> {
    let inline = AvailableSize {
        value: parent_content.width.value,
        definite: parent_content.width.definite,
    };
    let block = AvailableSize {
        value: parent_content.height.value,
        definite: parent_content.height.definite,
    };
    let width = resolve_length(child.width, Property::Width, inline, inline, inline)?;
    let height = resolve_length(child.height, Property::Height, inline, block, inline)?;
    let to_axis = |resolved: ResolvedLength| -> crate::measurement_plan::AxisConstraint {
        match resolved {
            ResolvedLength::Used(value) => crate::measurement_plan::AxisConstraint {
                value: Some(value), definite: true,
            },
            _ => crate::measurement_plan::AxisConstraint { value: None, definite: false },
        }
    };
    Ok(ChildConstraintResolution {
        constraints: Constraints { width: to_axis(width), height: to_axis(height) },
        width_kind: width,
        height_kind: height,
    })
}

pub fn plan_styled_measurements(
    generation: u64,
    nodes: &[Node],
    root_constraints: Constraints,
    parent_content: &[(String, Constraints)],
    child_sizing: &[(String, ChildSizing)],
    measurements: &[MeasuredRevision],
    revisions: &[(String, u64)],
) -> Result<MeasurementPlan, FlexMathError> {
    if nodes.is_empty() {
        if !parent_content.is_empty() || !child_sizing.is_empty() {
            return Err(FlexMathError::InvalidInput("metadata without layout tree"));
        }
        return plan_measurements(generation, nodes, root_constraints, &[], measurements, revisions);
    }
    let mut content = HashMap::new();
    let mut styles = HashMap::new();
    for (id, sizes) in parent_content {
        if !nodes.iter().any(|node| &node.id == id) || content.insert(id.as_str(), *sizes).is_some() {
            return Err(FlexMathError::InvalidInput("unknown/duplicate parent content"));
        }
    }
    for (id, style) in child_sizing {
        if !nodes.iter().any(|node| &node.id == id) || styles.insert(id.as_str(), *style).is_some() {
            return Err(FlexMathError::InvalidInput("unknown/duplicate child sizing"));
        }
    }
    if styles.contains_key(nodes[0].id.as_str()) {
        return Err(FlexMathError::InvalidInput("root is not a child"));
    }
    let mut resolved = Vec::with_capacity(nodes.len().saturating_sub(1));
    for node in nodes.iter().skip(1) {
        let style = styles.get(node.id.as_str()).ok_or(
            FlexMathError::InvalidInput("missing child style"),
        )?;
        let parent = node.parent.as_ref().ok_or(
            FlexMathError::InvalidInput("missing child parent"),
        )?;
        let parent_size = content.get(parent.as_str()).ok_or(
            FlexMathError::InvalidInput("missing established parent content size"),
        )?;
        let used = resolve_child_constraints(*parent_size, *style)?;
        resolved.push((node.id.clone(), used.constraints));
    }
    plan_measurements(
        generation, nodes, root_constraints, &resolved, measurements, revisions,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::measurement_plan::AxisConstraint;

    fn size(value: Option<f64>, definite: bool) -> AxisConstraint {
        AxisConstraint { value, definite }
    }
    fn pair(width: AxisConstraint, height: AxisConstraint) -> Constraints {
        Constraints { width, height }
    }
    #[test]
    fn child_percentages_use_corresponding_parent_content_axis() {
        let parent = pair(size(Some(200.0), true), size(Some(90.0), true));
        let resolved = resolve_child_constraints(parent, ChildSizing {
            width: Length::Percent(0.5), height: Length::Percent(0.25),
        }).unwrap();
        assert_eq!(resolved.constraints, pair(size(Some(100.0), true), size(Some(22.5), true)));
    }
    #[test]
    fn indefinite_reference_remains_indefinite() {
        let parent = pair(size(Some(200.0), true), size(None, false));
        let resolved = resolve_child_constraints(parent, ChildSizing {
            width: Length::Px(40.0), height: Length::Percent(0.25),
        }).unwrap();
        assert_eq!(resolved.constraints.height, size(None, false));
        assert_eq!(resolved.height_kind, ResolvedLength::UnresolvedPercent);
    }
    #[test]
    fn styled_tree_plans_child_before_root() {
        let root = Node { id: "root".into(), parent: None };
        let child = Node { id: "child".into(), parent: Some("root".into()) };
        let parent = pair(size(Some(200.0), true), size(Some(90.0), true));
        let plan = plan_styled_measurements(
            7, &[root, child], parent, &[("root".into(),parent)],
            &[("child".into(), ChildSizing {
                width: Length::Percent(0.5), height: Length::Auto,
            })], &[], &[],
        ).unwrap();
        assert_eq!(plan.requests.iter().map(|r| r.node_id.as_str()).collect::<Vec<_>>(),
                   vec!["child", "root"]);
        assert_eq!(plan.requests[0].constraints.width, size(Some(100.0), true));
        assert_eq!(plan.requests[0].constraints.height, size(None, false));
    }
    #[test]
    fn cannot_infer_parent_content_from_root_constraints() {
        let nodes = [
            Node { id: "root".into(), parent: None },
            Node { id: "child".into(), parent: Some("root".into()) },
        ];
        let parent = pair(size(Some(200.0), true), size(Some(90.0), true));
        assert!(plan_styled_measurements(
            7, &nodes, parent, &[],
            &[("child".into(), ChildSizing {
                width: Length::Percent(0.5), height: Length::Auto,
            })], &[], &[],
        ).is_err());
    }
}
