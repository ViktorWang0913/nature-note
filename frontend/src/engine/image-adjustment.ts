import {ImageEdit} from '../types/models';

// 参数设置：调整参数随笔记保存，原始图片只读。
export const defaultImageEdit:ImageEdit={cropX:0,cropY:0,cropW:100,cropH:100,brightness:100,contrast:100,saturation:100,filter:'none'};
const processedImages=new WeakMap<object,{signature:string;canvas:HTMLCanvasElement}>();

export function AdjustImage(image:HTMLImageElement, settings:ImageEdit):HTMLCanvasElement {
  const signature=JSON.stringify(settings),cached=processedImages.get(image);
  console.log('[开始] 素材调整缓存');
  if(cached?.signature===signature){console.log('[分支] 使用当前调整；[结束] 素材调整缓存，提前结束');return cached.canvas;}
  console.log('[分支] 计算新调整；[结束] 素材调整缓存');
  const canvas=document.createElement('canvas');
  const left=Math.round(image.width*settings.cropX/100),top=Math.round(image.height*settings.cropY/100);
  canvas.width=Math.max(1,Math.round(image.width*(settings.cropX+settings.cropW)/100)-left);
  canvas.height=Math.max(1,Math.round(image.height*(settings.cropY+settings.cropH)/100)-top);
  const context=canvas.getContext('2d')!;
  // 复用浏览器原生滤镜，预览和导出共享同一次计算，并保留透明通道。
  console.log('[开始] 浏览器图片调整能力检查');
  if(!('filter' in context)){console.log('[分支] 当前浏览器不支持；[结束] 浏览器图片调整能力检查，提前结束');throw new Error('当前浏览器不支持图片调整，请使用新版 Chrome 或 Edge');}
  console.log('[分支] 原生 Canvas 滤镜；[结束] 浏览器图片调整能力检查');
  const filterStyles={none:'',warm:'sepia(0.22) saturate(1.15)',cool:'sepia(0.12) hue-rotate(165deg)',grayscale:'grayscale(1)'};
  context.filter=`brightness(${settings.brightness}%) contrast(${settings.contrast}%) saturate(${settings.saturation}%) ${filterStyles[settings.filter]}`.trim();
  context.drawImage(image,left,top,canvas.width,canvas.height,0,0,canvas.width,canvas.height);
  processedImages.set(image,{signature,canvas});
  return canvas;
}
