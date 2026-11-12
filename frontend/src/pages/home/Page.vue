<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue';
import {chooseProject} from '../../services/projects';
import {go,fail} from '../../components/flows';
import bird from '../../assets/home/bird.webp';
import butterfly from '../../assets/home/butterfly.webp';
import magpie from '../../assets/home/magpie.webp';
import flowers from '../../assets/home/flowers.webp';
import moth from '../../assets/home/moth.webp';
import reedBird from '../../assets/home/reed-bird.webp';
import eagles from '../../assets/home/eagles.webp';
import egret from '../../assets/home/egret.webp';
const slides=[{src:bird,position:'42% 42%'},{src:butterfly,position:'50% 48%'},{src:magpie,position:'46% 72%'},{src:flowers,position:'50% 65%'},{src:moth,position:'48% 55%'},{src:reedBird,position:'48% 48%'},{src:eagles,position:'50% 46%'},{src:egret,position:'50% 70%'}];
const index=ref(0),busy=ref(false),loaded=ref(new Set([0,1]));
const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
let timer:ReturnType<typeof setInterval>|undefined,startX=0;
function Change(step:number){index.value=(index.value+step+slides.length)%slides.length;loaded.value=new Set([...loaded.value,index.value,(index.value+1)%slides.length]);}
function Schedule(){clearInterval(timer);if(!document.hidden&&!motion.matches)timer=setInterval(()=>Change(1),6000);}
function Swipe(event:TouchEvent){const delta=event.changedTouches[0].clientX-startX;if(Math.abs(delta)>45){Change(delta<0?1:-1);Schedule();}}
async function Record(){if(busy.value)return;busy.value=true;try{const id=await chooseProject();go('/pages/gps/index?projectId='+id);}catch(error){if(!(error as any)?.errMsg?.includes('cancel'))fail(error);}finally{busy.value=false;}}
onMounted(()=>{Schedule();document.addEventListener('visibilitychange',Schedule);motion.addEventListener('change',Schedule);});
onBeforeUnmount(()=>{clearInterval(timer);document.removeEventListener('visibilitychange',Schedule);motion.removeEventListener('change',Schedule);});
</script>
<template>
  <main class="home-scene" @touchstart.passive="startX=$event.touches[0].clientX" @touchend.passive="Swipe">
    <div class="home-photographs" aria-hidden="true"><template v-for="(slide,i) in slides" :key="slide.src"><img v-if="loaded.has(i)" :src="slide.src" :style="{objectPosition:slide.position}" :class="{visible:i===index}" :fetchpriority="i===0?'high':'auto'" alt=""></template></div>
    <div class="home-shade"></div>
    <header class="home-heading"><h1>今天，<br>去看看自然</h1></header>
    <div class="home-slide-controls"><span class="slide-dots" aria-label="背景轮播"><button v-for="(_,i) in slides" :key="i" :aria-label="'背景 '+(i+1)" :aria-current="i===index?'true':undefined" @click="Change(i-index);Schedule()"><i :class="{active:i===index}"></i></button></span></div>
    <section class="home-actions" aria-label="开始探索"><button class="home-action" :disabled="busy" @click="Record"><img src="/assets/icons/camera.svg" alt=""><span>{{busy?'正在打开…':'开始记录'}}</span></button><button class="home-action" @click="go('/pages/creation/index')"><img src="/assets/icons/pen.svg" alt=""><span>图片创作</span></button></section>
  </main>
</template>
<style scoped>
.home-scene{position:relative;isolation:isolate;height:calc(100dvh - var(--nn-tabs-height));min-height:440px;overflow:hidden;background:#526330;display:flex;flex-direction:column;color:#fffdf0}.home-photographs,.home-shade{position:absolute;inset:0;z-index:-2}.home-photographs img{position:absolute;width:100%;height:100%;max-width:none;opacity:0;transition:opacity 1.2s ease;object-fit:cover}.home-photographs img.visible{opacity:1}.home-shade{z-index:-1;background:linear-gradient(180deg,#14210c66 0%,transparent 36%,transparent 56%,#25331336 100%)}.home-heading{display:flex;align-items:flex-start;justify-content:space-between;padding:calc(24px + env(safe-area-inset-top)) 24px 0}.home-heading h1{margin:0;font-family:var(--nn-serif);font-size:clamp(29px,7.6vw,40px);font-weight:500;line-height:1.5;letter-spacing:2px;text-shadow:0 1px 8px #21300e35}.home-actions{position:relative;margin-top:0;padding:26px 20px 28px;background:#4d6029;border:1px solid #e4e6b747;border-bottom:0;border-radius:40px 40px 32px 32px;display:flex;flex-direction:column;gap:22px}.home-actions:before{content:'';position:absolute;top:-29px;left:calc(50% - 36px);width:72px;height:42px;background:#4d6029;border-radius:48px 48px 0 0;z-index:-1;border-top:1px solid #e4e6b747}.home-action{display:flex;align-items:center;justify-content:center;gap:24px;width:100%;min-height:76px;border-radius:999px;background:#faf9e9;color:#344424;padding:15px 24px;box-shadow:0 2px 0 #22321512;font-family:var(--nn-serif);font-size:29px;letter-spacing:2px}.home-action img{width:38px;height:38px;margin:0}.home-action span{padding-left:24px;border-left:1px solid #7d865540;line-height:1.3}.home-slide-controls{display:flex;justify-content:center;align-items:center;gap:8px;margin-top:auto;margin-bottom:40px;height:28px}.slide-dots{display:flex}.slide-dots button{display:grid;place-items:center;width:22px;min-height:32px;padding:0;background:transparent}.slide-dots i{height:4px;width:4px;border-radius:8px;background:#fff8;transition:width .2s}.slide-dots .active{width:15px;background:#fff}@media(min-width:700px){.home-heading{padding:40px 8vw}.home-heading h1{font-size:48px}.home-actions{width:480px;align-self:center;padding:28px;gap:20px}.home-scene{min-height:600px}.home-photographs img{object-position:center 42%!important}.home-action{min-height:76px}.home-slide-controls{margin-bottom:40px}}@media(max-height:700px){.home-heading{padding-top:18px}.home-heading h1{font-size:29px}.home-actions{padding:20px;gap:16px;border-radius:32px}.home-action{min-height:64px;font-size:25px}.home-action img{width:32px;height:32px}.home-slide-controls{margin-bottom:32px}}@media(prefers-reduced-motion:reduce){.home-photographs img,.slide-dots i{transition:none}}
</style>
