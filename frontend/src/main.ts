import { createApp } from 'vue';
import { InitializeStorage } from './web/storage';
import { InstallPlatform, ShowError } from './web/platform';
import { RefreshSession } from './web/auth';
import * as components from './web/components';
import './styles/app.css';
import './styles/workspace.css';
import './web/browser.css';
import './styles/specimen.css';

// 主程序
InstallPlatform();
await InitializeStorage();
await RefreshSession();
const {default:App}=await import('./App.vue');
const app=createApp(App);
app.config.errorHandler=ShowError;
console.log('[开始] 网页组件注册');
Object.entries(components).forEach(([name,component],index,list)=>{console.log(`[开始] 组件 ${index+1}/${list.length}`);app.component(name,component);console.log(`[结束] 组件 ${index+1}/${list.length}`);});
console.log('[结束] 网页组件注册');
app.mount('#app');
console.log('[开始] 离线应用支持');
if(import.meta.env.PROD&&'serviceWorker' in navigator){console.log('[分支] 注册应用外壳缓存');navigator.serviceWorker.register('/sw.js').then(undefined,ShowError);}else{console.log('[分支] 开发环境直接加载');}
console.log('[结束] 离线应用支持');
