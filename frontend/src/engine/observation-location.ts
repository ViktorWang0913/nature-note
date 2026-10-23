// 草稿的位置代表此次观察发生时的位置；接受最近 30 秒、误差不超过 150 米的真实定位。
export function IsRecentPosition(position:any,now=Date.now()):boolean{
  const timestamp=typeof position?.timestamp==='number'?position.timestamp:Date.parse(position?.timestamp);
  return Number.isFinite(position?.latitude)&&Math.abs(position.latitude)<=90
    &&Number.isFinite(position?.longitude)&&Math.abs(position.longitude)<=180
    &&Number.isFinite(position?.accuracy)&&position.accuracy>=0&&position.accuracy<=150
    &&Number.isFinite(timestamp)&&now-timestamp>=-1000&&now-timestamp<=30000;
}
