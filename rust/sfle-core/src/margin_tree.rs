//! F2.2.4.6 nested resolved Flex with signed/auto margins and alignment.
//! Source CSS/intrinsic dependencies are resolved in preceding sizing phases.

use crate::align_content::AlignContent;
use crate::cross_alignment::CrossAlign;
use crate::edge_pipeline::{BoxEdges, Edges};
use crate::line_layout::{Direction, Rect, Wrap, WritingDirection};
use crate::main_alignment::JustifyContent;
use crate::margin_flex_pipeline::{
    compute_margin_flex_layout_content, MarginFlexBox, MarginFlexItem,
};
use crate::FlexMathError;
use std::collections::HashMap;

#[derive(Clone, Debug, PartialEq)]
pub struct MarginTreeNode {
    pub id: String,
    pub parent: Option<String>,
    pub width: f64,
    pub height: f64,
    pub item: Option<MarginFlexItem>,
    pub edges: BoxEdges,
    pub direction: Direction,
    pub wrap: Wrap,
    pub main_gap: f64,
    pub cross_gap: f64,
    pub justify: JustifyContent,
    pub align_items: CrossAlign,
    pub align_content: AlignContent,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MarginTreeLayout {
    pub boxes: Vec<MarginFlexBox>,
}

fn translate(r: Rect, x: f64, y: f64) -> Rect {
    Rect { x: r.x+x, y:r.y+y, ..r }
}
fn translate_box(mut b: MarginFlexBox, x: f64, y: f64) -> MarginFlexBox {
    b.content=translate(b.content,x,y);
    b.padding=translate(b.padding,x,y);
    b.border=translate(b.border,x,y);
    b
}

pub fn compute_margin_tree(
    nodes: &[MarginTreeNode],
    writing: WritingDirection,
) -> Result<MarginTreeLayout, FlexMathError> {
    if nodes.is_empty() { return Ok(MarginTreeLayout{boxes:vec![]}); }
    let mut children:HashMap<&str,Vec<usize>>=HashMap::new();
    for (i,node) in nodes.iter().enumerate() {
        if node.id.is_empty() || children.contains_key(node.id.as_str())
            || ![node.width,node.height,node.main_gap,node.cross_gap]
                .iter().all(|x| x.is_finite() && *x >= 0.0)
            || node.edges.margin != Edges::default()
            || node.align_items == CrossAlign::Auto
        {
            return Err(FlexMathError::InvalidInput("invalid margin tree node"));
        }
        if i==0 {
            if node.parent.is_some() || node.item.is_some() {
                return Err(FlexMathError::InvalidInput("root cannot be item"));
            }
        } else {
            let parent=node.parent.as_deref().ok_or(
                FlexMathError::InvalidInput("missing parent")
            )?;
            if !children.contains_key(parent) || node.item.as_ref().is_none_or(|it| it.id!=node.id) {
                return Err(FlexMathError::InvalidInput("non-preorder parent or mismatched item"));
            }
            children.get_mut(parent).expect("parent exists").push(i);
        }
        children.insert(node.id.as_str(),vec![]);
    }
    let root=&nodes[0];
    let e=root.edges;
    let content=Rect {
        x:e.border.left+e.padding.left,
        y:e.border.top+e.padding.top,
        width:root.width,
        height:root.height,
    };
    let padding=Rect {
        x:e.border.left,y:e.border.top,
        width:root.width+e.padding.left+e.padding.right,
        height:root.height+e.padding.top+e.padding.bottom,
    };
    let border=Rect {
        x:0.0,y:0.0,
        width:padding.width+e.border.left+e.border.right,
        height:padding.height+e.border.top+e.border.bottom,
    };
    let mut geometry:HashMap<&str,MarginFlexBox>=HashMap::new();
    geometry.insert(root.id.as_str(),MarginFlexBox{
        id:root.id.clone(),content,padding,border,
        used_main_start_margin:0.0,used_main_end_margin:0.0,line_index:0,
        used_cross_start_margin:0.0,used_cross_end_margin:0.0,
    });
    for parent in nodes {
        let origin=geometry[parent.id.as_str()].content;
        let child_indices=&children[parent.id.as_str()];
        if child_indices.is_empty(){continue;}
        let items:Vec<MarginFlexItem>=child_indices.iter().map(|&index|
            nodes[index].item.as_ref().expect("validated").clone()
        ).collect();
        let positioned=compute_margin_flex_layout_content(
            &items,origin.width,origin.height,
            parent.direction,writing,parent.wrap,parent.main_gap,parent.cross_gap,
            parent.justify,parent.align_items,parent.align_content,
        )?;
        for item in positioned.boxes {
            let key=nodes.iter().find(|n|n.id==item.id).expect("known").id.as_str();
            geometry.insert(key,translate_box(item,origin.x,origin.y));
        }
    }
    Ok(MarginTreeLayout{
        boxes:nodes.iter().map(|n|geometry[n.id.as_str()].clone()).collect(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::FlexBasis;
    fn flex(v:f64)->MarginFlexItem {
        MarginFlexItem {
            id:"".into(),flex:FlexBasis{
                basis:v,hypothetical:v,min_size:0.0,max_size:None,
                grow:0.0,shrink:0.0,
            },
            cross_content_size:20.0,edges:BoxEdges::default(),
            main_start:Some(0.0),main_end:Some(0.0),order:0,
            cross_start:Some(0.0),cross_end:Some(0.0),
            align_self:CrossAlign::Auto,cross_size_auto:false,
            min_cross_content_size:0.0,max_cross_content_size:None,
            baseline_from_cross_start:None,
        }
    }
    fn node(id:&str,parent:Option<&str>,width:f64,height:f64,item:Option<MarginFlexItem>)->MarginTreeNode{
        MarginTreeNode{id:id.into(),parent:parent.map(str::to_string),
            width,height,item,edges:BoxEdges::default(),
            direction:Direction::Row,wrap:Wrap::NoWrap,
            main_gap:0.0,cross_gap:0.0,justify:JustifyContent::FlexStart,
            align_items:CrossAlign::FlexStart,align_content:AlignContent::FlexStart}
    }
    #[test]
    fn nested_justify_offsets_from_parent_content_origin(){
        let mut root=node("root",None,200.0,80.0,None);
        root.edges.padding.left=5.0;
        root.justify=JustifyContent::Center;
        let mut p=flex(100.0);p.id="parent".into();p.edges.padding.left=6.0;
        let mut parent=node("parent",Some("root"),100.0,40.0,Some(p));
        parent.justify=JustifyContent::FlexEnd;
        let mut l=flex(20.0);l.id="leaf".into();
        let leaf=node("leaf",Some("parent"),20.0,20.0,Some(l));
        let result=compute_margin_tree(&[root,parent,leaf],WritingDirection::Ltr).unwrap();
        assert_eq!(result.boxes[1].border.x,52.0);
        assert_eq!(result.boxes[2].border.x,138.0);
    }
}
