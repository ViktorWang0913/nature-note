import {beforeEach,expect,test,vi} from 'vitest';
import {ref,nextTick} from 'vue';
const hooks=vi.hoisted(()=>({mounted:[] as any[],unmounted:[] as any[]}));
vi.mock('vue',async original=>({...await original<typeof import('vue')>(),onMounted:(fn:any)=>hooks.mounted.push(fn),onBeforeUnmount:(fn:any)=>hooks.unmounted.push(fn)}));
vi.mock('./platform',()=>({SelectorQuery:vi.fn(),SetCurrentPage:vi.fn(),ShowError:vi.fn(),WindowInfo:()=>({}),ui:{tabHidden:true}}));
import {UsePage} from './page';
import {SetCurrentPage,ui} from './platform';
beforeEach(()=>{vi.clearAllMocks();hooks.mounted=[];hooks.unmounted=[];vi.stubGlobal('window',{addEventListener:vi.fn(),removeEventListener:vi.fn()});vi.stubGlobal('visualViewport',{addEventListener:vi.fn(),removeEventListener:vi.fn()});vi.stubGlobal('location',{hash:'#/pages/gps/index?projectId=host'});});
test('embedded pages keep host routing and tab visibility and receive explicit options',async()=>{
  const onLoad=vi.fn(),onShow=vi.fn(),onHide=vi.fn(),active=ref(true);
  UsePage({data:{},onLoad,onShow,onHide,onReady(){this.getTabBar().setData({hidden:false});}},{embedded:true,query:{id:'asset'},active:()=>active.value});
  await hooks.mounted[0]();
  expect(onLoad).toHaveBeenCalledWith({id:'asset'});expect(SetCurrentPage).not.toHaveBeenCalled();expect(ui.tabHidden).toBe(true);
  active.value=false;await nextTick();expect(onHide).toHaveBeenCalledOnce();
  active.value=true;await nextTick();expect(onShow).toHaveBeenCalledTimes(2);
});
test('normal pages remain the registered navigation owner',async()=>{
  const onLoad=vi.fn();UsePage({data:{},onLoad});await hooks.mounted[0]();
  expect(SetCurrentPage).toHaveBeenCalledOnce();expect(onLoad).toHaveBeenCalledWith({projectId:'host'});
});
