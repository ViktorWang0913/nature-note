<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { authState, Authenticate, AuthRequest, RefreshSession, LogoutSession } from './web/auth';
import { ui, ResolveDialog, ShowError, currentPage, Navigate, ShouldBlockNavigation } from './web/platform';
import { getActiveTrack, pauseTrack, syncTrack } from './engine/tracker';
import { flushQueue } from './services/sync';
const pageModules=import.meta.glob('./pages/*/Page.vue',{eager:true,import:'default'});
const route=ref(location.hash.slice(1)||'/pages/home/index');
const tabIndex=computed(()=>['home','gallery','atlas','community'].indexOf(route.value.split('?')[0].split('/')[2]));
const username=ref(''),password=ref(''),newPassword=ref(''),error=ref(''),busy=ref(false),dialogText=ref('');
const page=computed(()=>{const requestedName=route.value.split('?')[0].split('/')[2]||'home';const name=['post','publish','user'].includes(requestedName)?'community':requestedName;return pageModules['./pages/'+name+'/Page.vue']||pageModules['./pages/home/Page.vue'];});
function ChangeRoute(){const nextRoute=location.hash.slice(1)||'/pages/home/index';console.log('[开始] 浏览器导航保存检查');if(ShouldBlockNavigation()){console.log('[分支] 保留当前排版，等待保存决定');history.replaceState(history.state,'','#'+route.value);currentPage.pendingNavigation=()=>Navigate(nextRoute);currentPage.Leave();console.log('[结束] 浏览器导航保存检查；提前等待');return;}console.log('[分支] 切换页面；[结束] 浏览器导航保存检查');route.value=nextRoute;history.replaceState({naturePage:route.value!='/pages/home/index'},'');window.scrollTo(0,0);}
async function Submit(){busy.value=true;error.value='';const action=authState.mustChange?AuthRequest('password',{current_password:password.value,new_password:newPassword.value}).then(()=>RefreshSession()):Authenticate(username.value,password.value);await action.then(()=>{password.value='';newPassword.value='';console.log('[开始] 登录后权限路由');if(authState.user?.restricted){console.log('[分支] 账号申诉');Navigate('/pages/support/index',true);}else{console.log('[分支] 普通账号');}console.log('[结束] 登录后权限路由');},failure=>{error.value=failure.message;});busy.value=false;}
function SubmitDialog(confirm:boolean,tapIndex?:number){ResolveDialog({confirm,cancel:!confirm,tapIndex,content:dialogText.value});dialogText.value='';}
function ChangePassword(){authState.mustChange=true;}
function InterruptTrack(){console.log('[开始] 轨迹中断检查');if(getActiveTrack()?.status==='recording'){console.log('[分支] 保存并暂停');pauseTrack().then(undefined,ShowError);}else{console.log('[分支] 未在记录');}console.log('[结束] 轨迹中断检查');}
function Visibility(){console.log('[开始] 页面可见性');if(document.hidden){console.log('[分支] 暂停前台定位');InterruptTrack();}else{console.log('[分支] 恢复查询和同步');RefreshSession().then(()=>flushQueue()).then(()=>syncTrack()).then(undefined,ShowError);}console.log('[结束] 页面可见性');}
function Reconnect(){RefreshSession().then(()=>flushQueue()).then(()=>syncTrack()).then(undefined,ShowError);}
onMounted(()=>{window.addEventListener('hashchange',ChangeRoute);window.addEventListener('nature-change-password',ChangePassword);window.addEventListener('nature-location-interrupted',InterruptTrack);window.addEventListener('online',Reconnect);document.addEventListener('visibilitychange',Visibility);});
onBeforeUnmount(()=>{window.removeEventListener('hashchange',ChangeRoute);window.removeEventListener('nature-change-password',ChangePassword);window.removeEventListener('online',Reconnect);document.removeEventListener('visibilitychange',Visibility);});
</script>
<template>
  <main v-if="!authState.user || authState.mustChange" class="login-page">
    <div class="login-brand">自然记<span>记录身边的自然</span></div>
    <form class="login-card" @submit.prevent="Submit">
      <h1>{{authState.mustChange?'修改登录密码':'登录自然记'}}</h1>
      <p>{{authState.mustChange?'请设置至少12位的新密码。':'请使用管理员分配的测试账号。'}}</p>
      <label v-if="!authState.mustChange">账号<input v-model="username" autocomplete="username" required maxlength="80" autocapitalize="none" spellcheck="false"></label>
      <label>{{authState.mustChange?'当前密码':'密码'}}<input v-model="password" type="password" autocomplete="current-password" required maxlength="200"></label>
      <label v-if="authState.mustChange">新密码<input v-model="newPassword" type="password" autocomplete="new-password" required minlength="12" maxlength="200"></label>
      <p v-if="error" class="login-error" role="alert">{{error}}</p>
      <button class="primary" :disabled="busy">{{busy?'正在处理…':authState.mustChange?'保存新密码':'登录'}}</button>
      <button v-if="authState.user" type="button" @click="LogoutSession().then(undefined,ShowError)">退出登录</button>
    </form>
  </main>
  <component v-else :is="page" :key="route+'-'+authState.user.id"/>
  <nt-bottom v-if="authState.user && !authState.mustChange && tabIndex>=0 && !ui.tabHidden" :selected="tabIndex"/>
  <div v-if="ui.toast" class="web-toast" role="status">{{ui.toast}}</div>
  <div v-if="ui.dialog" class="web-dialog-backdrop" @click.self="SubmitDialog(false)">
    <section class="web-dialog" role="dialog" aria-modal="true" :aria-label="ui.dialog.title||'选择操作'">
      <h2 v-if="ui.dialog.title">{{ui.dialog.title}}</h2><p v-if="ui.dialog.content">{{ui.dialog.content}}</p>
      <form v-if="ui.dialog.kind==='modal'" @submit.prevent="SubmitDialog(true)">
        <input v-if="ui.dialog.editable" v-model="dialogText" :type="ui.dialog.inputType||'text'" :placeholder="ui.dialog.placeholderText||'请输入'" autofocus>
        <div class="web-dialog-actions"><button v-if="ui.dialog.showCancel!==false" type="button" @click="SubmitDialog(false)">{{ui.dialog.cancelText||'取消'}}</button><button class="primary">{{ui.dialog.confirmText||'确定'}}</button></div>
      </form>
      <template v-else><button v-for="(item,index) in ui.dialog.itemList" :key="index" @click="SubmitDialog(true,index)">{{item}}</button><button @click="SubmitDialog(false)">取消</button></template>
    </section>
  </div>
  <div v-if="ui.preview" class="web-preview" role="dialog" @click="ui.preview=''"><button aria-label="关闭">×</button><img :src="ui.preview" alt="图片预览"></div>
</template>
