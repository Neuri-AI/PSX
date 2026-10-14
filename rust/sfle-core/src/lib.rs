//! Pure, renderer-independent CSS Flexbox main-size distribution kernel.
//!
//! This implements the resolved single-line flexible-length freezing step
//! (CSS Flexbox §9.7). It does **not** provide a complete Flexbox renderer,
//! percentage/intrinsic resolution, native geometry or Python bindings yet.
//! The Python counterpart lives at psx/sfle/flex_math.py.

pub mod compute;
pub mod grid_math;
pub mod layout_unit;
#[cfg(feature = "python")]
mod python_binding;
mod compute_layout;
pub mod cross_margins;
pub mod cross_alignment;
pub mod cross_stretch;
pub mod align_content;
pub mod baseline;
pub mod measurement_plan;
pub mod constraint_propagation;
pub mod used_size;
pub mod used_size_tree;
pub mod remeasurement;
pub mod measurement_round;
pub mod convergence;
pub mod measurement_coordinator;
pub mod resolved_tree;
pub mod intrinsic_dependencies;
pub mod dependency_cycle;
pub mod edge_tree;
pub mod margin_tree;
pub mod auto_cross_tree;
pub mod edge_pipeline;
pub mod intrinsic;
pub mod main_margins;
pub mod main_alignment;
pub mod margin_flex_pipeline;
pub mod percentage_box_sizing;
pub mod percentage_flex_basis;
pub mod percentage_constraints;
pub mod line_layout;
pub mod resolved_pipeline;
pub mod sizing;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FlexBasis {
    pub basis: f64,
    pub hypothetical: f64,
    pub grow: f64,
    pub shrink: f64,
    pub min_size: f64,
    pub max_size: Option<f64>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum FlexMathError {
    InvalidInput(&'static str),
    NoProgress,
}

impl FlexBasis {
    pub fn validate(self) -> Result<(), FlexMathError> {
        if ![self.basis, self.hypothetical, self.grow, self.shrink, self.min_size]
            .iter().all(|v| v.is_finite() && *v >= 0.0)
        {
            return Err(FlexMathError::InvalidInput("main sizes and factors must be finite and nonnegative"));
        }
        if let Some(limit) = self.max_size {
            if !limit.is_finite() || limit < self.min_size {
                return Err(FlexMathError::InvalidInput("max_size must be finite and >= min_size"));
            }
        }
        let expected = clamp(self.basis, self.min_size, self.max_size);
        if (self.hypothetical - expected).abs() > 1e-9 {
            return Err(FlexMathError::InvalidInput("hypothetical must equal min/max-clamped basis"));
        }
        Ok(())
    }
}

fn clamp(value: f64, min_size: f64, max_size: Option<f64>) -> f64 {
    if let Some(maximum) = max_size {
        value.max(min_size).min(maximum)
    } else {
        value.max(min_size)
    }
}

/// Resolve definite, content-box main sizes for an already-formed flex line.
///
/// Preconditions: definite container, resolved basis/min/max, no margins,
/// padding, borders, auto margins or intrinsic measurement operations.
pub fn resolve_flexible_lengths(
    items: &[FlexBasis],
    container_inner_main_size: f64,
    gap: f64,
) -> Result<Vec<f64>, FlexMathError> {
    if !container_inner_main_size.is_finite()
        || !gap.is_finite()
        || container_inner_main_size < 0.0
        || gap < 0.0
    {
        return Err(FlexMathError::InvalidInput("container size and gap must be finite and nonnegative"));
    }
    for item in items {
        item.validate()?;
    }
    if items.is_empty() {
        return Ok(vec![]);
    }
    // This low-level resolved Flex kernel deliberately runs on f64; unlike
    // used geometry it has no LayoutUnit storage to saturate into.
    // Reject overflowing finite-input gutter products and basis sums.
    let free_main = container_inner_main_size - gap * (items.len() - 1) as f64;
    let hypothetical_total=items.iter().map(|i| i.hypothetical).sum::<f64>();
    if !free_main.is_finite() || !hypothetical_total.is_finite() {
        return Err(FlexMathError::InvalidInput(
            "resolved Flex prequantization arithmetic overflow",
        ));
    }
    let finite_used=|value:f64|->Result<f64,FlexMathError>{
        if value.is_finite(){Ok(value)}else{
            Err(FlexMathError::InvalidInput(
                "resolved Flex prequantization arithmetic overflow",
            ))
        }
    };
    let growing = hypothetical_total < free_main;
    let mut targets: Vec<f64> = items.iter().map(|i| i.basis).collect();
    let mut frozen = vec![false; items.len()];

    for (idx, item) in items.iter().enumerate() {
        let factor = if growing { item.grow } else { item.shrink };
        if factor == 0.0
            || (growing && item.basis > item.hypothetical)
            || (!growing && item.basis < item.hypothetical)
        {
            targets[idx] = item.hypothetical;
            frozen[idx] = true;
        }
    }

    let initial_free = finite_used(free_main - items.iter().enumerate().map(|(idx, item)| {
        if frozen[idx] { item.hypothetical } else { item.basis }
    }).sum::<f64>())?;

    for _ in 0..=items.len() {
        let live: Vec<usize> = (0..items.len()).filter(|&idx| !frozen[idx]).collect();
        if live.is_empty() {
            return Ok(targets);
        }
        let mut remaining = finite_used(free_main - items.iter().enumerate().map(|(idx, item)| {
            if frozen[idx] { targets[idx] } else { item.basis }
        }).sum::<f64>())?;
        let factors: Vec<f64> = live.iter().map(|&idx| {
            if growing { items[idx].grow } else { items[idx].shrink }
        }).collect();
        let total_factor=finite_used(factors.iter().sum::<f64>())?;
        if total_factor < 1.0 {
            let scaled = finite_used(initial_free * total_factor)?;
            if scaled.abs() < remaining.abs() {
                remaining = scaled;
            }
        }
        let weights: Vec<f64> = live.iter().map(|&idx| {
            if growing { items[idx].grow } else { items[idx].shrink * items[idx].basis }
        }).collect();
        if weights.iter().any(|w|!w.is_finite()){
            return Err(FlexMathError::InvalidInput(
                "resolved Flex prequantization arithmetic overflow",
            ));
        }
        let weight_sum=finite_used(weights.iter().sum::<f64>())?;
        for (&idx, &weight) in live.iter().zip(weights.iter()) {
            let contribution = if weight_sum > 0.0 {
                finite_used(finite_used(remaining * weight)? / weight_sum)?
            } else { 0.0 };
            targets[idx] = finite_used(items[idx].basis + contribution)?;
        }

        let mut violations = vec![0.0_f64; items.len()];
        let mut total_violation = 0.0_f64;
        for &idx in &live {
            let raw = targets[idx];
            let final_size = clamp(raw.max(0.0), items[idx].min_size, items[idx].max_size);
            targets[idx] = final_size;
            violations[idx] = finite_used(final_size - raw)?;
            total_violation = finite_used(total_violation + violations[idx])?;
        }
        if total_violation.abs() <= 1e-12 {
            return Ok(targets);
        }
        let mut froze_one = false;
        for idx in live {
            if (total_violation > 0.0 && violations[idx] > 0.0)
                || (total_violation < 0.0 && violations[idx] < 0.0)
            {
                frozen[idx] = true;
                froze_one = true;
            }
        }
        if !froze_one {
            return Err(FlexMathError::NoProgress);
        }
    }
    Err(FlexMathError::NoProgress)
}
