import {Layout,SceneElement} from '../types/models';
import {clone,uid,worldMatrix,transform,validateLayout} from './scene';
import {BuildStroke} from './drawing';

// 旧模板的路线仅是装饰，转换后不携带真实轨迹或观察点引用。
export function manualTemplate(source:Layout):Layout{
  if(!validateLayout(source)||!Number.isInteger(source.width)||!Number.isInteger(source.height)||source.width>4096||source.height>4096)throw new Error('模板画布不符合当前编辑器的尺寸要求');
  const result:Layout={schema_version:1,notebookVersion:1,designMode:'manual',width:source.width,height:source.height,background:source.background,elements:[]};
  const Add=(element:SceneElement)=>{element.id=uid('template');element.z=result.elements.length+1;result.elements.push(element);};
  for(const original of [...source.elements].sort((a,b)=>a.z-b.z)){
    const matrix=worldMatrix(source,original);
    if(original.type==='route'){
      const route=original.route;if(!route)throw new Error('模板路线缺少数据');
      const color=route.color||'#bebbb6',lineWidth=route.lineWidth||36;
      if(!/^#[0-9a-fA-F]{6}$/.test(color)||lineWidth<1||lineWidth>80)throw new Error('模板路线样式不受支持');
      for(const segment of route.segments||[route.points]){
        if(segment.length<2)continue;
        if(segment.length>2048||segment.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)))throw new Error('模板路线坐标无效');
        if(route.style==='smooth')Add(BuildStroke(segment.map(p=>transform(matrix,p)),lineWidth,color,original.opacity??1,uid(),1,'pen'));
        else{
          for(let i=1;i<segment.length;i++){
            const a=segment[i-1],b=segment[i],corner={x:b.x,y:a.y};
            for(const [start,end] of [[a,corner],[corner,b]]){
              const first=transform(matrix,start),last=transform(matrix,end);
              if(first.x===last.x&&first.y===last.y)continue;
              const left=Math.min(first.x,last.x)-1,top=Math.min(first.y,last.y)-1,width=Math.abs(last.x-first.x)+2,height=Math.abs(last.y-first.y)+2;
              Add({id:'',type:'shape',x:left,y:top,width,height,rotation:0,z:1,shape:{kind:'line',fill:'none',stroke:color,lineWidth:Math.min(40,lineWidth),dashed:false,radius:0,lockRatio:false,points:[first,last].map(p=>({x:(p.x-left)/width,y:(p.y-top)/height}))}});
            }
          }
        }
      }
      const radius=Math.max(30,original.width*.018),fontSize=Math.max(26,original.width*.016);
      for(const node of route.nodes){
        const center=transform(matrix,node);
        Add({id:'',type:'shape',x:center.x-radius,y:center.y-radius,width:radius*2,height:radius*2,rotation:0,z:1,shape:{kind:'circle',fill:'#63ac77',stroke:'#ffffff',lineWidth:8,dashed:false,radius:0,lockRatio:true}});
        Add({id:'',type:'text',x:center.x-radius,y:center.y-fontSize*.6,width:radius*2,height:fontSize*1.5,rotation:0,z:1,text:node.label,fontSize,fontFamily:'sans-serif',fontWeight:'bold',textAlign:'center',color:'#ffffff'});
      }
    }else{
      const element=clone(original),angle=Math.atan2(matrix[1],matrix[0]),c=Math.cos(angle),s=Math.sin(angle);
      if(!['image','text','shape','stroke'].includes(element.type))throw new Error('模板包含暂不支持的图层');
      element.x=matrix[4]-element.width/2+c*element.width/2-s*element.height/2;
      element.y=matrix[5]-element.height/2+s*element.width/2+c*element.height/2;
      element.rotation=angle*180/Math.PI;
      delete element.parent_id;delete element.node_id;
      Add(element);
    }
  }
  if(result.elements.length>200||!validateLayout(result))throw new Error('模板图层过多或结构无效，请选择其他模板');
  return result;
}
