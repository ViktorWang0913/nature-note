<script setup lang="ts">
defineProps<{state:any}>();
const emit=defineEmits(['action']);
function Dispatch(name:string,event?:Event){emit('action',name,event);}
</script>
<template>
  <div v-if="state.panel==='style'" class="vector-settings">
    <p>{{state.selectedLabel}}样式</p>
    <label>不透明度 <input type="number" aria-label="图层不透明度数值" min="0" max="100" :value="state.styleForm.opacity" data-field="opacity" @change="Dispatch('ApplyStyle',$event)" :disabled="state.selectedLocked">%</label>
    <input type="range" aria-label="图层不透明度" min="0" max="100" :value="state.styleForm.opacity" data-field="opacity" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)" :disabled="state.selectedLocked">
    <label v-if="state.selectedType==='stroke'">笔画颜色<input type="color" aria-label="笔画颜色" :value="state.styleForm.color" data-field="color" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)" :disabled="state.selectedLocked"></label>
    <template v-if="state.selectedType==='shape'">
      <label v-if="!state.selectedLine">填充颜色<input type="color" aria-label="填充颜色" :value="state.styleForm.fill==='none'?'#9eb594':state.styleForm.fill" data-field="fill" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)"><button data-field="fill" data-value="none" @click="Dispatch('ApplyStyle',$event)" :class="{chosen:state.styleForm.fill==='none'}">无填充</button></label>
      <label>描边颜色<input type="color" aria-label="描边颜色" :value="state.styleForm.stroke==='none'?'#416b55':state.styleForm.stroke" data-field="stroke" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)"><button v-if="!state.selectedLine" data-field="stroke" data-value="none" @click="Dispatch('ApplyStyle',$event)" :class="{chosen:state.styleForm.stroke==='none'}">无描边</button></label>
      <label>描边粗细 <input type="number" aria-label="描边粗细数值" min="1" max="40" :value="state.styleForm.lineWidth" data-field="lineWidth" @change="Dispatch('ApplyStyle',$event)">px</label><input aria-label="描边粗细" type="range" min="1" max="40" :value="state.styleForm.lineWidth" data-field="lineWidth" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)">
      <label>虚线<input type="checkbox" aria-label="虚线" :checked="state.styleForm.dashed" data-field="dashed" @change="Dispatch('ApplyStyle',$event)"></label>
      <label v-if="!state.selectedLine">锁定比例<input type="checkbox" aria-label="锁定比例" :checked="state.styleForm.lockRatio" data-field="lockRatio" @change="Dispatch('ApplyStyle',$event)"></label>
      <template v-if="state.selectedShape==='rounded'"><label>圆角大小 <output>{{state.styleForm.radius}}%</output></label><input aria-label="圆角大小" type="range" min="0" max="50" :value="state.styleForm.radius" data-field="radius" @input="Dispatch('StyleInput',$event)" @change="Dispatch('FinishStyle',$event)"></template>
    </template>
    <button class="primary" @click="Dispatch('ClosePanel',$event)">完成</button>
  </div>
  <div v-if="state.panel==='paper'" class="vector-settings">
    <template v-if="state.manual">
      <label>画布比例</label><div class="paper-presets"><button v-for="(preset,index) in state.paperPresets" :key="preset.label" :data-index="index" @click="Dispatch('PaperPreset',$event)">{{preset.label}}</button></div>
      <label>宽度<input type="number" aria-label="画布宽度" min="100" max="4096" step="1" :value="state.paperForm.width" data-field="width" @input="Dispatch('PaperInput',$event)">px</label>
      <label>高度<input type="number" aria-label="画布高度" min="100" max="4096" step="1" :value="state.paperForm.height" data-field="height" @input="Dispatch('PaperInput',$event)">px</label>
      <button @click="Dispatch('SwapPaper',$event)">横竖切换</button><p>宽高 100–4096 px。尺寸调整不缩放内容。</p>
    </template>
    <template v-else><p>GPS 背景笔记固定为 1024 × 1536 像素。</p><button @click="Dispatch('Background',$event)">制作／更换背景</button></template>
    <label>背景颜色<input type="color" aria-label="画布背景颜色" :value="state.paperForm.background" data-field="background" @input="Dispatch('PaperInput',$event)"></label>
    <div class="paper-colors"><button v-for="color in state.colors" :key="color" :style="{background:color}" :aria-label="'背景 '+color" @click="emit('action','PaperInput',{currentTarget:{dataset:{field:'background'}},detail:{value:color}})"></button></div>
    <div class="paper-actions"><button @click="Dispatch('ClosePanel',$event)">取消</button><button class="primary" @click="Dispatch('ApplyPaper',$event)">应用</button></div>
  </div>
</template>
<style scoped>
.vector-settings{overflow:auto;max-height:65dvh;padding:0 3px 12px}.vector-settings label{display:flex;align-items:center;gap:9px;font-size:13px;min-height:48px}.vector-settings output{margin-left:auto;font-variant-numeric:tabular-nums}.vector-settings input[type=range]{width:100%;height:36px;accent-color:var(--nn-accent)}.vector-settings input[type=color]{width:52px;height:40px;margin-left:auto;padding:3px;border:1px solid var(--nn-line);border-radius:7px}.vector-settings input[type=number]{width:110px;height:44px;margin-left:auto;padding:8px;border:1px solid var(--nn-line);border-radius:7px}.vector-settings input[type=checkbox]{width:24px;height:24px;margin-left:auto;accent-color:var(--nn-accent)}.vector-settings button{font-size:12px;min-height:44px;padding:9px 13px;background:var(--nn-soft);border-radius:8px}.vector-settings .chosen{background:var(--nn-selected)}.vector-settings .primary{background:var(--nn-accent);color:white}.vector-settings>button.primary{width:100%;margin-top:15px}.vector-settings p{font-size:12px;line-height:1.8;color:var(--nn-muted)}.paper-presets{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.paper-actions{display:flex;gap:10px;margin-top:14px}.paper-actions button{flex:1}.paper-colors{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.paper-colors button{width:36px;min-height:36px;border-radius:50%;border:1px solid var(--nn-line);padding:0}
</style>
