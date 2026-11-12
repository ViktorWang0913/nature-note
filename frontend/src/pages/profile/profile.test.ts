import {afterEach,beforeEach,expect,test,vi} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn(),logout:vi.fn(),errorMessage:(e:any)=>e.message}));
vi.mock('../../components/flows',()=>({fail:vi.fn(),go:vi.fn(),confirm:vi.fn(),selectTab:vi.fn()}));
import definition from './logic';
import {request,logout} from '../../services/api';
import {confirm} from '../../components/flows';
function Page(){return {...definition,data:{...structuredClone(definition.data),loading:false,user:{id:'me',nickname:'原昵称'},nickname:'原昵称'},setData(patch:any){Object.assign(this.data,patch);}} as any;}
beforeEach(()=>{vi.resetAllMocks();vi.stubGlobal('wx',{showToast:vi.fn()});vi.stubGlobal('window',{scrollTo:vi.fn()});});
test('editing a nickname is explicit and cancelling restores the saved name',()=>{
 const page=Page();page.EditName();page.input({detail:{value:'新昵称'}});expect(page.data.editingName).toBe(true);expect(page.data.user.nickname).toBe('原昵称');page.CancelName();expect(page.data.nickname).toBe('原昵称');expect(page.data.editingName).toBe(false);expect(request).not.toHaveBeenCalled();
});
test('nickname save trims the name and ignores duplicate submissions',async()=>{
 let finish:(value:any)=>void=()=>{};vi.mocked(request).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve));
 const page=Page();page.EditName();page.data.nickname=' 新昵称 ';const first=page.save();await page.save();page.CancelName();expect(page.data.editingName).toBe(true);expect(request).toHaveBeenCalledTimes(1);expect(request).toHaveBeenCalledWith('/me','PATCH',{nickname:'新昵称'});
 finish({id:'me',nickname:'新昵称'});await first;expect(page.data.user.nickname).toBe('新昵称');expect(page.data.nickname).toBe('新昵称');expect(page.data.editingName).toBe(false);expect(page.data.saving).toBe(false);
});
test('failed or invalid nickname saves preserve the editor and the saved account data',async()=>{
 const page=Page();page.EditName();page.data.nickname='   ';await page.save();expect(request).not.toHaveBeenCalled();expect(page.data.nameError).toBeTruthy();
 page.data.nickname='x'.repeat(25);await page.save();expect(request).not.toHaveBeenCalled();
 vi.mocked(request).mockRejectedValueOnce(new Error('网络不可用'));page.data.nickname='新昵称';await page.save();expect(page.data.nameError).toBe('网络不可用');expect(page.data.nickname).toBe('新昵称');expect(page.data.user.nickname).toBe('原昵称');expect(page.data.editingName).toBe(true);expect(page.data.saving).toBe(false);
});
test('returning to My from achievements preserves the nickname draft',()=>{
 const page=Page();page.EditName();page.data.nickname='未保存的昵称';page.toggle();expect(page.data.section).toBe('achievements');page.onTabItemTap();expect(page.data.section).toBe('profile');expect(page.data.editingName).toBe(true);expect(page.data.nickname).toBe('未保存的昵称');
});
test('cancelling logout or account deletion sends no destructive request',async()=>{
 const page=Page();vi.mocked(confirm).mockResolvedValue(false);await page.logout();await page.CloseAccount();expect(logout).not.toHaveBeenCalled();expect(request).not.toHaveBeenCalled();
});

afterEach(()=>vi.unstubAllGlobals());
