import { expect, test } from 'vitest';
import { IsRecentPosition } from './observation-location';

test('排除缺失、过期、未来及低精度坐标，允许真实零坐标',()=>{
  const now=Date.now(),position={latitude:0,longitude:0,accuracy:20,timestamp:now};
  expect(IsRecentPosition(position,now)).toBe(true);
  expect(IsRecentPosition(undefined,now)).toBe(false);
  expect(IsRecentPosition({...position,timestamp:now-31000},now)).toBe(false);
  expect(IsRecentPosition({...position,timestamp:now+60000},now)).toBe(false);
  expect(IsRecentPosition({...position,accuracy:151},now)).toBe(false);
  expect(IsRecentPosition({...position,latitude:NaN},now)).toBe(false);
});
