// 参数设置：保持现有图片编辑协议的最小裁剪范围。
export interface CropRect {cropX:number;cropY:number;cropW:number;cropH:number}
export const fullCrop:CropRect={cropX:0,cropY:0,cropW:100,cropH:100};
export const cropMinimum=10;

export function RotateCrop(crop:CropRect,rotation:number):CropRect {
  const turn=((rotation%360)+360)%360;
  console.log('[开始] 裁剪坐标旋转');
  switch(turn){
    case 90: console.log('[分支] 顺时针 90 度；[结束] 裁剪坐标旋转');return {cropX:100-crop.cropY-crop.cropH,cropY:crop.cropX,cropW:crop.cropH,cropH:crop.cropW};
    case 180: console.log('[分支] 旋转 180 度；[结束] 裁剪坐标旋转');return {...crop,cropX:100-crop.cropX-crop.cropW,cropY:100-crop.cropY-crop.cropH};
    case 270: console.log('[分支] 顺时针 270 度；[结束] 裁剪坐标旋转');return {cropX:crop.cropY,cropY:100-crop.cropX-crop.cropW,cropW:crop.cropH,cropH:crop.cropW};
    default: console.log('[分支] 原图坐标；[结束] 裁剪坐标旋转');return {...crop};
  }
}

export function ClampCrop(crop:CropRect):CropRect {
  const cropX=Math.max(0,Math.min(90,Number(crop.cropX.toFixed(6)))),cropY=Math.max(0,Math.min(90,Number(crop.cropY.toFixed(6))));
  return {cropX,cropY,cropW:Math.min(100-cropX,Math.max(cropMinimum,Number(crop.cropW.toFixed(6)))),cropH:Math.min(100-cropY,Math.max(cropMinimum,Number(crop.cropH.toFixed(6))))};
}

// ratio 是显示坐标中的百分比宽高比，像素比例须先除以图片宽高比。
export function FitCrop(crop:CropRect,ratio:number):CropRect {
  const cropW=Math.min(100,100*ratio),cropH=cropW/ratio;
  return ClampCrop({cropW,cropH,cropX:Math.max(0,Math.min(100-cropW,crop.cropX+crop.cropW/2-cropW/2)),cropY:Math.max(0,Math.min(100-cropH,crop.cropY+crop.cropH/2-cropH/2))});
}

export function DragCrop(crop:CropRect,handle:string,deltaX:number,deltaY:number,ratio=0):CropRect {
  console.log('[开始] 裁剪手势计算');
  if(handle==='move'){
    console.log('[分支] 平移选区；[结束] 裁剪手势计算，提前结束');
    return ClampCrop({...crop,cropX:Math.max(0,Math.min(100-crop.cropW,crop.cropX+deltaX)),cropY:Math.max(0,Math.min(100-crop.cropH,crop.cropY+deltaY))});
  }
  console.log('[分支] 调整选区边界；[结束] 裁剪手势计算');
  const west=handle.includes('w'),north=handle.includes('n'),east=handle.includes('e'),south=handle.includes('s');
  const anchorX=west?crop.cropX+crop.cropW:crop.cropX,anchorY=north?crop.cropY+crop.cropH:crop.cropY;
  let cropW=crop.cropW+(west?-deltaX:east?deltaX:0),cropH=crop.cropH+(north?-deltaY:south?deltaY:0);
  const maxWidth=west?anchorX:100-anchorX,maxHeight=north?anchorY:100-anchorY;
  console.log('[开始] 裁剪比例约束');
  if(ratio){
    console.log('[分支] 固定比例且保持对角锚点');
    const proposedWidth=Math.abs(deltaX)>=Math.abs(deltaY*ratio)?cropW:cropH*ratio;
    cropW=Math.max(Math.max(cropMinimum,cropMinimum*ratio),Math.min(maxWidth,maxHeight*ratio,proposedWidth));cropH=cropW/ratio;
  }else{
    console.log('[分支] 自由调整');cropW=Math.max(cropMinimum,Math.min(maxWidth,cropW));cropH=Math.max(cropMinimum,Math.min(maxHeight,cropH));
  }
  console.log('[结束] 裁剪比例约束');
  return ClampCrop({cropX:west?anchorX-cropW:anchorX,cropY:north?anchorY-cropH:anchorY,cropW,cropH});
}
