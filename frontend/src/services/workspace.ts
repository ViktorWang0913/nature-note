// 真实窗口与键盘高度共同确定内容可用空间。
export const workspace = Behavior({
 data:{viewportHeight:0,keyboardHeight:0},
 methods:{
  MeasureWindow(){const windowInfo=wx.getWindowInfo();this._fullWindowHeight=windowInfo.windowHeight;this._windowWidth=windowInfo.windowWidth;this.setData({viewportHeight:windowInfo.windowHeight,keyboardHeight:0});},
  ApplyKeyboardHeight(event:any){const keyboardHeight=Math.max(0,event.detail.height||0);const windowInfo=wx.getWindowInfo();this.setData({keyboardHeight,viewportHeight:Math.max(180,Math.min(windowInfo.windowHeight,(this._fullWindowHeight||windowInfo.windowHeight)-keyboardHeight))});},
  ResizeWindow(event:any){
   const windowSize=event.size;
   console.log('[开始] 窗口尺寸变化');
   if(windowSize.windowWidth!==this._windowWidth||windowSize.windowHeight>=(this._fullWindowHeight||0)){console.log('[分支] 更新完整窗口尺寸');this._fullWindowHeight=windowSize.windowHeight;this._windowWidth=windowSize.windowWidth;}else{console.log('[分支] 保留键盘弹出前的高度');}
   console.log('[结束] 窗口尺寸变化');
   this.setData({viewportHeight:Math.max(180,Math.min(windowSize.windowHeight,this._fullWindowHeight-this.data.keyboardHeight))});
  }
 }
});
