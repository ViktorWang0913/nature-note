<script setup lang="ts">
defineProps<{state:any}>();
const emit=defineEmits(['action']);
function Dispatch(name:string,event?:Event){emit('action',name,event);}
</script>
<template>
  <div class="drawing-tools" v-if="state.hasBackground && !state.busy && state.panel!=='image'">
    <aside class="drawing-rail" aria-label="绘图工具">
      <button data-tool="brush" :class="{active:state.drawingMode}" aria-label="画笔" :aria-expanded="state.toolPanel==='brush'" @click="Dispatch('ToggleTool',$event)"><svg viewBox="0 0 24 24"><path d="m5 16-1 5 5-1L21 8l-4-4Z M14 7l4 4"/></svg><span>画笔</span></button>
      <button data-tool="shapes" :class="{active:state.toolPanel==='shapes'}" aria-label="图形" :aria-expanded="state.toolPanel==='shapes'" @click="Dispatch('ToggleTool',$event)"><svg viewBox="0 0 24 24"><rect x="10" y="10" width="11" height="11" rx="1"/><circle cx="8" cy="8" r="6"/></svg><span>图形</span></button>
      <button v-if="state.drawingMode" class="finish-drawing" @click="Dispatch('FinishDrawing',$event)" aria-label="完成绘画">✓<span>完成</span></button>
    </aside>
    <section v-if="state.toolPanel==='shapes'" class="drawing-flyout shape-flyout" aria-label="标准图形">
      <button class="flyout-close" data-tool="shapes" @click="Dispatch('ToggleTool',$event)" aria-label="关闭图形">×</button>
      <div class="shape-list"><button v-for="shape in state.shapeChoices" :key="shape.kind" :data-kind="shape.kind" :aria-label="shape.label" :title="shape.label" @click="Dispatch('AddShape',$event)"><svg viewBox="0 0 32 32" :class="{line:['line','arrow','doubleArrow'].includes(shape.kind)}"><path :d="shape.path"/></svg><span>{{shape.label}}</span></button></div>
    </section>
    <section v-if="state.toolPanel==='brush'" class="drawing-flyout brush-flyout" aria-label="笔型选择">
      <button class="flyout-close" data-tool="brush" @click="Dispatch('ToggleTool',$event)" aria-label="收起笔型">×</button>
      <button v-for="brush in state.brushChoices" :key="brush.kind" :data-kind="brush.kind" :aria-label="brush.label" :class="{active:state.brushKind===brush.kind}" @click="Dispatch('ChooseBrush',$event)"><span class="brush-symbol" :style="{color:state.brushColor}">{{brush.symbol}}</span><span>{{brush.label}}</span></button>
      <button data-popup="color" @click="Dispatch('BrushPopup',$event)" aria-label="画笔颜色"><i class="color-dot" :style="{background:state.brushColor}"></i><span>颜色</span></button>
      <button data-popup="settings" @click="Dispatch('BrushPopup',$event)" aria-label="笔刷设置"><span class="brush-symbol">☷</span><span>设置</span></button>
    </section>
    <section v-if="state.brushPopup" class="brush-popover" :aria-label="state.brushPopup==='color'?'画笔颜色设置':'笔刷参数'">
      <header><strong>{{state.brushPopup==='color'?'颜色':'笔刷设置'}}</strong><button :data-popup="state.brushPopup" @click="Dispatch('BrushPopup',$event)" aria-label="关闭笔刷设置">×</button></header>
      <template v-if="state.brushPopup==='color'">
        <div class="brush-swatches"><button v-for="color in [...state.colors,...state.recentColors]" :key="color" :data-color="color" :style="{background:color}" :aria-label="'选择颜色 '+color" @click="Dispatch('BrushColor',$event)"></button></div>
        <label class="drawing-field">自定义颜色<input type="color" :value="state.brushColor" @input="Dispatch('BrushColor',$event)" aria-label="自定义笔刷颜色"></label>
        <label class="drawing-field">颜色值<input type="text" maxlength="7" :value="state.brushColor" @change="Dispatch('BrushColor',$event)" aria-label="笔刷颜色值"></label>
      </template>
      <template v-else>
        <label class="drawing-field">粗细<input aria-label="画笔粗细数值" type="number" min="1" max="80" :value="state.brushWidth" data-field="brushWidth" @change="Dispatch('BrushSetting',$event)">px</label>
        <input aria-label="画笔粗细" type="range" min="1" max="80" :value="state.brushWidth" data-field="brushWidth" @input="Dispatch('BrushSetting',$event)">
      </template>
      <label class="drawing-field">不透明度<input aria-label="画笔不透明度数值" type="number" min="0" max="100" :value="state.brushOpacity" data-field="brushOpacity" @change="Dispatch('BrushSetting',$event)">%</label>
      <input aria-label="画笔不透明度" type="range" min="0" max="100" :value="state.brushOpacity" data-field="brushOpacity" @input="Dispatch('BrushSetting',$event)">
      <div class="stroke-preview"><svg viewBox="0 0 240 74"><path d="M22 43 Q60 15 100 38 T218 33" fill="none" :stroke="state.brushColor" :stroke-width="Math.min(40,state.brushWidth)" :opacity="state.brushOpacity/100" stroke-linecap="round"/></svg><span>笔迹预览</span></div>
    </section>
    <span v-if="state.drawingMode" class="drawing-mode-label">{{state.brushKind==='eraser'?'整笔擦除':'正在绘画'}} · 双指移动与缩放</span>
  </div>
</template>
<style scoped>
.drawing-tools{position:absolute;inset:0;pointer-events:none;z-index:3;color:var(--nn-ink)}.drawing-tools button,.drawing-tools input,.drawing-flyout,.brush-popover{pointer-events:auto}.drawing-rail{position:absolute;top:16px;left:10px;padding:5px;background:var(--nn-panel);border:1px solid var(--nn-line);border-radius:12px;box-shadow:0 3px 12px #253f3310;display:flex;flex-direction:column;gap:4px}.drawing-rail button{display:flex;flex-direction:column;align-items:center;gap:4px;width:46px;min-height:54px;background:transparent;border-radius:6px;font-size:11px;padding:5px}.drawing-rail svg{width:24px;height:24px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.drawing-rail .active{background:var(--nn-accent);color:#fff}.brush-flyout .active{background:var(--nn-selected);color:var(--nn-accent)}.drawing-flyout{position:absolute;left:76px;top:16px;width:82px;max-height:calc(100% - 32px);background:var(--nn-panel);border-radius:12px;box-shadow:0 4px 18px #263d3020;border:1px solid var(--nn-line);display:flex;flex-direction:column;overflow:hidden}.flyout-close{height:38px;min-height:38px;align-self:flex-end;width:38px;font-size:24px;background:var(--nn-panel)}.shape-list{overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin}.shape-list button,.brush-flyout>button:not(.flyout-close){width:100%;min-height:65px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;font-size:10px;background:var(--nn-panel);padding:8px 2px;flex-shrink:0}.shape-list button:hover{background:var(--nn-soft)}.shape-list svg{width:32px;height:32px;fill:var(--nn-ink);stroke:var(--nn-ink);stroke-width:1.2}.shape-list svg.line{fill:none;stroke-width:2.5}.brush-flyout{overflow:auto}.brush-flyout>button.active{background:var(--nn-selected)}.brush-symbol{font-size:30px;line-height:32px}.color-dot{width:28px;height:28px;border:2px solid white;outline:1px solid var(--nn-line);border-radius:50%}.brush-popover{position:absolute;left:168px;top:16px;width:280px;max-height:calc(100% - 32px);overflow-y:auto;overscroll-behavior:contain;background:var(--nn-panel);border-radius:12px;padding:14px;box-shadow:0 5px 25px #263d3025;border:1px solid var(--nn-line)}.brush-popover header{display:flex;align-items:center;justify-content:space-between;font-size:14px}.brush-popover header button{width:38px;height:38px;background:var(--nn-panel);font-size:23px}.drawing-field{display:flex;align-items:center;gap:6px;font-size:12px;margin:10px 0}.drawing-field input{margin-left:auto;width:74px;min-width:0;height:38px;border:1px solid var(--nn-line);border-radius:8px;padding:6px}.drawing-field input[type=text]{width:100px}.brush-popover input[type=range]{width:100%;height:30px;accent-color:var(--nn-accent)}.brush-swatches{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}.brush-swatches button{width:34px;height:34px;border-radius:50%;border:1px solid var(--nn-line);padding:0}.stroke-preview{background:var(--nn-soft);border-radius:10px;position:relative;margin-top:8px}.stroke-preview svg{width:100%;height:74px}.stroke-preview span{position:absolute;bottom:4px;right:8px;font-size:10px;color:var(--nn-muted)}.drawing-mode-label{position:absolute;top:5px;right:10px;font-size:10px;color:var(--nn-muted);background:var(--nn-workspace);padding:3px 5px;border-radius:4px}.finish-drawing{font-size:20px!important}.drawing-tools button:focus-visible,.drawing-tools input:focus-visible{outline:2px solid var(--nn-accent);outline-offset:2px}@media(max-width:600px){.brush-popover{left:76px;top:48px;width:calc(100% - 86px);max-height:calc(100% - 58px);z-index:2}.drawing-rail{left:6px;top:24px}.drawing-flyout{left:68px;top:24px;max-height:calc(100% - 36px)}.brush-popover{left:68px;width:calc(100% - 78px)}}
.finish-drawing span{font-size:11px;white-space:nowrap}
</style>
