//! Renderer-neutral snapshot sizing orchestration for the initial closed F2 path.
//! This stage never measures widgets and never converts an unknown CSS value
//! into a numeric zero. Unsupported contexts carry a stable diagnostic.
use crate::align_content::AlignContent;
use crate::compute::{ComputeError, LayoutBox, LayoutInput, LayoutResult, Rect};
use crate::cross_alignment::CrossAlign;
use crate::edge_pipeline::BoxEdges;
use crate::line_layout::{Direction, Wrap, WritingDirection};
use crate::main_alignment::JustifyContent;
use crate::margin_flex_pipeline::MarginFlexItem;
use crate::margin_tree::{compute_margin_tree, MarginTreeNode};
use crate::{resolve_flexible_lengths, FlexBasis};
use serde_json::Value;
use std::collections::HashMap;

#[derive(Clone, Copy)]
enum Length { Auto, Px(f64), Percent(f64) }

#[derive(Clone, Copy)]
struct Style {
    direction: Direction,
    width: Length,
    height: Length,
    basis: Length,
    grow: f64,
    shrink: f64,
    min_width: Length,
    min_height: Length,
    align: CrossAlign,
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
            "layout_min_width"|"layout_min_height"|"align_items"){
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
    let align=match map.get("align_items").and_then(Value::as_str).unwrap_or("stretch"){
        "stretch"=>CrossAlign::Stretch,"flex-start"=>CrossAlign::FlexStart,
        _=>return Err(unsupported("Unsupported align-items value.",&input.node_id)),
    };
    Ok(Style{
        direction,align,
        width:length(value(map,&["layout_width","width"]),&input.node_id)?,
        height:length(value(map,&["layout_height","height"]),&input.node_id)?,
        basis:length(map.get("flex_basis"),&input.node_id)?,
        grow:factor(map.get("flex_grow"),0.0,&input.node_id)?,
        shrink:factor(map.get("flex_shrink"),1.0,&input.node_id)?,
        min_width:length(value(map,&["layout_min_width","min_width"]),&input.node_id)?,
        min_height:length(value(map,&["layout_min_height","min_height"]),&input.node_id)?,
    })
}
fn resolved(v:Length, reference:Option<f64>, vertical:bool, id:&str)->Result<Option<f64>,ComputeError>{
    match v {
        Length::Auto=>Ok(None),
        Length::Px(n)=>Ok(Some(n)),
        Length::Percent(p) if reference.is_some()=>Ok(Some(p*reference.unwrap())),
        Length::Percent(_) if vertical=>Ok(None), // CSS auto-block-size cyclic context
        Length::Percent(_)=>Err(unsupported("Indefinite inline percentage dependency.",id)),
    }
}
fn horizontal(dir:Direction)->bool{
    matches!(dir,Direction::Row|Direction::RowReverse)
}
struct Context<'a>{
    input:&'a LayoutInput,
    styles:Vec<Style>,
    children:Vec<Vec<usize>>,
    measurements:HashMap<&'a str,&'a crate::compute::MeasuredBox>,
    used:Vec<Option<(f64,f64)>>,
}
impl Context<'_>{
    fn preferred(&self,index:usize,h:bool)->Result<f64,ComputeError>{
        let node=&self.input.nodes[index];
        let style=self.styles[index];
        match if h {style.width}else{style.height}{
            Length::Px(n)=>return Ok(n),
            _=>{},
        }
        if self.children[index].is_empty(){
            if let Some(m)=self.measurements.get(node.node_id.as_str()){
                return Ok(if h{m.intrinsic.preferred_width}else{m.intrinsic.preferred_height});
            }
            if node.component=="Text" {
                return Err(measurement("Text requires intrinsic measurement.",&node.node_id));
            }
            return Ok(0.0);
        }
        let mut sizes=Vec::with_capacity(self.children[index].len());
        for &child in &self.children[index] {sizes.push(self.preferred(child,h)?);}
        Ok(if horizontal(style.direction)==h {
            sizes.iter().sum()
        } else {
            sizes.into_iter().fold(0.0_f64,f64::max)
        })
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
                if let Some(m)=self.measurements.get(id.as_str()){
                    if m.constraints.width.definite &&
                        (m.constraints.width.value.unwrap()-width.unwrap()).abs()>0.01{
                        return Err(measurement("Missing post-flex width-specific intrinsic measurement.",&id));
                    }
                }
                height=Some(self.preferred(index,false)?);
            }
            let dims=(width.unwrap(),height.unwrap());
            self.used[index]=Some(dims);
            return Ok(dims);
        }
        let row=horizontal(style.direction);
        if width.is_none(){width=Some(self.preferred(index,true)?);}
        if height.is_none()&&!row{height=Some(self.preferred(index,false)?);}
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
                    Some(n)=>p*n,None=>self.preferred(child,row)?,
                },
            };
            let minimum=match if row{child_style.min_width}else{child_style.min_height}{
                Length::Px(n)=>n,
                Length::Auto=>self.measurements.get(child_id.as_str())
                    .map(|m|if row{m.intrinsic.min_content_width}else{m.intrinsic.min_content_height}).unwrap_or(0.0),
                Length::Percent(_)=>return Err(unsupported("Unresolved percentage automatic minimum.",child_id)),
            };
            bases.push(FlexBasis {
                basis:desired, hypothetical:desired.max(minimum),
                grow:child_style.grow,shrink:child_style.shrink,
                min_size:minimum,max_size:None,
            });
        }
        let targets=resolve_flexible_lengths(&bases,main,0.0)
            .map_err(|e|failure("SFLE_LAYOUT_CONSTRAINT_ERROR",format!("Flex allocation failed: {e:?}"),Some(&id)))?;
        let mut cross_sizes=Vec::new();
        for (&child,&target) in child_indices.iter().zip(targets.iter()){
            let child_id=self.input.nodes[child].node_id.clone();
            let child_style=self.styles[child];
            let (cw,ch)=if row{
                let mut cross=resolved(child_style.height,height,true,&child_id)?;
                if cross.is_none()&&height.is_some()&&style.align==CrossAlign::Stretch{cross=height;}
                self.layout(child,Some(target),cross,width,height)?
            }else{
                let mut cross=resolved(child_style.width,width,false,&child_id)?;
                if cross.is_none()&&style.align==CrossAlign::Stretch{cross=width;}
                self.layout(child,cross,Some(target),width,height)?
            };
            cross_sizes.push(if row{ch}else{cw});
        }
        if height.is_none(){height=Some(cross_sizes.into_iter().fold(0.0_f64,f64::max));}
        let dims=(width.unwrap(),height.unwrap());
        self.used[index]=Some(dims);
        Ok(dims)
    }
}
fn converted(r:crate::line_layout::Rect)->Rect{
    Rect{x:r.x,y:r.y,width:r.width,height:r.height}
}
pub fn compute_normalized(input:&LayoutInput)->Result<LayoutResult,ComputeError>{
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
    let mut context=Context {
        input,styles,children,
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
            item=Some(MarginFlexItem {
                id:node.node_id.clone(),
                flex:FlexBasis {basis:main,hypothetical:main,grow:0.0,shrink:0.0,
                    min_size:0.0,max_size:None},
                cross_content_size:cross,
                edges:BoxEdges::default(),
                main_start:Some(0.0),main_end:Some(0.0),
                cross_start:Some(0.0),cross_end:Some(0.0),
                order:0,align_self:CrossAlign::Auto,cross_size_auto:false,
                min_cross_content_size:0.0,max_cross_content_size:None,
                baseline_from_cross_start:None,
            });
        }
        nodes.push(MarginTreeNode {
            id:node.node_id.clone(),parent:node.parent_id.clone(),
            width,height,item,edges:BoxEdges::default(),
            direction:st.direction,wrap:Wrap::NoWrap,
            main_gap:0.0,cross_gap:0.0,justify:JustifyContent::FlexStart,
            align_items:CrossAlign::FlexStart,
            align_content:AlignContent::FlexStart,intrinsic_basis:None,
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
