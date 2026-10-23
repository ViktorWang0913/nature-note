import {expect,test} from 'vitest';
import {ClampCrop,DragCrop,FitCrop,RotateCrop,fullCrop} from './crop';

test.each([0,90,180,270])('screen crop maps back to original coordinates at %s degrees',rotation=>{
  const crop={cropX:12,cropY:18,cropW:35,cropH:60};
  expect(RotateCrop(RotateCrop(crop,rotation),-rotation)).toEqual(crop);
});
test('clockwise crop selects the correct original quadrant',()=>{
  expect(RotateCrop({cropX:0,cropY:0,cropW:50,cropH:50},-90)).toEqual({cropX:0,cropY:50,cropW:50,cropH:50});
});
test('moving beyond the image clamps position and preserves size',()=>{
  expect(DragCrop({cropX:20,cropY:20,cropW:30,cropH:40},'move',300,-300)).toEqual({cropX:70,cropY:0,cropW:30,cropH:40});
});
test('corner cannot cross the opposite corner or escape the image',()=>{
  const crop={cropX:20,cropY:30,cropW:50,cropH:40};
  expect(DragCrop(crop,'nw',100,100)).toEqual({cropX:60,cropY:60,cropW:10,cropH:10});
  expect(DragCrop(crop,'se',100,100)).toEqual({cropX:20,cropY:30,cropW:80,cropH:70});
});
test('free edge changes just one axis and leaves its opposite edge fixed',()=>{
  expect(DragCrop({cropX:20,cropY:30,cropW:50,cropH:40},'w',15,200)).toEqual({cropX:35,cropY:30,cropW:35,cropH:40});
});
test('square pixel preset fits portrait source without stretching',()=>{
  const crop=FitCrop(fullCrop,1/(2/3));
  expect(crop.cropW).toBe(100);expect(crop.cropH).toBeCloseTo(66.666667);
  expect(crop.cropW*80/(crop.cropH*120)).toBeCloseTo(1);
});
test('fixed corner keeps ratio and opposite corner at boundaries',()=>{
  const crop={cropX:20,cropY:20,cropW:60,cropH:40};
  const result=DragCrop(crop,'nw',-200,-200,1.5);
  expect(result.cropX+result.cropW).toBe(80);expect(result.cropY+result.cropH).toBe(60);
  expect(result.cropW/result.cropH).toBeCloseTo(1.5);expect(result.cropX).toBe(0);
});
test('serializable crop coordinates respect strict backend sum limits',()=>{
  const crop=ClampCrop({cropX:33.3333333,cropY:26.6666667,cropW:66.6666667,cropH:73.3333333});
  expect(crop.cropX+crop.cropW).toBeLessThanOrEqual(100);expect(crop.cropY+crop.cropH).toBeLessThanOrEqual(100);
});
