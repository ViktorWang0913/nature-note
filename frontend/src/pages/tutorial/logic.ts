import {chooseProject} from '../../services/projects';
import {request} from '../../services/api';import {fail,go,pickPhoto,decorateAsset} from '../../components/flows';
export default {
 data:{step:0,photos:[],illustration:'',template:'',titles:['记录观察','选择模板','生成笔记'],captions:['沿途添加观察点，拍下照片，记下地点与发现。','结束观察后，为笔记选择喜欢的风格与画幅。','核对路线、照片与文字，再生成并保存自然笔记。']},
 async onLoad(){try{const [a,t]:any[]=await Promise.all([request('/assets?limit=100'),request('/templates')]);const all=a.items.map(decorateAsset);this.setData({photos:all.filter((x:any)=>x.source==='photo'||x.id==='public-photo-bulbul-1'),illustration:all.find((x:any)=>x.id==='public-bulbul')?.url||'',template:t.items[0]?.cover_url||''});}catch(e){fail(e);}},
 change(e:any){this.setData({step:e.detail.current});},next(){this.setData({step:Math.min(2,this.data.step+1)});},previous(){this.setData({step:Math.max(0,this.data.step-1)});},
 async begin(){const id=await chooseProject();go('/pages/gps/index?projectId='+id);}
};
