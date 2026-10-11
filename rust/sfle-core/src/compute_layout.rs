//! Renderer-neutral snapshot sizing orchestration for the initial closed F2 path.
//! This stage never measures widgets and never converts an unknown CSS value
//! into a numeric zero. Unsupported contexts carry a stable diagnostic.
use crate::align_content::AlignContent;
use crate::compute::{ComputeError, LayoutBox, LayoutInput, LayoutResult, Rect};
use crate::cross_alignment::CrossAlign;
use crate::edge_pipeline::{BoxEdges,Edges};
use crate::line_layout::{Direction, Wrap, WritingDirection};
use crate::main_alignment::JustifyContent;
use crate::margin_flex_pipeline::MarginFlexItem;
use crate::margin_tree::{compute_margin_tree, MarginTreeNode};
use crate::{resolve_flexible_lengths, FlexBasis};
use crate::layout_unit::LayoutUnit;
use serde_json::Value;
use std::collections::HashMap;

#[derive(Clone, Copy)]
enum Length { Auto, Px(f64), Percent(f64) }

#[derive(Clone, Copy)]
struct Style {
    direction: Direction,
    wrap: Wrap,
    justify: JustifyContent,
    align_content: AlignContent,
    align_self: CrossAlign,
    margin_top: Length,
    margin_right: Length,
    margin_bottom: Length,
    margin_left: Length,
    max_width: Length,
    max_height: Length,
    width: Length,
    height: Length,
    basis: Length,
    grow: f64,
    shrink: f64,
    min_width: Length,
    min_height: Length,
    align: CrossAlign,
    row_gap:Length,
    column_gap:Length,
    padding_top:Length,
    padding_right:Length,
    padding_bottom:Length,
    padding_left:Length,
}

fn failure(code: &'static str, message: impl Into<String>, id: Option<&str>) -> ComputeError {
    ComputeError { code, message: message.into(), node_id: id.map(str::to_owned) }
}
fn unsupported(message: impl Into<String>, id: &str) -> ComputeError {
    failure("SFLE_UNSUPPORTED_FEATURE", message, Some(id))
}
fn measurement(message: impl Into<String>, id: &str) -> ComputeError {
    failure("SFLE_UNSUPPORTED_MEASUREMENT", message, Some(id))
}
fn value<'a>(map: &'a serde_json::Map<String,Value>, keys: &[&str]) -> Option<&'a Value> {
    keys.iter().find_map(|key| map.get(*key))
}
fn length(raw: Option<&Value>, id: &str) -> Result<Length, ComputeError> {
    let Some(v) = raw else { return Ok(Length::Auto) };
    if let Some(n)=v.as_f64() {
        if !n.is_finite() || n<0.0 { return Err(failure("SFLE_INVALID_LENGTH","Nonfinite or negative length.",Some(id))); }
        return Ok(Length::Px(n));
    }
    if let Some(s) = v.as_str() {
        if s=="auto" { return Ok(Length::Auto); }
        if let Some(n) = s.strip_suffix("px").and_then(|x|x.parse::<f64>().ok()) {
            if n.is_finite()&&n>=0.0{return Ok(Length::Px(n));}
        }
        if let Some(n) = s.strip_suffix('%').and_then(|x|x.parse::<f64>().ok()) {
            if n.is_finite()&&n>=0.0{return Ok(Length::Percent(n/100.0));}
        }
    }
    if let Some(map) = v.as_object() {
        let kind=map.get("kind").and_then(Value::as_str);
        let number=map.get("value").and_then(Value::as_f64);
        match kind {
            Some("auto") if map.get("value").is_none_or(Value::is_null) => return Ok(Length::Auto),
            Some("px") if number.is_some_and(|n|n.is_finite()&&n>=0.0) =>return Ok(Length::Px(number.unwrap())),
            Some("percent") if number.is_some_and(|n|n.is_finite()&&n>=0.0) =>return Ok(Length::Percent(number.unwrap())),
            _=>{},
        }
    }
    Err(unsupported("Unsupported CSS length keyword or expression.", id))
}
fn factor(raw: Option<&Value>, default: f64, id:&str)->Result<f64,ComputeError>{
    let n=raw.map(Value::as_f64).flatten().unwrap_or(default);
    if !n.is_finite()||n<0.0 {
        return Err(failure("SFLE_INVALID_LENGTH","Invalid flex factor.",Some(id)));
    }
    Ok(n)
}
fn style(input:&crate::compute::LayoutNode)->Result<Style,ComputeError>{
    let map=&input.style;
    for key in map.keys(){
        if !matches!(key.as_str(),"direction"|"width"|"height"|"layout_width"|"layout_height"|
            "flex_basis"|"flex_grow"|"flex_shrink"|"min_width"|"min_height"|
            "layout_min_width"|"layout_min_height"|"align_items"|
            "wrap"|"justify_content"|"align_content"|"align_self"|
            "max_width"|"max_height"|"layout_max_width"|"layout_max_height"|
            "layout_margin_top"|"layout_margin_right"|"layout_margin_bottom"|"layout_margin_left"|
            "row_gap"|"column_gap"|
            "layout_padding_top"|"layout_padding_right"|
            "layout_padding_bottom"|"layout_padding_left"){
            return Err(unsupported(format!("Unimplemented CSS style property: {key}."),&input.node_id));
        }
    }
    if (map.contains_key("width")&&map.contains_key("layout_width"))||
       (map.contains_key("height")&&map.contains_key("layout_height")){
        return Err(failure("SFLE_LAYOUT_CONSTRAINT_ERROR","Conflicting layout size aliases.",Some(&input.node_id)));
    }
    let direction=match map.get("direction").and_then(Value::as_str).unwrap_or("row"){
        "row"=>Direction::Row,"row-reverse"=>Direction::RowReverse,
        "column"=>Direction::Column,"column-reverse"=>Direction::ColumnReverse,
        _=>return Err(unsupported("Unsupported flex direction.",&input.node_id)),
    };
    let parse_align=|k:&str,default:&str| -> Result<CrossAlign,ComputeError> {
        match map.get(k).and_then(Value::as_str).unwrap_or(default) {
            "stretch"=>Ok(CrossAlign::Stretch),"flex-start"=>Ok(CrossAlign::FlexStart),
            "flex-end"=>Ok(CrossAlign::FlexEnd),"center"=>Ok(CrossAlign::Center),
            "baseline"=>Ok(CrossAlign::Baseline),
            "auto" if k=="align_self"=>Ok(CrossAlign::Auto),
            _=>Err(unsupported(format!("Unsupported {k} value."),&input.node_id)),
        }
    };
    let align=parse_align("align_items","stretch")?;
    let align_self=parse_align("align_self","auto")?;
    let wrap=match map.get("wrap").and_then(Value::as_str).unwrap_or("nowrap"){
        "nowrap"=>Wrap::NoWrap,"wrap"=>Wrap::Wrap,"wrap-reverse"=>Wrap::WrapReverse,
        _=>return Err(unsupported("Unsupported wrap value.",&input.node_id)),
    };
    let justify=match map.get("justify_content").and_then(Value::as_str).unwrap_or("flex-start"){
        "flex-start"=>JustifyContent::FlexStart,"flex-end"=>JustifyContent::FlexEnd,
        "center"=>JustifyContent::Center,"space-between"=>JustifyContent::SpaceBetween,
        "space-around"=>JustifyContent::SpaceAround,"space-evenly"=>JustifyContent::SpaceEvenly,
        _=>return Err(unsupported("Unsupported justify-content value.",&input.node_id)),
    };
    let align_content=match map.get("align_content").and_then(Value::as_str).unwrap_or("normal"){
        "normal"|"stretch"=>AlignContent::Stretch,
        "flex-start"=>AlignContent::FlexStart,"flex-end"=>AlignContent::FlexEnd,
        "center"=>AlignContent::Center,"space-between"=>AlignContent::SpaceBetween,
        "space-around"=>AlignContent::SpaceAround,"space-evenly"=>AlignContent::SpaceEvenly,
        _=>return Err(unsupported("Unsupported align-content value.",&input.node_id)),
    };
    Ok(Style{
        direction,align,wrap,justify,align_content,align_self,
        margin_top:if map.contains_key("layout_margin_top"){length(map.get("layout_margin_top"),&input.node_id)?}else{Length::Px(0.0)},
        margin_right:if map.contains_key("layout_margin_right"){length(map.get("layout_margin_right"),&input.node_id)?}else{Length::Px(0.0)},
        margin_bottom:if map.contains_key("layout_margin_bottom"){length(map.get("layout_margin_bottom"),&input.node_id)?}else{Length::Px(0.0)},
        margin_left:if map.contains_key("layout_margin_left"){length(map.get("layout_margin_left"),&input.node_id)?}else{Length::Px(0.0)},
        max_width:length(value(map,&["layout_max_width","max_width"]),&input.node_id)?,
        max_height:length(value(map,&["layout_max_height","max_height"]),&input.node_id)?,
        row_gap:if map.contains_key("row_gap"){length(map.get("row_gap"),&input.node_id)?}else{Length::Px(0.0)},
        column_gap:if map.contains_key("column_gap"){length(map.get("column_gap"),&input.node_id)?}else{Length::Px(0.0)},
        padding_top:if map.contains_key("layout_padding_top"){length(map.get("layout_padding_top"),&input.node_id)?}else{Length::Px(0.0)},
        padding_right:if map.contains_key("layout_padding_right"){length(map.get("layout_padding_right"),&input.node_id)?}else{Length::Px(0.0)},
        padding_bottom:if map.contains_key("layout_padding_bottom"){length(map.get("layout_padding_bottom"),&input.node_id)?}else{Length::Px(0.0)},
        padding_left:if map.contains_key("layout_padding_left"){length(map.get("layout_padding_left"),&input.node_id)?}else{Length::Px(0.0)},
        width:length(value(map,&["layout_width","width"]),&input.node_id)?,
        height:length(value(map,&["layout_height","height"]),&input.node_id)?,
        basis:length(map.get("flex_basis"),&input.node_id)?,
        grow:factor(map.get("flex_grow"),0.0,&input.node_id)?,
        shrink:factor(map.get("flex_shrink"),1.0,&input.node_id)?,
        min_width:length(value(map,&["layout_min_width","min_width"]),&input.node_id)?,
        min_height:length(value(map,&["layout_min_height","min_height"]),&input.node_id)?,
    })
}
fn layout_unit(value:f64)->f64 {
    LayoutUnit::from_nearest(value).expect("SFLE prevalidated finite used length").to_px()
}
fn sum_units(values: impl IntoIterator<Item=f64>) -> f64 {
    values.into_iter().fold(LayoutUnit::from_raw(0), |total, value|
        total + LayoutUnit::from_nearest(value).expect("Finite used geometry")
    ).to_px()
}
fn subtract_units(value: f64, deductions: impl IntoIterator<Item=f64>) -> f64 {
    deductions.into_iter().fold(LayoutUnit::from_nearest(value).expect("Finite used geometry"),
        |total, deduction| total - LayoutUnit::from_nearest(deduction).expect("Finite used geometry")
    ).to_px()
}
fn percent_flex_basis_used(fraction:f64,reference:f64)->f64 {
    LayoutUnit::from_floor(fraction*reference)
        .expect("SFLE prevalidated finite percentage").to_px()
}
fn blink_flex_targets(bases:&[FlexBasis], inner:f64,gap:f64,id:&str)->Result<Vec<f64>,ComputeError>{
    // Exact port of Chromium 153 line_flexer.cc:
    // FreezeItems + ResolveFlexibleLengths. Integer LayoutUnit for all
    // free-space subtractions, used sizes, clamping and repeated violations.
    // f64 only for cumulative flex factors / weighted shrink fractions.
    if bases.is_empty(){return Ok(vec![]);}
    let raw=|v:f64| LayoutUnit::from_nearest(v).map_err(|e|unsupported(e,id));
    let available=raw(inner)?;
    let gutter=raw(gap)?;
    let base:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.basis)).collect::<Result<_,_>>()?;
    let hypot:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.hypothetical)).collect::<Result<_,_>>()?;
    let min:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.min_size)).collect::<Result<_,_>>()?;
    let max:Vec<Option<LayoutUnit>>=bases.iter().map(|b|b.max_size.map(&raw).transpose())
        .collect::<Result<_,_>>()?;
    let usable=available-LayoutUnit::from_raw(
        gutter.raw().saturating_mul((bases.len()-1) as i32));
    let growing=hypot.iter().map(|v|v.raw() as i64).sum::<i64>()<usable.raw() as i64;
    let mut frozen:Vec<bool>=bases.iter().enumerate().map(|(i,b)|{
        let factor=if growing{b.grow}else{b.shrink};
        factor==0.0 || if growing{base[i]>hypot[i]}else{base[i]<hypot[i]}
    }).collect();
    let mut sizes=hypot.clone();
    let mut initial_free=LayoutUnit::from_raw(0);
    for round in 0..=bases.len(){
        let mut total_factor=0.0_f64;
        let mut total_scaled_shrink=0.0_f64;
        let mut fractions=vec![0.0_f64;bases.len()];
        let mut remaining=available;
        for (i,b) in bases.iter().enumerate(){
            if frozen[i]{
                remaining=remaining-sizes[i]-gutter;
                continue;
            }
            sizes[i]=hypot[i];
            let factor=if growing{b.grow}else{b.shrink};
            total_factor+=factor;
            if growing{
                fractions[i]=factor/total_factor;
            }else{
                let weighted=factor*base[i].to_px();
                total_scaled_shrink+=weighted;
                fractions[i]=if total_scaled_shrink==0.0{0.0}else{weighted/total_scaled_shrink};
            }
            remaining=remaining-base[i]-gutter;
        }
        remaining=remaining+gutter;
        if round==0{initial_free=remaining;}
        if total_factor>0.0 && total_factor<1.0 {
            let fraction=LayoutUnit::from_trunc(initial_free.to_px()*total_factor)
                .map_err(|e|unsupported(e,id))?;
            if fraction.raw().abs()<remaining.raw().abs(){remaining=fraction;}
        }
        if (growing && remaining.raw()<=0) || (!growing && remaining.raw()>=0){
            return Ok(sizes.into_iter().map(|v|v.to_px()).collect());
        }
        let mut violations=vec![0_i32;bases.len()];
        let mut total_violation=LayoutUnit::from_raw(0);
        for i in (0..bases.len()).rev(){
            if frozen[i]{continue;}
            let extra=if fractions[i]==1.0{remaining}else{
                LayoutUnit::from_nearest(remaining.to_px()*fractions[i])
                    .map_err(|e|unsupported(e,id))?
            };
            remaining=remaining-extra;
            let unbounded=base[i]+extra;
            let mut bounded=unbounded;
            if bounded<min[i]{bounded=min[i];}
            if let Some(maximum)=max[i]{
                if bounded>maximum{bounded=maximum;}
            }
            sizes[i]=bounded;
            let violation=bounded-unbounded;
            violations[i]=violation.raw();
            total_violation=total_violation+violation;
        }
        if total_violation.raw()==0{
            return Ok(sizes.into_iter().map(|v|v.to_px()).collect());
        }
        for (i,&v) in violations.iter().enumerate(){
            if (v<0 && total_violation.raw()<0) || (v>0 && total_violation.raw()>0){
                frozen[i]=true;
            }
        }
    }
    Err(measurement("Blink fractional freezing did not converge.",id))
}
fn resolved(v:Length, reference:Option<f64>, vertical:bool, id:&str)->Result<Option<f64>,ComputeError>{
    match v {
        Length::Auto=>Ok(None),
        Length::Px(n)=>Ok(Some(n)),
        Length::Percent(p) if reference.is_some()=>Ok(Some(layout_unit(p*reference.unwrap()))),
        Length::Percent(_) if vertical=>Ok(None), // CSS auto-block-size cyclic context
        Length::Percent(_)=>Err(unsupported("Unlisted indefinite inline percentage dependency cycle.",id)),
    }
}
fn padding(style:Style,inline_reference:f64,id:&str)->Result<Edges,ComputeError>{
    fn edge(value:Length,base:f64,id:&str)->Result<f64,ComputeError>{
        match value{
            Length::Px(n)=>Ok(n),
            Length::Percent(p)=>{
                // Used padding percentages use Blink's floor LayoutUnit
                // conversion, not the flex allocation's nearest conversion.
                // Move one representational ULP up to stabilize decimal CSS
                // boundaries such as 35% * 45px = 15.75px.
                let value=p*base;
                let stable=if value.is_finite()&&value>=0.0{
                    f64::from_bits(value.to_bits()+1)
                }else{value};
                LayoutUnit::from_floor(stable).map(|n|n.to_px())
                    .map_err(|e|unsupported(e,id))
            },
            Length::Auto=>Err(failure("SFLE_INVALID_LENGTH","Padding requires a valid numeric CSS length.",Some(id))),
        }
    }
    Ok(Edges{
        top:edge(style.padding_top,inline_reference,id)?,
        right:edge(style.padding_right,inline_reference,id)?,
        bottom:edge(style.padding_bottom,inline_reference,id)?,
        left:edge(style.padding_left,inline_reference,id)?,
    })
}
fn intrinsic_gap(length:Length,id:&str)->Result<f64,ComputeError>{
    match length{
        Length::Px(n)=>Ok(n),
        Length::Percent(_)=>Ok(0.0), // intrinsic contribution only
        Length::Auto=>Err(failure("SFLE_INVALID_LENGTH","Invalid gap keyword.",Some(id))),
    }
}
fn used_gap(length:Length,reference:f64,id:&str)->Result<f64,ComputeError>{
    intrinsic_gap(length,id)?;
    match length{Length::Px(n)=>Ok(n),Length::Percent(p)=>Ok((p*reference*64.0).round()/64.0),
        Length::Auto=>Err(failure("SFLE_INVALID_LENGTH","Invalid gap.",Some(id))),}
}
fn main_gap(style:Style,width:f64,height:f64,id:&str)->Result<f64,ComputeError>{
    if horizontal(style.direction){used_gap(style.column_gap,width,id)}
    else{used_gap(style.row_gap,height,id)}
}
fn horizontal(dir:Direction)->bool{
    matches!(dir,Direction::Row|Direction::RowReverse)
}
struct Context<'a>{
    provisional:bool,
    input:&'a LayoutInput,
    styles:Vec<Style>,
    children:Vec<Vec<usize>>,
    cyclic_padding:Vec<bool>,
    measurements:HashMap<&'a str,&'a crate::compute::MeasuredBox>,
    used:Vec<Option<(f64,f64)>>,
}
fn bounded_intrinsic(style:Style,h:bool,mut value:f64,reference:Option<f64>)->f64{
    // Minimum precedence wins over a conflicting maximum. Percentage bounds
    // resolve only against a definite containing-block axis.
    let maximum=if h{style.max_width}else{style.max_height};
    let minimum=if h{style.min_width}else{style.min_height};
    let bound=|v:Length|match v {
        Length::Px(n)=>Some(layout_unit(n)),
        Length::Percent(p)=>reference.map(|r|layout_unit(p*r)),
        Length::Auto=>None,
    };
    if let Some(cap)=bound(maximum){value=value.min(cap);}
    if let Some(floor)=bound(minimum){value=value.max(floor);}
    layout_unit(value)
}
impl Context<'_>{
    fn preferred(&self,index:usize,h:bool)->Result<f64,ComputeError>{
        self.intrinsic_contribution(index,h,false)
    }
    fn intrinsic_contribution(&self,index:usize,h:bool,minimum:bool)->Result<f64,ComputeError>{
        let node=&self.input.nodes[index];
        let style=self.styles[index];
        match if h {style.width}else{style.height}{
            Length::Px(n)=>return Ok(bounded_intrinsic(style,h,n,None)),
            _=>{},
        }
        if self.children[index].is_empty(){
            if let Some(m)=self.measurements.get(node.node_id.as_str()){
                let value = if minimum {
                    if h {m.intrinsic.min_content_width} else {m.intrinsic.min_content_height}
                } else {
                    if h {m.intrinsic.preferred_width} else {m.intrinsic.preferred_height}
                };
                return Ok(bounded_intrinsic(style,h,value,None));
            }
            if node.component=="Text" && !minimum {
                return Err(measurement("Text requires intrinsic measurement.",&node.node_id));
            }
            return Ok(bounded_intrinsic(style,h,0.0,None));
        }
        let mut sizes=Vec::with_capacity(self.children[index].len());
        for &child in &self.children[index] {
            let child_style = self.styles[child];
            let edges = if h {
                [child_style.padding_left, child_style.padding_right]
            } else {
                [child_style.padding_top, child_style.padding_bottom]
            };
            let mut padding_sum = 0.0_f64;
            for edge in edges {
                match edge {
                    Length::Px(n) => padding_sum = sum_units([padding_sum,n]),
                    Length::Percent(_) if self.cyclic_padding[child] => {},
                    _ => return Err(unsupported(
                        "Unresolved intrinsic percentage padding contribution.",
                        &self.input.nodes[child].node_id,
                    )),
                }
            }
            let mut contribution = self.intrinsic_contribution(child,h,minimum)?;
            if horizontal(style.direction)==h {
                let base = match child_style.basis {
                    Length::Px(n) => layout_unit(n),
                    _ => self.preferred(child,h)?,
                };
                if child_style.grow==0.0 {contribution=contribution.min(base);}
                if child_style.shrink==0.0 {contribution=contribution.max(base);}
                contribution=bounded_intrinsic(child_style,h,contribution,None);
            }
            let margins=if h {[child_style.margin_left,child_style.margin_right]}
                        else {[child_style.margin_top,child_style.margin_bottom]};
            let mut outer=sum_units([contribution,padding_sum]);
            for margin in margins {
                if let Length::Px(n)=margin {outer=sum_units([outer,n]);}
            }
            sizes.push(outer);
        }
        if horizontal(style.direction)==h {
            if minimum && style.wrap!=Wrap::NoWrap {
                return Ok(bounded_intrinsic(style,h,sizes.into_iter().fold(0.0_f64,f64::max),None));
            }
            let intrinsic = intrinsic_gap(if horizontal(style.direction){style.column_gap}else{style.row_gap},&node.node_id)?;
            let mut total=0.0;
            for (i,size) in sizes.into_iter().enumerate() {
                total=sum_units([total,if i>0 {intrinsic} else {0.0},size]);
            }
            Ok(bounded_intrinsic(style,h,total,None))
        } else {
            Ok(bounded_intrinsic(style,h,sizes.into_iter().fold(0.0_f64,f64::max),None))
        }
    }
    fn layout(&mut self,index:usize,forced_w:Option<f64>,forced_h:Option<f64>,
        pw:Option<f64>,ph:Option<f64>) ->Result<(f64,f64),ComputeError>{
        let node=&self.input.nodes[index];
        let style=self.styles[index];
        let id=node.node_id.clone();
        let mut width=forced_w.or(resolved(style.width,pw,false,&id)?);
        let mut height=forced_h.or(resolved(style.height,ph,true,&id)?);
        if self.children[index].is_empty(){
            if width.is_none(){width=Some(self.preferred(index,true)?);}
            if height.is_none(){
                if matches!(style.height,Length::Percent(_))
                    && !self.measurements.contains_key(id.as_str()){
                    return Err(unsupported(
                        "Unmeasured indefinite percentage block dependency cycle.",
                        &id,
                    ));
                }
                if let Some(m)=self.measurements.get(id.as_str()){
                    if !self.provisional && m.constraints.width.definite &&
                        (m.constraints.width.value.unwrap()-width.unwrap()).abs()>0.01{
                        return Err(measurement("Missing post-flex width-specific intrinsic measurement.",&id));
                    }
                }
                height=Some(self.preferred(index,false)?);
            }
            let dims=(layout_unit(bounded_intrinsic(style,true,width.unwrap(),pw)),layout_unit(bounded_intrinsic(style,false,height.unwrap(),ph)));
            self.used[index]=Some(dims);
            return Ok(dims);
        }
        let row=horizontal(style.direction);
        if width.is_none(){width=Some(self.preferred(index,true)?);}
        if height.is_none()&&!row{height=Some(self.preferred(index,false)?);}
        width=width.map(|v|bounded_intrinsic(style,true,v,pw));
        height=height.map(|v|bounded_intrinsic(style,false,v,ph));
        let main=if row{width.unwrap()}else{height.unwrap()};
        let main_reference=if (row&&matches!(style.width,Length::Auto)&&forced_w.is_none())||
                              (!row&&matches!(style.height,Length::Auto)&&forced_h.is_none()){
            None
        }else{Some(main)};
        let child_indices=self.children[index].clone();
        let mut bases=Vec::with_capacity(child_indices.len());
        for &child in &child_indices{
            let child_style=self.styles[child];
            let child_id=&self.input.nodes[child].node_id;
            let axis=if row{child_style.width}else{child_style.height};
            let desired=match child_style.basis{
                Length::Auto=>resolved(axis,main_reference,!row,child_id)?
                    .unwrap_or(self.preferred(child,row)?),
                Length::Px(n)=>n,
                Length::Percent(p)=>match main_reference{
                    Some(n)=>percent_flex_basis_used(p,n),None=>self.preferred(child,row)?,
                },
            };
            let mut minimum=match if row{child_style.min_width}else{child_style.min_height}{
                Length::Px(n)=>n,
                Length::Auto=>{
                    let content=self.intrinsic_contribution(child,row,true)?;
                    resolved(axis,main_reference,!row,child_id)?.map_or(content,|n|content.min(n))
                },
                Length::Percent(p) if main_reference.is_some()=>layout_unit(p*main_reference.unwrap()),
                Length::Percent(_)=>return Err(unsupported("Unlisted percentage minimum size dependency cycle.",child_id)),
            };
            let mut maximum=match if row{child_style.max_width}else{child_style.max_height}{
                Length::Px(n)=>Some(n),Length::Auto=>None,
                Length::Percent(p) if main_reference.is_some()=>Some(layout_unit(p*main_reference.unwrap())),
                Length::Percent(_)=>return Err(unsupported("Unlisted indefinite percentage maximum size dependency cycle.",child_id)),
            };
            if let Some(cap)=maximum{
                if matches!(if row{child_style.min_width}else{child_style.min_height},Length::Auto){
                    minimum=minimum.min(cap);
                }
                if cap<minimum{maximum=Some(minimum);}
            }
            let hypothetical=desired.max(minimum).min(maximum.unwrap_or(f64::INFINITY));
            bases.push(FlexBasis {
                basis:desired,hypothetical,
                grow:child_style.grow,shrink:child_style.shrink,
                min_size:minimum,max_size:maximum,
            });
        }
        let main=layout_unit(main);
        let gap=layout_unit(main_gap(style,width.unwrap(),height.unwrap_or(0.0),&id)?);
        let edges=child_indices.iter().map(|&child|
            padding(self.styles[child],width.unwrap(),&self.input.nodes[child].node_id)
        ).collect::<Result<Vec<_>,ComputeError>>()?;
        let fixed_margin=|length|margin_value(length,width.unwrap()).unwrap_or(0.0);
        let fixed_edges:Vec<f64>=child_indices.iter().zip(&edges).map(|(&child,e)|{
            let s=self.styles[child];
            if row {sum_units([e.left,e.right,fixed_margin(s.margin_left),fixed_margin(s.margin_right)])}
            else {sum_units([e.top,e.bottom,fixed_margin(s.margin_top),fixed_margin(s.margin_bottom)])}
        }).collect();
        // Outer hypothetical sizes determine line membership before flexing.
        let mut lines:Vec<Vec<usize>>=vec![vec![]];
        let mut occupied=0.0;
        for (i,basis) in bases.iter().enumerate(){
            let outer=sum_units([basis.hypothetical,fixed_edges[i]]);
            let candidate=sum_units([occupied,if lines.last().unwrap().is_empty(){0.0}else{gap},outer]);
            if style.wrap!=Wrap::NoWrap && !lines.last().unwrap().is_empty() && candidate>main {
                lines.push(vec![]);
                occupied=0.0;
            }
            occupied=sum_units([occupied,if lines.last().unwrap().is_empty(){0.0}else{gap},outer]);
            lines.last_mut().unwrap().push(i);
        }
        let mut targets=vec![0.0;bases.len()];
        for line in &lines {
            let available=subtract_units(main,line.iter().map(|&i|fixed_edges[i])).max(0.0);
            let line_bases:Vec<FlexBasis>=line.iter().map(|&i|bases[i]).collect();
            for (&i,target) in line.iter().zip(blink_flex_targets(&line_bases,available,gap,&id)?){
                targets[i]=target;
            }
        }
        let mut cross_sizes=Vec::new();
        for ((&child,&target),padding_box) in child_indices.iter().zip(targets.iter()).zip(edges.iter()){
            let child_id=self.input.nodes[child].node_id.clone();
            let child_style=self.styles[child];
            let (cw,ch)=if row{
                let mut cross=resolved(child_style.height,height,true,&child_id)?;
                let align=if child_style.align_self==CrossAlign::Auto{style.align}else{child_style.align_self};
                if cross.is_none()&&height.is_some()&&align==CrossAlign::Stretch
                    &&style.wrap==Wrap::NoWrap
                    &&!matches!(child_style.margin_top,Length::Auto)
                    &&!matches!(child_style.margin_bottom,Length::Auto){
                    cross=Some(subtract_units(height.unwrap(),[padding_box.top,padding_box.bottom,
                        fixed_margin(child_style.margin_top),fixed_margin(child_style.margin_bottom)]).max(0.0));
                }
                self.layout(child,Some(target),cross,width,height)?
            }else{
                let mut cross=resolved(child_style.width,width,false,&child_id)?;
                let align=if child_style.align_self==CrossAlign::Auto{style.align}else{child_style.align_self};
                if cross.is_none()&&align==CrossAlign::Stretch&&style.wrap==Wrap::NoWrap
                    &&!matches!(child_style.margin_left,Length::Auto)
                    &&!matches!(child_style.margin_right,Length::Auto){
                    cross=Some(subtract_units(width.unwrap(),[padding_box.left,padding_box.right,
                        fixed_margin(child_style.margin_left),fixed_margin(child_style.margin_right)]).max(0.0));
                }
                self.layout(child,cross,Some(target),width,height)?
            };
            // CSS auto cross contribution is the entire child padding box,
            // not merely the content size returned by recursive layout.
            cross_sizes.push(if row{sum_units([ch,padding_box.top,padding_box.bottom,
                fixed_margin(child_style.margin_top),fixed_margin(child_style.margin_bottom)]).max(0.0)}
                else{sum_units([cw,padding_box.left,padding_box.right,
                    fixed_margin(child_style.margin_left),fixed_margin(child_style.margin_right)]).max(0.0)});
        }
        if height.is_none(){
            // Apply cross min/max only after recursive auto sizing has used
            // the children's outer contributions (matching Python + Blink).
            let cross_gap=intrinsic_gap(style.row_gap,&id)?;
            let mut auto_cross=0.0;
            for (i,line) in lines.iter().enumerate(){
                let size=line.iter().map(|&i|cross_sizes[i]).fold(0.0_f64,f64::max);
                auto_cross=sum_units([auto_cross,if i>0{cross_gap}else{0.0},size]);
            }
            height=Some(bounded_intrinsic(style,false,auto_cross,ph));
        }
        let dims=(layout_unit(width.unwrap()),layout_unit(height.unwrap()));
        self.used[index]=Some(dims);
        Ok(dims)
    }
}
fn margin_value(v:Length,base:f64)->Option<f64>{
    match v{Length::Auto=>None,Length::Px(n)=>Some(layout_unit(n)),
        Length::Percent(p)=>Some(layout_unit(p*base))}
}
fn cross_gap(st:Style,width:f64,id:&str)->Result<f64,ComputeError>{
    used_gap(if horizontal(st.direction){st.row_gap}else{st.column_gap},width,id)
}
fn converted(r:crate::line_layout::Rect)->Rect{
    Rect{x:r.x,y:r.y,width:r.width,height:r.height}
}
pub fn compute_normalized(input:&LayoutInput,provisional:bool)->Result<LayoutResult,ComputeError>{
    if input.nodes.is_empty(){
        return Ok(LayoutResult {schema_version:1,generation:input.generation,
            boxes:vec![],diagnostics:vec![],measurement_error:None,
            engine_error:None,geometry_commit_error:None});
    }
    let mut indices: HashMap<&str, usize> = HashMap::new();
    let mut children: Vec<Vec<usize>> = vec![Vec::new();input.nodes.len()];
    let mut styles=Vec::with_capacity(input.nodes.len());
    for (index,node) in input.nodes.iter().enumerate(){
        styles.push(style(node)?);
        if let Some(parent)=node.parent_id.as_ref(){
            let parent_index=indices.get(parent.as_str()).copied().ok_or(
                failure("SFLE_INVALID_TREE","Missing parent in normalized preorder.",Some(&node.node_id))
            )?;
            children[parent_index].push(index);
        }
        indices.insert(node.node_id.as_str(),index);
    }
    for index in 0..input.nodes.len(){
        if children[index].len()!=1 {continue;}
        let child=children[index][0];
        let Some(&grand)=children[child].first() else{continue;};
        let (s,c,g)=(styles[index],styles[child],styles[grand]);
        if matches!(s.width,Length::Auto)&&matches!(s.height,Length::Auto)
            &&matches!(c.width,Length::Percent(_))&&matches!(c.height,Length::Percent(_))
            &&matches!(g.width,Length::Percent(_))&&matches!(g.height,Length::Percent(_)){
            return Err(unsupported("Unlisted multi-node percentage dependency cycle across auto ancestors.",
                &input.nodes[child].node_id));
        }
    }
    // Fail closed for nested indefinite column intrinsic-percent
    // dependencies. C01 permits a percentage basis with a measured leaf,
    // but not a percent-height descendant cycle.
    for index in 0..input.nodes.len(){
        let style=styles[index];
        if !matches!(style.direction,Direction::Column|Direction::ColumnReverse)
            || !matches!(style.height,Length::Auto){continue;}
        for &child in &children[index]{
            if !matches!(styles[child].basis,Length::Percent(_)){continue;}
            let mut pending=children[child].clone();
            while let Some(descendant)=pending.pop(){
                if matches!(styles[descendant].height,Length::Percent(_)){
                    return Err(unsupported(
                        "Unlisted column intrinsic percentage basis descendant cycle.",
                        &input.nodes[child].node_id,
                    ));
                }
                pending.extend(children[descendant].iter().copied());
            }
        }
    }
    // Parent-index traversal determines whether a percentage's containing
    // inline reference is actually definite, without depending on fixture IDs.
    fn definite_inline(
        node:usize,input:&LayoutInput,styles:&[Style],indices:&HashMap<&str,usize>,
        depth:usize,
    )->bool{
        if depth>input.nodes.len(){return false;}
        let Some(parent_name)=input.nodes[node].parent_id.as_deref() else{
            return input.constraints.width.definite
                || matches!(styles[node].width,Length::Px(_));
        };
        let parent=indices[parent_name];
        match styles[parent].width{
            Length::Px(_)=>true,
            Length::Percent(_)=>definite_inline(parent,input,styles,indices,depth+1),
            Length::Auto if styles[parent].grow>0.0 =>{
                if let Some(grand)=input.nodes[parent].parent_id.as_deref(){
                    let outer=indices[grand];
                    horizontal(styles[outer].direction)
                        && definite_inline(parent,input,styles,indices,depth+1)
                }else{false}
            },
            Length::Auto=>false,
        }
    }
    for index in 1..input.nodes.len(){
        if matches!(styles[index].width,Length::Percent(_))
            && !definite_inline(index,input,&styles,&indices,0){
            return Err(unsupported(
                "Unlisted indefinite inline percentage dependency cycle.",
                &input.nodes[index].node_id,
            ));
        }
    }
    // D-F1.13 / C01–C06: explicit allowlist for definitely referenced
    // percentages and measurable C05 block auto. Unknown graphs fail closed,
    // irrespective of fixture name; Python applies identical class/node ID.
    fn definite_block(
        node:usize,input:&LayoutInput,styles:&[Style],indices:&HashMap<&str,usize>,
        depth:usize,
    )->bool{
        if depth>input.nodes.len(){return false;}
        let Some(parent_name)=input.nodes[node].parent_id.as_deref() else{
            return input.constraints.height.definite || matches!(styles[node].height,Length::Px(_));
        };
        let parent=indices[parent_name];
        match styles[parent].height{
            Length::Px(_)=>true,
            Length::Percent(_)=>definite_block(parent,input,styles,indices,depth+1),
            Length::Auto=>false,
        }
    }
    // Blink cyclic percent inline padding: this precisely identified shape
    // contributes zero intrinsically and resolves percent only after the
    // auto-width wrapper's used content dimension is available. N06 and
    // unknown percentage graphs remain fail-closed.
    let cyclic_padding:Vec<bool>=(0..input.nodes.len()).map(|index|{
        let Some(parent_name)=input.nodes[index].parent_id.as_deref() else{return false;};
        let parent=indices[parent_name];
        let Some(outer_name)=input.nodes[parent].parent_id.as_deref() else{return false;};
        let outer=indices[outer_name];
        let (st,wrapper,container)=(styles[index],styles[parent],styles[outer]);
        children[index].is_empty() && children[parent].len()==1
            && children[parent][0]==index
            && matches!(st.width,Length::Px(_)) && matches!(st.basis,Length::Px(_))
            && matches!(wrapper.width,Length::Auto) && wrapper.shrink==0.0
            && horizontal(wrapper.direction) && horizontal(container.direction)
            && matches!(container.width,Length::Px(_))
            && matches!(st.padding_top,Length::Px(_))
            && matches!(st.padding_bottom,Length::Px(_))
            && (matches!(st.padding_left,Length::Percent(_))
                ||matches!(st.padding_right,Length::Percent(_)))
    }).collect();
    for index in 0..input.nodes.len(){
        let st=styles[index];
        let node=&input.nodes[index].node_id;
        let percentage_padding=[st.padding_top,st.padding_right,st.padding_bottom,st.padding_left]
            .iter().any(|v|matches!(v,Length::Percent(_)));
        if percentage_padding && !definite_inline(index,input,&styles,&indices,0) && !cyclic_padding[index]{
            return Err(unsupported("Unlisted indefinite inline percentage padding dependency cycle.",node));
        }
        if matches!(st.max_height,Length::Percent(_))
            && !definite_block(index,input,&styles,&indices,0){
            return Err(unsupported("Unlisted indefinite percentage maximum size dependency cycle.",node));
        }
        if matches!(st.height,Length::Percent(_))
            && !definite_block(index,input,&styles,&indices,0)
            && !input.measurements.iter().any(|measurement|measurement.node_id==*node){
            return Err(unsupported("Unmeasured indefinite percentage block dependency cycle.",node));
        }
    }
    let mut context=Context {
        input,styles,children,cyclic_padding,provisional,
        measurements:input.measurements.iter().map(|m|(m.node_id.as_str(),m)).collect(),
        used:vec![None;input.nodes.len()],
    };
    let root_style=context.styles[0];
    let width=resolved(root_style.width,
        input.constraints.width.value.filter(|_|input.constraints.width.definite),
        false,&input.nodes[0].node_id)?
        .or(input.constraints.width.value.filter(|_|input.constraints.width.definite));
    let height=resolved(root_style.height,
        input.constraints.height.value.filter(|_|input.constraints.height.definite),
        true,&input.nodes[0].node_id)?
        .or(input.constraints.height.value.filter(|_|input.constraints.height.definite));
    context.layout(0,width,height,None,None)?;
    let mut nodes=Vec::with_capacity(input.nodes.len());
    for (index,node) in input.nodes.iter().enumerate(){
        let (width,height)=context.used[index].ok_or(
            failure("SFLE_INVALID_SNAPSHOT","Incomplete node sizes.",Some(&node.node_id))
        )?;
        let st=context.styles[index];
        let mut item=None;
        if index>0 {
            let parent=indices[node.parent_id.as_deref().unwrap()];
            let h=horizontal(context.styles[parent].direction);
            let (main,cross)=if h{(width,height)}else{(height,width)};
            let parent_width=context.used[parent].unwrap().0;
            let resolved_padding=padding(st,parent_width,&node.node_id)?;
            let outer_st=context.styles[parent];
            let (top,right,bottom,left)=(
                margin_value(st.margin_top,parent_width),
                margin_value(st.margin_right,parent_width),
                margin_value(st.margin_bottom,parent_width),
                margin_value(st.margin_left,parent_width));
            let rtl=input.direction=="rtl";
            let reversed=matches!(outer_st.direction,Direction::RowReverse|Direction::ColumnReverse);
            let forward=if h{(!reversed)!=rtl}else{!reversed};
            let (main_start,main_end,cross_start,cross_end)=if h{
                (if forward{left}else{right},if forward{right}else{left},top,bottom)
            }else{
                (if forward{top}else{bottom},if forward{bottom}else{top},
                    if rtl{right}else{left},if rtl{left}else{right})
            };
            item=Some(MarginFlexItem {
                id:node.node_id.clone(),
                flex:FlexBasis {basis:main,hypothetical:main,grow:0.0,shrink:0.0,
                    min_size:0.0,max_size:None},
                cross_content_size:cross,
                edges:BoxEdges{padding:resolved_padding,..BoxEdges::default()},
                main_start,main_end,cross_start,cross_end,
                order:0,align_self:st.align_self,cross_size_auto:false,
                min_cross_content_size:0.0,max_cross_content_size:None,
                baseline_from_cross_start:None,
            });
        }
        nodes.push(MarginTreeNode {
            id:node.node_id.clone(),parent:node.parent_id.clone(),
            width,height,item,edges:BoxEdges::default(),
            direction:st.direction,wrap:st.wrap,
            main_gap:main_gap(st,width,height,&node.node_id)?,
            cross_gap:cross_gap(st,width,&node.node_id)?,
            justify:st.justify,align_items:st.align,
            align_content:st.align_content,intrinsic_basis:None,
        });
    }
    let writing=match input.direction.as_str(){"ltr"=>WritingDirection::Ltr,_=>WritingDirection::Rtl};
    let result=compute_margin_tree(&nodes,writing)
        .map_err(|e|failure("SFLE_LAYOUT_CONSTRAINT_ERROR",format!("Nested placement failed: {e:?}"),None))?;
    Ok(LayoutResult {
        schema_version:1,generation:input.generation,
        boxes:result.boxes.into_iter().map(|b|LayoutBox{
            node_id:b.id,content:converted(b.content),padding:converted(b.padding),
            border:converted(b.border),margin:converted(b.border),
        }).collect(),diagnostics:vec![],
        measurement_error:None,engine_error:None,geometry_commit_error:None,
    })
}
