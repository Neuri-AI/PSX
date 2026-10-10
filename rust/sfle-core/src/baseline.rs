//! Baseline alignment using upstream measured border-box offsets.
use crate::FlexMathError;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BaselineItem {
    pub border_cross_size: f64,
    pub start_margin: f64,
    pub end_margin: f64,
    pub baseline: f64,
}
impl BaselineItem {
    fn validate(self) -> Result<(), FlexMathError> {
        if ![self.border_cross_size,self.start_margin,self.end_margin,self.baseline]
            .iter().all(|v| v.is_finite())
            || self.border_cross_size < 0.0
            || self.baseline < 0.0 || self.baseline > self.border_cross_size
        {
            return Err(FlexMathError::InvalidInput("invalid measured baseline"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BaselineGroup {
    pub ascent: f64,
    pub descent: f64,
}
impl BaselineGroup {
    pub fn extent(self) -> f64 { self.ascent + self.descent }
}

pub fn measure_baseline_group(items: &[BaselineItem]) -> Result<BaselineGroup,FlexMathError> {
    if items.is_empty() {
        return Err(FlexMathError::InvalidInput("empty baseline group"));
    }
    let mut ascent=f64::NEG_INFINITY;
    let mut descent=f64::NEG_INFINITY;
    for item in items {
        item.validate()?;
        ascent=ascent.max(item.start_margin+item.baseline);
        descent=descent.max(item.end_margin+item.border_cross_size-item.baseline);
    }
    Ok(BaselineGroup{ascent,descent})
}

pub fn position_baseline_item(
    item:BaselineItem,group:BaselineGroup,line_cross_size:f64,cross_forward:bool,
)->Result<f64,FlexMathError>{
    item.validate()?;
    if !line_cross_size.is_finite() || line_cross_size < 0.0
        || !group.ascent.is_finite() || !group.descent.is_finite(){
        return Err(FlexMathError::InvalidInput("invalid baseline group size"));
    }
    let logical=group.ascent-item.baseline;
    Ok(if cross_forward {logical}
       else {line_cross_size-logical-item.border_cross_size})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn align_two_measured_baselines(){
        let a=BaselineItem{border_cross_size:20.0,start_margin:0.0,end_margin:0.0,baseline:15.0};
        let b=BaselineItem{border_cross_size:30.0,start_margin:0.0,end_margin:0.0,baseline:10.0};
        let group=measure_baseline_group(&[a,b]).unwrap();
        assert_eq!(group.extent(),35.0);
        assert_eq!(position_baseline_item(a,group,35.0,true).unwrap(),0.0);
        assert_eq!(position_baseline_item(b,group,35.0,true).unwrap(),5.0);
    }
    #[test]
    fn reject_unmeasured_invalid_baselines(){
        let x=BaselineItem{border_cross_size:10.0,start_margin:0.0,end_margin:0.0,baseline:11.0};
        assert!(measure_baseline_group(&[x]).is_err());
    }
}
