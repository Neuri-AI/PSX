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
enum Length { Auto, Px(f64), Percent(f64), MinContent, MaxContent }
#[derive(Clone, Copy, PartialEq)]
enum Overflow { Visible, Clip, Hidden, Auto, Scroll }

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
    order: i32,
    min_width: Length,
    min_height: Length,
    align: CrossAlign,
    row_gap:Length,
    column_gap:Length,
    padding_top:Length,
    padding_right:Length,
    padding_bottom:Length,
    padding_left:Length,
    border_top:Length,
    border_right:Length,
    border_bottom:Length,
    border_left:Length,
    aspect_ratio:Option<f64>,
    overflow:Overflow,
    scroll_container:bool,
    replaced:bool,
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
fn css_decimal(raw:&str)->Option<f64>{
    // Match psx.sfle.lengths._PX_RE / _PERCENT_RE: no scientific
    // notation, internal whitespace, Infinity, NaN, or bare sign.
    let unsigned=raw.strip_prefix('+')
        .or_else(||raw.strip_prefix('-')).unwrap_or(raw);
    let mut parts=unsigned.split('.');
    let integer=parts.next()?;
    let fraction=parts.next();
    if parts.next().is_some() || !integer.bytes().all(|c|c.is_ascii_digit()){
        return None;
    }
    if let Some(decimal)=fraction {
        if !decimal.bytes().all(|c|c.is_ascii_digit())
            || (integer.is_empty() && decimal.is_empty()){
            return None;
        }
    } else if integer.is_empty() {
        return None;
    }
    raw.parse::<f64>().ok().filter(|value|value.is_finite())
}
fn length(raw: Option<&Value>, id: &str) -> Result<Length, ComputeError> {
    let Some(v) = raw else { return Ok(Length::Auto) };
    if let Some(n)=v.as_f64() {
        if !n.is_finite() { return Err(failure("SFLE_INVALID_LENGTH","Length payload must be finite.",Some(id))); }
        return Ok(Length::Px(n));
    }
    if let Some(original) = v.as_str() {
        let normalized=original.trim().to_ascii_lowercase();
        let s=normalized.as_str();
        if s=="auto" { return Ok(Length::Auto); }
        if s=="min-content" { return Ok(Length::MinContent); }
        if s=="max-content" { return Ok(Length::MaxContent); }
        if let Some(n) = s.strip_suffix("px").and_then(css_decimal) {
            if n.is_finite(){return Ok(Length::Px(n));}
        }
        if let Some(n) = s.strip_suffix('%').and_then(css_decimal) {
            if n.is_finite(){return Ok(Length::Percent(n/100.0));}
        }
    }
    if let Some(map) = v.as_object() {
        let kind=map.get("kind").and_then(Value::as_str);
        let number=map.get("value").and_then(Value::as_f64);
        match kind {
            Some("auto") if map.get("value").is_none_or(Value::is_null) => return Ok(Length::Auto),
            Some("min-content") if map.get("value").is_none_or(Value::is_null) => return Ok(Length::MinContent),
            Some("max-content") if map.get("value").is_none_or(Value::is_null) => return Ok(Length::MaxContent),
            Some("px") if number.is_some_and(f64::is_finite) =>return Ok(Length::Px(number.unwrap())),
            Some("percent") if number.is_some_and(f64::is_finite) =>return Ok(Length::Percent(number.unwrap())),
            _=>{},
        }
    }
    Err(unsupported("Unsupported CSS length keyword or expression.", id))
}
fn factor(raw: Option<&Value>, default: f64, id:&str)->Result<f64,ComputeError>{
    let n=match raw {None=>default,Some(value)=>value.as_f64().unwrap_or(f64::NAN)};
    if !n.is_finite()||n<0.0 {
        return Err(failure("SFLE_INVALID_LENGTH","Invalid flex factors.",Some(id)));
    }
    Ok(n)
}
fn enum_raw<'a>(
    map:&'a serde_json::Map<String,Value>,key:&str,
    default:&'a str,id:&str,
)->Result<&'a str,ComputeError>{
    match map.get(key){
        None=>Ok(default),
        Some(Value::String(s))=>Ok(s.as_str()),
        Some(_)=>Err(unsupported(format!("Unsupported {key} value."),id)),
    }
}
fn style(input:&crate::compute::LayoutNode)->Result<Style,ComputeError>{
    let map=&input.style;
    let mut unknown=Vec::new();
    for key in map.keys(){
        if !matches!(key.as_str(),"direction"|"width"|"height"|"layout_width"|"layout_height"|
            "flex_basis"|"flex_grow"|"flex_shrink"|"min_width"|"min_height"|
            "order"|
            "layout_min_width"|"layout_min_height"|"align_items"|
            "wrap"|"justify_content"|"align_content"|"align_self"|
            "max_width"|"max_height"|"layout_max_width"|"layout_max_height"|
            "layout_margin_top"|"layout_margin_right"|"layout_margin_bottom"|"layout_margin_left"|
            "row_gap"|"column_gap"|
            "layout_padding_top"|"layout_padding_right"|
            "layout_padding_bottom"|"layout_padding_left"|
            "layout_border_top"|"layout_border_right"|"layout_border_bottom"|"layout_border_left"|
            "aspect_ratio"|"overflow"|"scroll_container"|"replaced"){
            unknown.push(key.as_str());
        }
    }
    if !unknown.is_empty(){
        unknown.sort_unstable();
        let names=unknown.iter().map(|name|format!("'{name}'")).collect::<Vec<_>>().join(", ");
        return Err(unsupported(format!("Unimplemented CSS style properties: [{names}]."),&input.node_id));
    }
    if map.contains_key("width")&&map.contains_key("layout_width") {
        return Err(failure("SFLE_LAYOUT_CONSTRAINT_ERROR","Conflicting width declarations.",Some(&input.node_id)));
    }
    if map.contains_key("height")&&map.contains_key("layout_height") {
        return Err(failure("SFLE_LAYOUT_CONSTRAINT_ERROR","Conflicting height declarations.",Some(&input.node_id)));
    }
    let direction=match enum_raw(map,"direction","row",&input.node_id)?{
        "row"=>Direction::Row,"row-reverse"=>Direction::RowReverse,
        "column"=>Direction::Column,"column-reverse"=>Direction::ColumnReverse,
        _=>return Err(unsupported("Unsupported direction value.",&input.node_id)),
    };
    let parse_align=|k:&str,default:&str| -> Result<CrossAlign,ComputeError> {
        match enum_raw(map,k,default,&input.node_id)? {
            "stretch"=>Ok(CrossAlign::Stretch),"flex-start"=>Ok(CrossAlign::FlexStart),
            "flex-end"=>Ok(CrossAlign::FlexEnd),"center"=>Ok(CrossAlign::Center),
            "baseline"=>Ok(CrossAlign::Baseline),
            "auto" if k=="align_self"=>Ok(CrossAlign::Auto),
            _=>Err(unsupported(format!("Unsupported {k} value."),&input.node_id)),
        }
    };
    let align=parse_align("align_items","stretch")?;
    let align_self=parse_align("align_self","auto")?;
    let wrap=match enum_raw(map,"wrap","nowrap",&input.node_id)?{
        "nowrap"=>Wrap::NoWrap,"wrap"=>Wrap::Wrap,"wrap-reverse"=>Wrap::WrapReverse,
        _=>return Err(unsupported("Unsupported wrap value.",&input.node_id)),
    };
    let justify=match enum_raw(map,"justify_content","flex-start",&input.node_id)?{
        "flex-start"=>JustifyContent::FlexStart,"flex-end"=>JustifyContent::FlexEnd,
        "center"=>JustifyContent::Center,"space-between"=>JustifyContent::SpaceBetween,
        "space-around"=>JustifyContent::SpaceAround,"space-evenly"=>JustifyContent::SpaceEvenly,
        _=>return Err(unsupported("Unsupported justify-content value.",&input.node_id)),
    };
    let align_content=match enum_raw(map,"align_content","normal",&input.node_id)?{
        "normal"|"stretch"=>AlignContent::Stretch,
        "flex-start"=>AlignContent::FlexStart,"flex-end"=>AlignContent::FlexEnd,
        "center"=>AlignContent::Center,"space-between"=>AlignContent::SpaceBetween,
        "space-around"=>AlignContent::SpaceAround,"space-evenly"=>AlignContent::SpaceEvenly,
        _=>return Err(unsupported("Unsupported align-content value.",&input.node_id)),
    };
    let aspect_ratio=match map.get("aspect_ratio") {
        None=>None,
        Some(value)=>{
            let ratio=value.as_f64().ok_or_else(||failure(
                "SFLE_INVALID_LENGTH","aspect_ratio must be a positive finite number.",Some(&input.node_id)))?;
            if !ratio.is_finite()||ratio<=0.0 {
                return Err(failure("SFLE_INVALID_LENGTH","aspect_ratio must be a positive finite number.",Some(&input.node_id)));
            }
            Some(ratio)
        },
    };
    let overflow=match enum_raw(map,"overflow","visible",&input.node_id)? {
        "visible"=>Overflow::Visible,"clip"=>Overflow::Clip,"hidden"=>Overflow::Hidden,
        "auto"=>Overflow::Auto,"scroll"=>Overflow::Scroll,
        _=>return Err(unsupported("Unsupported overflow value.",&input.node_id)),
    };
    let scroll_container=match map.get("scroll_container") {
        None=>overflow==Overflow::Scroll,
        Some(Value::Bool(value))=>*value,
        _=>return Err(failure("SFLE_INVALID_LENGTH","scroll_container must be boolean.",Some(&input.node_id))),
    };
    if scroll_container && overflow!=Overflow::Auto && overflow!=Overflow::Scroll {
        return Err(failure("SFLE_LAYOUT_CONSTRAINT_ERROR","scroll_container requires overflow auto or scroll.",Some(&input.node_id)));
    }
    let replaced=match map.get("replaced") {
        None=>input.component=="Image",
        Some(Value::Bool(value))=>*value,
        _=>return Err(failure("SFLE_INVALID_LENGTH","replaced must be boolean.",Some(&input.node_id))),
    };
    let order=match map.get("order") {
        None=>0,
        Some(value)=>{
            let raw=value.as_i64().ok_or_else(||failure(
                "SFLE_INVALID_LENGTH","order must be a signed integer.",Some(&input.node_id)))?;
            i32::try_from(raw).map_err(|_|failure(
                "SFLE_INVALID_LENGTH","order is outside the supported signed range.",Some(&input.node_id)))?
        },
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
        border_top:if map.contains_key("layout_border_top"){length(map.get("layout_border_top"),&input.node_id)?}else{Length::Px(0.0)},
        border_right:if map.contains_key("layout_border_right"){length(map.get("layout_border_right"),&input.node_id)?}else{Length::Px(0.0)},
        border_bottom:if map.contains_key("layout_border_bottom"){length(map.get("layout_border_bottom"),&input.node_id)?}else{Length::Px(0.0)},
        border_left:if map.contains_key("layout_border_left"){length(map.get("layout_border_left"),&input.node_id)?}else{Length::Px(0.0)},
        width:length(value(map,&["layout_width","width"]),&input.node_id)?,
        height:length(value(map,&["layout_height","height"]),&input.node_id)?,
        basis:length(map.get("flex_basis"),&input.node_id)?,
        grow:factor(map.get("flex_grow"),0.0,&input.node_id)?,
        shrink:factor(map.get("flex_shrink"),1.0,&input.node_id)?,
        order,
        min_width:length(value(map,&["layout_min_width","min_width"]),&input.node_id)?,
        min_height:length(value(map,&["layout_min_height","min_height"]),&input.node_id)?,
        aspect_ratio,
        overflow,
        scroll_container,
        replaced,
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
fn percent_used_dimension(fraction:f64,reference:f64)->f64 {
    let value=fraction*reference;
    let stable=if value.is_finite()&&value>=0.0 {
        f64::from_bits(value.to_bits()+1)
    } else {value};
    if stable.is_infinite(){
        return LayoutUnit::from_raw(if stable.is_sign_positive(){i32::MAX}else{i32::MIN}).to_px();
    }
    LayoutUnit::from_floor(stable).expect("prevalidated finite CSS percentage").to_px()
}
fn percent_flex_basis_used(fraction:f64,reference:f64)->f64 {
    let used=fraction*reference;
    if used.is_infinite(){
        return LayoutUnit::from_raw(if used.is_sign_positive(){i32::MAX}else{i32::MIN}).to_px();
    }
    LayoutUnit::from_floor(used)
        .expect("SFLE prevalidated finite percentage").to_px()
}
fn saturating_gutter_product(gutter:LayoutUnit, count:usize)->LayoutUnit{
    // A usize count must never narrow to i32 before multiplying the
    // signed raw gap: even the unsupported >2^31-node extreme must not wrap.
    let raw=(gutter.raw() as i128)*(count as i128);
    LayoutUnit::from_raw(raw.clamp(i32::MIN as i128,i32::MAX as i128) as i32)
}
fn blink_flex_targets(bases:&[FlexBasis], inner:f64,gap:f64,id:&str)->Result<Vec<f64>,ComputeError>{
    // Exact port of Chromium 153 line_flexer.cc:
    // FreezeItems + ResolveFlexibleLengths. Integer LayoutUnit for all
    // free-space subtractions, used sizes, clamping and repeated violations.
    // f64 only for cumulative flex factors / weighted shrink fractions.
    if bases.is_empty(){return Ok(vec![]);}
    let raw=|v:f64| LayoutUnit::from_nearest(v).map_err(|e|unsupported(e,id));
    let finite_factor=|value:f64|->Result<f64,ComputeError>{
        if value.is_finite(){Ok(value)}else{
            Err(unsupported("Flex factor accumulation exceeds finite f64 range.",id))
        }
    };
    let available=raw(inner)?;
    let gutter=raw(gap)?;
    let base:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.basis)).collect::<Result<_,_>>()?;
    let hypot:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.hypothetical)).collect::<Result<_,_>>()?;
    let min:Vec<LayoutUnit>=bases.iter().map(|b|raw(b.min_size)).collect::<Result<_,_>>()?;
    let max:Vec<Option<LayoutUnit>>=bases.iter().map(|b|b.max_size.map(&raw).transpose())
        .collect::<Result<_,_>>()?;
    let usable=available-saturating_gutter_product(gutter,bases.len().saturating_sub(1));
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
            total_factor=finite_factor(total_factor+factor)?;
            if growing{
                fractions[i]=finite_factor(factor/total_factor)?;
            }else{
                let weighted=finite_factor(factor*base[i].to_px())?;
                total_scaled_shrink=finite_factor(total_scaled_shrink+weighted)?;
                fractions[i]=if total_scaled_shrink==0.0{0.0}
                    else{finite_factor(weighted/total_scaled_shrink)?};
            }
            remaining=remaining-base[i]-gutter;
        }
        remaining=remaining+gutter;
        if round==0{initial_free=remaining;}
        if total_factor>0.0 && total_factor<1.0 {
            let fraction=LayoutUnit::from_trunc(initial_free.to_px()*total_factor)
                .map_err(|e|unsupported(e,id))?;
            // i32::MIN.abs() overflows in debug and wraps in release.
            // Widen before abs to preserve Python's unbounded signed
            // comparison at the exact -2^31 LayoutUnit boundary.
            if (fraction.raw() as i64).abs() < (remaining.raw() as i64).abs() {
                remaining=fraction;
            }
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
fn resolved(v:Length, reference:Option<f64>, _vertical:bool, _id:&str)->Result<Option<f64>,ComputeError>{
    match v {
        Length::Auto|Length::MinContent|Length::MaxContent=>Ok(None),
        Length::Px(n)=>Ok(Some(n)),
        Length::Percent(p) if reference.is_some()=>Ok(Some(percent_used_dimension(p,reference.unwrap()))),
        // An intrinsically indefinite percentage has no used numeric value
        // in this phase. Flex sizing uses the auto/content branch and calls
        // this again after the containing axis becomes definite.
        Length::Percent(_)=>Ok(None),
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
                if stable.is_infinite(){
                    Ok(LayoutUnit::from_raw(if stable.is_sign_positive(){i32::MAX}else{i32::MIN}).to_px())
                }else{
                    LayoutUnit::from_floor(stable).map(|n|n.to_px())
                        .map_err(|e|unsupported(e,id))
                }
            },
            Length::Auto|Length::MinContent|Length::MaxContent=>Err(failure("SFLE_INVALID_LENGTH","Padding requires a valid numeric CSS length.",Some(id))),
        }
    }
    Ok(Edges{
        top:edge(style.padding_top,inline_reference,id)?,
        right:edge(style.padding_right,inline_reference,id)?,
        bottom:edge(style.padding_bottom,inline_reference,id)?,
        left:edge(style.padding_left,inline_reference,id)?,
    })
}
fn border(style:Style,id:&str)->Result<Edges,ComputeError>{
    fn edge(value:Length,id:&str)->Result<f64,ComputeError>{
        match value {
            Length::Px(value) if value>=0.0=>Ok(layout_unit(value)),
            _=>Err(failure("SFLE_INVALID_LENGTH","Borders require nonnegative pixel lengths.",Some(id))),
        }
    }
    Ok(Edges{top:edge(style.border_top,id)?,right:edge(style.border_right,id)?,
             bottom:edge(style.border_bottom,id)?,left:edge(style.border_left,id)?})
}
fn intrinsic_gap(length:Length,id:&str)->Result<f64,ComputeError>{
    match length{
        Length::Px(n)=>Ok(n),
        Length::Percent(_)=>Ok(0.0), // intrinsic contribution only
        Length::Auto|Length::MinContent|Length::MaxContent=>Err(failure("SFLE_INVALID_LENGTH","Invalid gap keyword.",Some(id))),
    }
}
fn used_gap(length:Length,reference:f64,id:&str)->Result<f64,ComputeError>{
    intrinsic_gap(length,id)?;
    match length{
        Length::Px(n)=>Ok(n),
        Length::Percent(p)=>{
            let used=p*reference;
            if used.is_infinite(){
                Ok(LayoutUnit::from_raw(if used.is_sign_positive(){i32::MAX}else{i32::MIN}).to_px())
            }else{
                LayoutUnit::from_nearest(used).map(|unit|unit.to_px())
                    .map_err(|e|unsupported(e,id))
            }
        },
        Length::Auto|Length::MinContent|Length::MaxContent=>Err(failure("SFLE_INVALID_LENGTH","Invalid gap.",Some(id))),
    }
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
    measurements:HashMap<&'a str,&'a crate::compute::MeasuredBox>,
    used:Vec<Option<(f64,f64)>>,
    reused_sizes:Vec<Option<(f64,f64)>>,
    reusable_descendants:Vec<Vec<usize>>,
}
fn bounded_intrinsic(style:Style,h:bool,mut value:f64,reference:Option<f64>)->f64{
    // Minimum precedence wins over a conflicting maximum. Percentage bounds
    // resolve only against a definite containing-block axis.
    let maximum=if h{style.max_width}else{style.max_height};
    let minimum=if h{style.min_width}else{style.min_height};
    let bound=|v:Length|match v {
        Length::Px(n)=>Some(layout_unit(n)),
        Length::Percent(p)=>reference.map(|r|percent_used_dimension(p,r)),
        Length::Auto|Length::MinContent|Length::MaxContent=>None,
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
        let sizing=if h {style.width}else{style.height};
        let minimum=match sizing {
            Length::MinContent=>true,
            Length::MaxContent=>false,
            _=>minimum,
        };
        if let Length::Px(n)=sizing {
            return Ok(bounded_intrinsic(style,h,n,None));
        }
        if self.children[index].is_empty(){
            if let Some(m)=self.measurements.get(node.node_id.as_str()){
                let value = if minimum {
                    if h {m.intrinsic.min_content_width} else {m.intrinsic.min_content_height}
                } else if matches!(sizing,Length::MaxContent) {
                    if h {m.intrinsic.max_content_width} else {m.intrinsic.max_content_height}
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
                    Length::Percent(_) => {},
                    _ => return Err(unsupported("Invalid intrinsic padding length.",
                        &self.input.nodes[child].node_id)),
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
        if let (Some(w),Some(h),Some((prior_w,prior_h)))=
            (forced_w,forced_h,self.reused_sizes[index]) {
            if (w-prior_w).abs() <= 1.0/64.0 && (h-prior_h).abs() <= 1.0/64.0 {
                for &descendant in &self.reusable_descendants[index] {
                    self.used[descendant]=self.reused_sizes[descendant];
                }
                return Ok((prior_w,prior_h));
            }
        }
        let mut width=forced_w.or(resolved(style.width,pw,false,&id)?);
        let mut height=forced_h.or(resolved(style.height,ph,true,&id)?);
        if style.wrap!=Wrap::NoWrap && (
            (horizontal(style.direction) && width.is_none()
                && !matches!(style.max_width,Length::Px(_)))
            || (!horizontal(style.direction) && height.is_none()
                && !matches!(style.max_height,Length::Px(_)))
        ){
            return Err(unsupported(
                "Intrinsically auto-sized Flex wrap without definite main axis is deferred.",
                &id,
            ));
        }
        if width.is_none() && height.is_some() && style.aspect_ratio.is_some() {
            width=Some(layout_unit(height.unwrap()*style.aspect_ratio.unwrap()));
        }
        if height.is_none() && width.is_some() && style.aspect_ratio.is_some() {
            height=Some(layout_unit(width.unwrap()/style.aspect_ratio.unwrap()));
        }
        if self.children[index].is_empty(){
            if width.is_none(){width=Some(self.preferred(index,true)?);}
            if height.is_none(){
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
        // Resolve the flex main axis first.  The auto cross axis must come
        // from the completed lines, including wrapped column lines.
        if row && width.is_none(){width=Some(self.preferred(index,true)?);}
        if !row && height.is_none(){height=Some(self.preferred(index,false)?);}
        width=width.map(|v|bounded_intrinsic(style,true,v,pw));
        height=height.map(|v|bounded_intrinsic(style,false,v,ph));
        let main=if row{width.unwrap()}else{height.unwrap()};
        let main_reference=if (row&&matches!(style.width,Length::Auto|Length::MinContent|Length::MaxContent)&&forced_w.is_none())||
                              (!row&&matches!(style.height,Length::Auto|Length::MinContent|Length::MaxContent)&&forced_h.is_none()){
            None
        }else{Some(main)};
        // CSS `order` establishes the flex order used for line formation as
        // well as placement.  Keep the source index as the stable tie-breaker
        // (the same rule used by the margin geometry compositor).
        let mut child_indices=self.children[index].clone();
        child_indices.sort_by_key(|&child|(self.styles[child].order,child));
        let mut bases=Vec::with_capacity(child_indices.len());
        for &child in &child_indices{
            let child_style=self.styles[child];
            let child_id=&self.input.nodes[child].node_id;
            let axis=if row{child_style.width}else{child_style.height};
            let cross_axis=if row{child_style.height}else{child_style.width};
            let cross_reference=if row{height}else{width};
            let mut transfer_cross=resolved(cross_axis,cross_reference,row,child_id)?;
            let alignment=if child_style.align_self==CrossAlign::Auto{style.align}else{child_style.align_self};
            if transfer_cross.is_none() && cross_reference.is_some() && style.wrap==Wrap::NoWrap
                && alignment==CrossAlign::Stretch {
                transfer_cross=cross_reference;
            }
            if transfer_cross.is_none() && child_style.aspect_ratio.is_some() {
                if let Some(metric)=self.measurements.get(child_id.as_str()) {
                    transfer_cross=Some(if row {metric.intrinsic.preferred_height}
                        else {metric.intrinsic.preferred_width});
                }
            }
            if let Some(cross)=transfer_cross {
                transfer_cross=Some(bounded_intrinsic(
                    child_style,!row,cross,cross_reference,
                ));
            }
            let transferred=transfer_cross.zip(child_style.aspect_ratio).map(|(cross,ratio)|
                layout_unit(if row{cross*ratio}else{cross/ratio})
            );
            let desired=match child_style.basis{
                Length::Auto=>match resolved(axis,main_reference,!row,child_id)? {
                    Some(value)=>value,
                    None=>match transferred {
                        Some(value)=>value,
                        None=>self.preferred(child,row)?,
                    },
                },
                Length::Px(n)=>n,
                Length::Percent(p)=>match main_reference{
                    Some(n)=>percent_flex_basis_used(p,n),None=>self.preferred(child,row)?,
                },
                Length::MinContent|Length::MaxContent=>{
                    if self.children[child].is_empty() {
                        let Some(metric)=self.measurements.get(child_id.as_str()) else {
                            return Err(measurement("Intrinsic flex basis requires measured leaf content.",child_id));
                        };
                        let min=matches!(child_style.basis,Length::MinContent);
                        if row {
                            if min {metric.intrinsic.min_content_width} else {metric.intrinsic.max_content_width}
                        }else if min {metric.intrinsic.min_content_height}
                            else {metric.intrinsic.max_content_height}
                    } else {
                        self.intrinsic_contribution(child,row,matches!(child_style.basis,Length::MinContent))?
                    }
                },
            };
            let mut minimum=match if row{child_style.min_width}else{child_style.min_height}{
                Length::Px(n)=>n,
                Length::Auto=>{
                    let mut content=if child_style.scroll_container {0.0}
                        else {self.intrinsic_contribution(child,row,true)?};
                    if let Some(transferred)=transferred {
                        content=if child_style.replaced {
                            content.min(transferred)
                        } else {content.max(transferred)};
                    }
                    resolved(axis,main_reference,!row,child_id)?.map_or(content,|n|content.min(n))
                },
                Length::Percent(p) if main_reference.is_some()=>percent_used_dimension(p,main_reference.unwrap()),
                Length::Percent(_)=>{
                    let mut content=if child_style.scroll_container {0.0}
                        else {self.intrinsic_contribution(child,row,true)?};
                    if let Some(transferred)=transferred {
                        content=if child_style.replaced {
                            content.min(transferred)
                        } else {content.max(transferred)};
                    }
                    content
                },
                Length::MinContent|Length::MaxContent=>{
                    return Err(unsupported("Intrinsic min-size keyword not yet certified.",child_id));
                },
            };
            let mut maximum=match if row{child_style.max_width}else{child_style.max_height}{
                Length::Px(n)=>Some(n),Length::Auto=>None,
                Length::Percent(p) if main_reference.is_some()=>Some(percent_used_dimension(p,main_reference.unwrap())),
                Length::Percent(_)=>None,
                Length::MinContent|Length::MaxContent=>{
                    return Err(unsupported("Intrinsic max-size keyword not yet certified.",child_id));
                },
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
        let inline_size=width.unwrap_or(0.0);
        let gap=layout_unit(main_gap(style,inline_size,height.unwrap_or(0.0),&id)?);
        let edges=child_indices.iter().map(|&child| Ok(BoxEdges{
            padding:padding(self.styles[child],inline_size,&self.input.nodes[child].node_id)?,
            border:border(self.styles[child],&self.input.nodes[child].node_id)?,
            ..BoxEdges::default()
        })
        ).collect::<Result<Vec<_>,ComputeError>>()?;
        let fixed_margin=|length|margin_value(length,inline_size).unwrap_or(0.0);
        let fixed_edges:Vec<f64>=child_indices.iter().zip(&edges).map(|(&child,e)|{
            let s=self.styles[child];
            if row {sum_units([e.padding.left,e.padding.right,e.border.left,e.border.right,fixed_margin(s.margin_left),fixed_margin(s.margin_right)])}
            else {sum_units([e.padding.top,e.padding.bottom,e.border.top,e.border.bottom,fixed_margin(s.margin_top),fixed_margin(s.margin_bottom)])}
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
                    cross=Some(subtract_units(height.unwrap(),[padding_box.padding.top,padding_box.padding.bottom,padding_box.border.top,padding_box.border.bottom,
                        fixed_margin(child_style.margin_top),fixed_margin(child_style.margin_bottom)]).max(0.0));
                }
                self.layout(child,Some(target),cross,width,height)?
            }else{
                let mut cross=resolved(child_style.width,width,false,&child_id)?;
                let align=if child_style.align_self==CrossAlign::Auto{style.align}else{child_style.align_self};
                if cross.is_none()&&width.is_some()&&align==CrossAlign::Stretch&&style.wrap==Wrap::NoWrap
                    &&!matches!(child_style.margin_left,Length::Auto)
                    &&!matches!(child_style.margin_right,Length::Auto){
                    cross=Some(subtract_units(width.unwrap(),[padding_box.padding.left,padding_box.padding.right,padding_box.border.left,padding_box.border.right,
                        fixed_margin(child_style.margin_left),fixed_margin(child_style.margin_right)]).max(0.0));
                }
                self.layout(child,cross,Some(target),width,height)?
            };
            // CSS auto cross contribution is the entire child padding box,
            // not merely the content size returned by recursive layout.
            cross_sizes.push(if row{sum_units([ch,padding_box.padding.top,padding_box.padding.bottom,padding_box.border.top,padding_box.border.bottom,
                fixed_margin(child_style.margin_top),fixed_margin(child_style.margin_bottom)]).max(0.0)}
                else{sum_units([cw,padding_box.padding.left,padding_box.padding.right,padding_box.border.left,padding_box.border.right,
                    fixed_margin(child_style.margin_left),fixed_margin(child_style.margin_right)]).max(0.0)});
        }
        if (row && height.is_none()) || (!row && width.is_none()){
            // Apply cross min/max only after recursive auto sizing has used
            // every line's outer contribution.  This is symmetric for
            // row-height and column-width auto cross sizing.
            let cross_gap=intrinsic_gap(if row{style.row_gap}else{style.column_gap},&id)?;
            let mut auto_cross=0.0;
            for (i,line) in lines.iter().enumerate(){
                let size=line.iter().map(|&i|cross_sizes[i]).fold(0.0_f64,f64::max);
                auto_cross=sum_units([auto_cross,if i>0{cross_gap}else{0.0},size]);
            }
            if row {height=Some(bounded_intrinsic(style,false,auto_cross,ph));}
            else {width=Some(bounded_intrinsic(style,true,auto_cross,pw));}
        }
        let dims=(layout_unit(width.unwrap()),layout_unit(height.unwrap()));
        self.used[index]=Some(dims);
        Ok(dims)
    }
}
fn margin_value(v:Length,base:f64)->Option<f64>{
    match v{Length::Auto|Length::MinContent|Length::MaxContent=>None,
        Length::Px(n)=>Some(layout_unit(n)),
        Length::Percent(p)=>{
            let used=p*base;
            if used.is_infinite(){
                Some(LayoutUnit::from_raw(if used.is_sign_positive(){i32::MAX}else{i32::MIN}).to_px())
            }else{
                Some(layout_unit(used))
            }
        }}
}
fn cross_gap(st:Style,width:f64,id:&str)->Result<f64,ComputeError>{
    used_gap(if horizontal(st.direction){st.row_gap}else{st.column_gap},width,id)
}
fn converted(r:crate::line_layout::Rect)->Rect{
    Rect{x:r.x,y:r.y,width:r.width,height:r.height}
}
pub fn compute_normalized(input:&LayoutInput,provisional:bool)->Result<LayoutResult,ComputeError>{
    compute_normalized_incremental(input, provisional, None)
}

pub fn compute_normalized_incremental(
    input:&LayoutInput, provisional:bool,
    previous:Option<(&LayoutInput,&LayoutResult)>,
)->Result<LayoutResult,ComputeError>{
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
    // Point-5 deferral: an unmeasured replaced ratio leaf with two auto
    // dimensions cannot guess a transferred size unless cross stretch exists.
    for (index,node) in input.nodes.iter().enumerate().skip(1) {
        let st=styles[index];
        if !(st.replaced && st.aspect_ratio.is_some()
            && matches!(st.width,Length::Auto)
            && matches!(st.height,Length::Auto)
            && !input.measurements.iter().any(|m|m.node_id==node.node_id)) {
            continue;
        }
        let parent=indices[node.parent_id.as_ref().unwrap().as_str()];
        let parent_style=styles[parent];
        let align=if st.align_self==CrossAlign::Auto{
            parent_style.align
        }else{st.align_self};
        if align!=CrossAlign::Stretch{
            return Err(unsupported(
                "Replaced intrinsic aspect-ratio sizing without native measurement is deferred.",
                &node.node_id,
            ));
        }
    }
    // Convert min/max-content constraint keywords bottom-up. Recursive
    // intrinsic inline sizing is supported only for certified column cross
    // contributions; unknown direction, percentage and relative-edge graphs
    // fail closed with an explicit diagnostic.
    fn intrinsic_flex_width(
        index:usize, minimum:bool, nodes:&[crate::compute::LayoutNode],
        children:&[Vec<usize>], styles:&[Style],
        measurements:&[crate::compute::MeasuredBox],
    )->Result<f64,ComputeError>{
        let id=&nodes[index].node_id;
        if children[index].is_empty(){
            if let Some(metric)=measurements.iter().find(|m|m.node_id==*id){
                return Ok(layout_unit(if minimum {
                    metric.intrinsic.min_content_width
                } else {metric.intrinsic.max_content_width}));
            }
            if nodes[index].component=="Text" {
                return Err(measurement("Intrinsic constraint requires measured text.",id));
            }
            return Ok(0.0);
        }
        let row=horizontal(styles[index].direction);
        if row && !matches!(styles[index].wrap,Wrap::NoWrap){
            return Err(unsupported(
                "Recursive row intrinsic constraint requires no-wrap.",id,
            ));
        }
        if row && children[index].iter().any(|&child|{
            let s=styles[child];
            s.shrink!=0.0 && (
                minimum || !matches!(s.width,Length::Px(_))
                || !matches!(s.basis,Length::Px(_))
                || !matches!(s.min_width,Length::Px(_))
            )
        }){
            return Err(unsupported(
                "Shrinking row max-content requires definite item width, basis and minimum.",id,
            ));
        }
        let mut greatest=0.0_f64;
        let mut total=0.0_f64;
        for (child_index,&child) in children[index].iter().enumerate() {
            let style=styles[child];
            let child_id=&nodes[child].node_id;
            let mut width=match style.width {
                Length::Px(v)=>layout_unit(v),
                Length::Auto|Length::MinContent|Length::MaxContent=>
                    intrinsic_flex_width(child,minimum,nodes,children,styles,measurements)?,
                _=>return Err(unsupported(
                    "Uncertified percentage dependency in recursive intrinsic constraint.",child_id,
                )),
            };
            match style.max_width {
                Length::Px(n)=>width=width.min(layout_unit(n)),
                Length::Auto=>{},
                _=>return Err(unsupported(
                    "Unresolved intrinsic maximum in recursive child.",child_id,
                )),
            }
            match style.min_width {
                Length::Px(n)=>width=width.max(layout_unit(n)),
                Length::Auto=>{},
                _=>return Err(unsupported(
                    "Unresolved intrinsic minimum in recursive child.",child_id,
                )),
            }
            let mut fixed=0.0_f64;
            for edge in [style.padding_left,style.padding_right,
                style.border_left,style.border_right,
                style.margin_left,style.margin_right] {
                match edge {
                    Length::Px(n)=>fixed=sum_units([fixed,n]),
                    Length::Auto=>{},
                    _=>return Err(unsupported(
                        "Uncertified relative edges in recursive intrinsic constraint.",
                        child_id,
                    )),
                }
            }
            let outer=sum_units([width,fixed]);
            greatest=greatest.max(outer);
            if row {
                let gap=match styles[index].column_gap {
                    Length::Px(n)=>n,
                    _=>return Err(unsupported(
                        "Recursive row intrinsic gap must be definite.",id,
                    )),
                };
                total=sum_units([total,if child_index==0 {0.0} else {gap},outer]);
            }
        }
        Ok(if row{total}else{greatest})
    }
    fn intrinsic_flex_height(
        index:usize,minimum:bool,nodes:&[crate::compute::LayoutNode],
        children:&[Vec<usize>],styles:&[Style],
        measurements:&[crate::compute::MeasuredBox],
    )->Result<f64,ComputeError>{
        let id=&nodes[index].node_id;
        if children[index].is_empty(){
            if let Some(metric)=measurements.iter().find(|m|m.node_id==*id){
                return Ok(layout_unit(if minimum{
                    metric.intrinsic.min_content_height
                }else{metric.intrinsic.max_content_height}));
            }
            if nodes[index].component=="Text"{
                return Err(measurement(
                    "Intrinsic block constraint requires measured text.",id,
                ));
            }
            return Ok(0.0);
        }
        let column=!horizontal(styles[index].direction);
        let mut contributions=Vec::with_capacity(children[index].len());
        for &child_index in &children[index]{
            let child=styles[child_index];
            let child_id=&nodes[child_index].node_id;
            if column && child.shrink!=0.0{
                return Err(unsupported(
                    "Recursive intrinsic column block sizing requires nonshrinking items.",
                    child_id,
                ));
            }
            let mut height=match child.height{
                Length::Px(n)=>layout_unit(n),
                Length::Auto|Length::MinContent|Length::MaxContent=>
                    intrinsic_flex_height(child_index,minimum,nodes,children,styles,measurements)?,
                _=>return Err(unsupported(
                    "Uncertified percentage block dependency in intrinsic constraint.",
                    child_id,
                )),
            };
            match child.max_height{
                Length::Px(n)=>height=height.min(layout_unit(n)),
                Length::Auto=>{},
                _=>return Err(unsupported(
                    "Unresolved intrinsic maximum block size.",child_id,
                )),
            }
            match child.min_height{
                Length::Px(n)=>height=height.max(layout_unit(n)),
                Length::Auto=>{},
                _=>return Err(unsupported(
                    "Unresolved intrinsic minimum block size.",child_id,
                )),
            }
            for edge in [
                child.padding_top,child.padding_bottom,
                child.border_top,child.border_bottom,
                child.margin_top,child.margin_bottom,
            ] {
                match edge{
                    Length::Px(n)=>height=sum_units([height,n]),
                    Length::Auto=>{},
                    _=>return Err(unsupported(
                        "Uncertified relative block edges in intrinsic constraint.",
                        child_id,
                    )),
                }
            }
            contributions.push(height);
        }
        if !column{
            return Ok(contributions.into_iter().fold(0.0_f64,f64::max));
        }
        let gap=match styles[index].row_gap{
            Length::Px(n)=>n,
            _=>return Err(unsupported(
                "Recursive intrinsic column gap must be definite.",id,
            )),
        };
        let mut total=0.0;
        for (i,height) in contributions.into_iter().enumerate(){
            total=sum_units([total,if i==0{0.0}else{gap},height]);
        }
        Ok(total)
    }
    for index in (0..input.nodes.len()).rev() {
        let id=&input.nodes[index].node_id;
        let has_bound=[
            styles[index].min_width,styles[index].max_width,
            styles[index].min_height,styles[index].max_height,
        ].iter().any(|value| matches!(value,Length::MinContent|Length::MaxContent));
        if !has_bound {continue;}
        let metric=input.measurements.iter().find(|m|m.node_id==*id);
        let bound=|value:Length,axis_width:bool|->Result<Length,ComputeError>{
            let is_min=match value {
                Length::MinContent=>true,Length::MaxContent=>false,
                _=>return Ok(value),
            };
            if !children[index].is_empty(){
                return Ok(Length::Px(if axis_width {
                    intrinsic_flex_width(
                        index,is_min,&input.nodes,&children,&styles,&input.measurements,
                    )?
                } else {
                    intrinsic_flex_height(
                        index,is_min,&input.nodes,&children,&styles,&input.measurements,
                    )?
                }));
            }
            let metric=metric.ok_or_else(||measurement(
                "Intrinsic min/max constraint requires measured leaf content.",id,
            ))?;
            Ok(Length::Px(match (axis_width,is_min){
                (true,true)=>metric.intrinsic.min_content_width,
                (true,false)=>metric.intrinsic.max_content_width,
                (false,true)=>metric.intrinsic.min_content_height,
                (false,false)=>metric.intrinsic.max_content_height,
            }))
        };
        let bounds=[
            bound(styles[index].min_width,true)?,
            bound(styles[index].max_width,true)?,
            bound(styles[index].min_height,false)?,
            bound(styles[index].max_height,false)?,
        ];
        styles[index].min_width=bounds[0];
        styles[index].max_width=bounds[1];
        styles[index].min_height=bounds[2];
        styles[index].max_height=bounds[3];
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
            Length::Auto|Length::MinContent|Length::MaxContent=>false,
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
            Length::Auto|Length::MinContent|Length::MaxContent=>false,
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
        let _outer=indices[outer_name];
        let (st,wrapper)=(styles[index],styles[parent]);
        let rooted_auto_chain={
            let mut current=parent;
            loop {
                let state=styles[current];
                if !matches!(state.width,Length::Auto)
                    || state.shrink!=0.0 || !horizontal(state.direction) {
                    break false;
                }
                let Some(ancestor_name)=input.nodes[current].parent_id.as_deref()
                    else {break false;};
                let ancestor=indices[ancestor_name];
                if matches!(styles[ancestor].width,Length::Px(_)) {
                    break horizontal(styles[ancestor].direction);
                }
                if children[ancestor].len()!=1 || children[ancestor][0]!=current {
                    break false;
                }
                current=ancestor;
            }
        };
        let fixed_siblings=!children[parent].is_empty()
            && children[parent].iter().all(|&sibling|{
                let sibling_style=styles[sibling];
                children[sibling].is_empty()
                    && matches!(sibling_style.width,Length::Px(_))
                    && matches!(sibling_style.basis,Length::Px(_))
                    && sibling_style.shrink==0.0
                    && matches!(sibling_style.padding_top,Length::Px(_))
                    && matches!(sibling_style.padding_bottom,Length::Px(_))
            });
        children[index].is_empty() && fixed_siblings
            && matches!(st.width,Length::Px(_)) && matches!(st.basis,Length::Px(_))
            && matches!(wrapper.width,Length::Auto) && wrapper.shrink==0.0
            && horizontal(wrapper.direction) && rooted_auto_chain
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
        // Indefinite containing axes do not authorize implicit min/max
        // percentages: reject with the same error class/node as Python.
        if (matches!(st.min_width,Length::Percent(_))
            && !definite_inline(index,input,&styles,&indices,0))
            || (matches!(st.min_height,Length::Percent(_))
                && !definite_block(index,input,&styles,&indices,0)){
            return Err(unsupported("Unlisted percentage minimum size dependency cycle.",node));
        }
        if matches!(st.max_width,Length::Percent(_))
            && !definite_inline(index,input,&styles,&indices,0){
            return Err(unsupported("Unlisted indefinite percentage maximum size dependency cycle.",node));
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
    let mut reused_sizes=vec![None;input.nodes.len()];
    let mut reusable_descendants=vec![Vec::new();input.nodes.len()];
    if let Some((old_input,old_result))=previous {
        let safe_environment=old_input.schema_version==input.schema_version
            && old_input.generation==old_result.generation
            && old_input.direction==input.direction
            && serde_json::to_value(&old_input.constraints).ok()
                ==serde_json::to_value(&input.constraints).ok()
            && old_input.nodes.len()==input.nodes.len()
            && old_result.diagnostics.is_empty()
            && old_result.geometry_commit_error.is_none_or(|v|v==0.0);
        if safe_environment {
            let old_measurements:HashMap<&str,&crate::compute::MeasuredBox>=old_input
                .measurements.iter().map(|m|(m.node_id.as_str(),m)).collect();
            let new_measurements:HashMap<&str,&crate::compute::MeasuredBox>=input
                .measurements.iter().map(|m|(m.node_id.as_str(),m)).collect();
            let old_boxes:HashMap<&str,&LayoutBox>=old_result.boxes.iter()
                .map(|b|(b.node_id.as_str(),b)).collect();
            let mut safe=vec![false;input.nodes.len()];
            for index in (0..input.nodes.len()).rev() {
                let node=&input.nodes[index];
                let old_node=&old_input.nodes[index];
                let old_metric=old_measurements.get(node.node_id.as_str());
                let new_metric=new_measurements.get(node.node_id.as_str());
                let measured_equal=match (old_metric,new_metric) {
                    (None,None)=>true,
                    (Some(a),Some(b))=>serde_json::to_value(a).ok()
                        ==serde_json::to_value(b).ok(),
                    _=>false,
                };
                let no_percent=!node.style.values().any(|value| {
                    if let Some(raw)=value.as_str(){return raw.contains('%');}
                    value.get("kind").and_then(Value::as_str)==Some("percent")
                });
                let direct=old_node.node_id==node.node_id
                    && old_node.parent_id==node.parent_id
                    && old_node.component==node.component
                    && old_node.style==node.style
                    && measured_equal && no_percent
                    && old_boxes.contains_key(node.node_id.as_str());
                let descendants_safe=children[index].iter().all(|&child|safe[child]);
                if direct && descendants_safe {
                    safe[index]=true;
                    let previous_box=old_boxes[node.node_id.as_str()];
                    reused_sizes[index]=Some((
                        previous_box.content.width,previous_box.content.height
                    ));
                    let mut subtree=vec![index];
                    for &child in &children[index] {
                        subtree.extend_from_slice(&reusable_descendants[child]);
                    }
                    reusable_descendants[index]=subtree;
                }
            }
        }
    }
    let mut context=Context {
        input,styles,children,provisional,
        measurements:input.measurements.iter().map(|m|(m.node_id.as_str(),m)).collect(),
        used:vec![None;input.nodes.len()],
        reused_sizes,reusable_descendants,
    };
    let root_style=context.styles[0];
    let width=resolved(root_style.width,
        input.constraints.width.value.filter(|_|input.constraints.width.definite),
        false,&input.nodes[0].node_id)?
        .or_else(||if matches!(root_style.width,Length::Auto){
            input.constraints.width.value.filter(|_|input.constraints.width.definite)
        }else{None});
    let height=resolved(root_style.height,
        input.constraints.height.value.filter(|_|input.constraints.height.definite),
        true,&input.nodes[0].node_id)?
        .or_else(||if matches!(root_style.height,Length::Auto){
            input.constraints.height.value.filter(|_|input.constraints.height.definite)
        }else{None});
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
            let resolved_edges=BoxEdges{
                padding:padding(st,parent_width,&node.node_id)?,
                border:border(st,&node.node_id)?,
                ..BoxEdges::default()
            };
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
                edges:resolved_edges,
                main_start,main_end,cross_start,cross_end,
                order:st.order,align_self:st.align_self,cross_size_auto:false,
                min_cross_content_size:0.0,max_cross_content_size:None,
                // The adapter provides both physical baseline axes in the
                // immutable snapshot; the shared kernel selects the axis
                // that is crosswise to the flex main direction.
                baseline_from_cross_start:context.measurements
                    .get(node.node_id.as_str())
                    .and_then(|measurement|if h {measurement.intrinsic.baseline}
                        else {measurement.intrinsic.orthogonal_baseline}),
            });
        }
        nodes.push(MarginTreeNode {
            id:node.node_id.clone(),parent:node.parent_id.clone(),
            width,height,item,edges:if index==0 {BoxEdges{
                padding:padding(st,width,&node.node_id)?,border:border(st,&node.node_id)?,
                ..BoxEdges::default()
            }} else {BoxEdges::default()},
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


#[cfg(test)]
mod point3_saturation_tests {
    use super::*;

    #[test]
    fn multiplied_gutter_count_is_never_truncated_to_i32() {
        let max=LayoutUnit::from_raw(i32::MAX);
        let count=(i32::MAX as usize)+4096;
        assert_eq!(saturating_gutter_product(max,count).raw(),i32::MAX);
        assert_eq!(
            saturating_gutter_product(LayoutUnit::from_raw(1),count).raw(),
            i32::MAX,
        );
        assert_eq!(
            saturating_gutter_product(LayoutUnit::from_raw(1),3).raw(),3,
        );
    }

    #[test]
    fn signed_overflow_in_percentage_margin_saturates_at_i32_endpoints() {
        let max=LayoutUnit::from_raw(i32::MAX).to_px();
        let min=LayoutUnit::from_raw(i32::MIN).to_px();
        assert_eq!(margin_value(Length::Percent(1e308),max),Some(max));
        assert_eq!(margin_value(Length::Percent(-1e308),max),Some(min));
    }

    #[test]
    fn finite_percentage_multiplication_overflow_saturates_without_panic() {
        let max = LayoutUnit::from_raw(i32::MAX).to_px();
        let min = LayoutUnit::from_raw(i32::MIN).to_px();
        assert_eq!(percent_used_dimension(1e200, 1e200), max);
        assert_eq!(percent_used_dimension(-1e200, 1e200), min);
        assert_eq!(percent_flex_basis_used(1e200, 1e200), max);
        assert_eq!(percent_flex_basis_used(-1e200, 1e200), min);
        assert_eq!(used_gap(Length::Percent(1e200), 1e200, "child").unwrap(), max);
    }

    #[test]
    fn signed_minimum_free_space_does_not_overflow_absolute_value() {
        // Two MAX-sized bases saturate the negative initial free space at
        // i32::MIN. A fractional flex shrink (sum 0.5) exercises the
        // intermediate absolute-value comparison at precisely that bound.
        // Previously i32::MIN.abs() panicked in debug builds.
        let max = LayoutUnit::from_raw(i32::MAX).to_px();
        let item = FlexBasis {
            basis: max, hypothetical: max, min_size: 0.0,
            max_size: None, grow: 0.0, shrink: 0.25,
        };
        let targets = blink_flex_targets(&[item, item], 0.0, 0.0, "saturation")
            .expect("Saturating fractional shrink must never panic");
        assert_eq!(targets.len(), 2);
        for size in targets {
            assert!(size.is_finite());
            assert!(size >= 0.0);
            assert!(size <= max);
            assert_eq!(size * 64.0, (size * 64.0).trunc());
        }
    }
}
