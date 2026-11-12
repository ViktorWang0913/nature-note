import {beforeEach,expect,test,vi} from 'vitest';
vi.mock('./platform',()=>({Navigate:vi.fn(),WindowInfo:vi.fn(),ShowError:vi.fn(),currentPage:{onTabItemTap:vi.fn()}}));
import {NtBottom} from './components';
import {Navigate,currentPage} from './platform';
beforeEach(()=>vi.clearAllMocks());
test('main navigation uses a single-person My tab instead of community',()=>{
 const render=(NtBottom as any).setup({selected:3});const buttons=render().children;
 expect(buttons.map((button:any)=>button.children[1].children)).toEqual(['首页','笔记','图鉴','我的']);
 expect(buttons[3].children[0].props.src).toBe('/assets/icons/profile.svg');expect(buttons[3].props['aria-current']).toBe('page');
 buttons[3].props.onClick();expect(currentPage.onTabItemTap).toHaveBeenCalledWith({index:3});expect(Navigate).toHaveBeenCalledWith('/pages/profile/index');
});
test('switching to My uses the normal navigation guard',()=>{
 const render=(NtBottom as any).setup({selected:1});render().children[3].props.onClick();expect(currentPage.onTabItemTap).not.toHaveBeenCalled();expect(Navigate).toHaveBeenCalledWith('/pages/profile/index');
});

test('shared headings support page titles without a back action and preserve local back handlers',async()=>{
 const {NtHeader}=await import('./components');const emit=vi.fn(),back=vi.fn();vi.stubGlobal('wx',{navigateBack:back});
 const props:any={title:'我的物种图鉴',description:'收藏自然发现',page:true,back:false,brand:false};
 const render=(NtHeader as any).setup(props,{emit,slots:{}});const heading=render();
 expect(heading.props.class).toContain('web-page-header');const content=heading.children[0].children;expect(content[0]).toBeNull();expect(content[1].children[0].type).toBe('h1');expect(content[1].children[0].children).toBe('我的物种图鉴');expect(content[1].children[1].children).toBe('收藏自然发现');
 props.page=false;props.back=true;props.localBack=true;render().children[0].children[0].props.onClick();expect(emit).toHaveBeenCalledWith('back');expect(back).not.toHaveBeenCalled();
 props.localBack=false;render().children[0].children[0].props.onClick();expect(back).toHaveBeenCalledOnce();vi.unstubAllGlobals();
});
