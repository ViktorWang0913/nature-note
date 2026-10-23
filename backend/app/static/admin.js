// 路径与参数
const apiBase = '/api/admin';
const sections = {overview:'概览',generated:'作品与素材',projects:'设计作品',assets:'上传与编辑',runtime:'服务配置',users:'用户',tasks:'AI 任务',charges:'费用对账',species:'总图鉴',posts:'帖子审核',comments:'评论审核',reports:'举报',feedback:'意见反馈',announcements:'公告',archives:'删除归档',audit:'操作记录'};
let activeSection='overview',nextCursor=null,selected=null;
const columnLabels={username:'登录账号',id:'编号',user_id:'用户',name:'名称',title:'标题',text:'内容',created_at:'创建时间',status:'状态',state:'结算状态',active:'可用',provider_id:'模型',actual_micros:'实际费用',reserved_micros:'暂占金额',review_status:'审核状态',group_key:'汇总分组',scientific_name:'学名',category:'分类',task_id:'任务编号',reason:'原因',action:'操作',resource_type:'内容类型',resource_id:'内容编号',expires_at:'保留期限'};

// 主程序
document.querySelector('#loginForm').addEventListener('submit',Login);
document.querySelector('#passwordForm').addEventListener('submit',ChangePassword);
document.querySelector('#quotaForm').addEventListener('submit',ChangeQuota);
document.querySelector('#announcementForm').addEventListener('submit',CreateAnnouncement);
document.querySelector('#refresh').addEventListener('click',()=>Load());
document.querySelector('#next').addEventListener('click',()=>{currentPage+=1;pageCursors[currentPage]=nextCursor;Load(nextCursor,true);});
document.querySelector('#logout').addEventListener('click',()=>Request('/logout','POST',{}).then(()=>location.reload(),ShowError));
BuildNavigation();
document.querySelector('#filterForm').addEventListener('submit',event=>{event.preventDefault();Load();});
document.querySelector('#resetFilters').addEventListener('click',()=>{document.querySelector('#filterForm').reset();Load();});
document.querySelector('#closeDetail').addEventListener('click',()=>{detailEpoch+=1;document.querySelector('#detailDialog').close();});
document.querySelector('#detailDialog').addEventListener('cancel',()=>{detailEpoch+=1;});
document.querySelector('#previous').addEventListener('click',()=>{currentPage-=1;Load(pageCursors[currentPage],true);});
Request('/overview').then(OpenWorkspace,error=>{
 console.log('[开始] 初始管理会话');
 if(error.code==='admin_login_required'){console.log('[分支] 未登录');document.querySelector('#notice').textContent='请使用独立管理员账号登录';}
 else{console.log('[分支] 显示实际错误');ShowError(error);}
 console.log('[结束] 初始管理会话');
});

// 自编函数
function Element(tag,text=''){const element=document.createElement(tag);element.textContent=text;return element;}
function ShowError(error){
 document.querySelector('#notice').textContent=error.message||String(error);
 console.log('[开始] 详情错误提示');
 if(document.querySelector('#detailDialog').open){console.log('[分支] 在当前详情显示错误');const message=Element('p',error.message||String(error));message.className='errorMessage';message.setAttribute('role','alert');document.querySelector('#recordInfo').prepend(message);}
 else{console.log('[分支] 显示页面错误');}
 console.log('[结束] 详情错误提示');
 console.log('[开始] 管理会话过期处理');
 if(error.code==='admin_login_required'){
  console.log('[分支] 返回登录页');document.querySelector('#detailDialog').close();detailEpoch+=1;
  document.querySelector('#workspace').hidden=true;document.querySelector('#loginPanel').hidden=false;
  document.querySelector('#logout').hidden=true;
 }else{console.log('[分支] 保留当前登录状态');}
 console.log('[结束] 管理会话过期处理');
 console.log('[开始] 密码更新入口检查');
 if(error.code==='change_password_required'){console.log('[分支] 恢复密码更新界面');document.querySelector('#loginPanel').hidden=true;document.querySelector('#workspace').hidden=true;document.querySelector('#passwordPanel').hidden=false;}
 else{console.log('[分支] 保留当前界面');}
 console.log('[结束] 密码更新入口检查');
}
async function Request(path,method='GET',body){
 const response=await fetch(apiBase+path,{method,headers:{'Content-Type':'application/json','X-Admin-Action':'nature-note'},body:JSON.stringify(body)});
 let result;
 try{result=await response.json();}catch(readError){throw new Error('服务响应异常（HTTP '+response.status+'），请稍后重试或检查服务状态');}
 console.log('[开始] 管理响应检查');
 if(!response.ok){console.log('[分支] 请求被拒绝；[结束] 管理响应检查');const error=new Error(result.detail?.message||'操作未完成');error.code=result.detail?.code;throw error;}
 console.log('[分支] 请求完成');console.log('[结束] 管理响应检查');return result;
}
function FormValues(form){return Object.fromEntries(new FormData(form).entries());}
function Login(event){event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;Request('/login','POST',FormValues(event.target)).then(result=>{
 console.log('[开始] 登录后界面选择');
 if(result.must_change){console.log('[分支] 首次修改密码');document.querySelector('#loginPanel').hidden=true;document.querySelector('#passwordPanel').hidden=false;}
 else{console.log('[分支] 打开管理界面');OpenWorkspace();}
 console.log('[结束] 登录后界面选择');event.target.reset();
},ShowError).finally(()=>{button.disabled=false;});}
function ChangePassword(event){event.preventDefault();Request('/password','POST',FormValues(event.target)).then(()=>{event.target.reset();OpenWorkspace();},ShowError);}
function OpenWorkspace(){document.querySelector('#loginPanel').hidden=true;document.querySelector('#passwordPanel').hidden=true;document.querySelector('#workspace').hidden=false;document.querySelector('#logout').hidden=false;Load();}
async function Load(cursor=null,keepPage=false){
 const previousPage=currentPage;
 await LoadWorkspace(cursor).catch(ShowError);
 console.log('[开始] 首页面码恢复');
 if(keepPage&&previousPage===0){console.log('[分支] 返回第一页');currentPage=0;}
 else{console.log('[分支] 保留当前页');}
 console.log('[结束] 首页面码恢复');
}
function RenderRows(items){
 const preferred=['username','name','title','provider_id','state','status','review_status','actual_micros','reserved_micros','active','scientific_name','text','reason','user_id','id','task_id','created_at'];
 const keys=preferred.filter(key=>key in (items[0]||{})).slice(0,7);
 const head=Element('tr');console.log('[开始] 表头绘制');keys.forEach((key,index)=>{console.log(`[开始] 表头 ${index+1}/${keys.length}`);head.append(Element('th',columnLabels[key]));console.log(`[结束] 表头 ${index+1}/${keys.length}`);});console.log('[结束] 表头绘制');document.querySelector('#columns').replaceChildren(head);
 document.querySelector('#empty').hidden=items.length>0;console.log('[开始] 表格记录绘制');
 items.forEach((record,index)=>{
  console.log(`[开始] 记录 ${index+1}/${items.length}`);const row=Element('tr');console.log('[开始] 记录单元格绘制');
  keys.forEach((key,columnIndex)=>{console.log(`[开始] 单元格 ${columnIndex+1}/${keys.length}`);let value=record[key];console.log('[开始] 金额格式检查');if(key.endsWith('_micros')&&value!==null){console.log('[分支] 人民币金额');value='¥'+(value/1000000).toFixed(6);}else{console.log('[分支] 普通数据');}console.log('[结束] 金额格式检查');row.append(Element('td',String(({pending:activeSection==='charges'?'待核对':'待审核',approved:'已通过',rejected:'未通过',queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已停止',settled:'已结算',submitted:'已提交',reserved:'已预占',open:'待处理',processing:'处理中',resolved:'已解决',draft:'草稿',published:'已发布',withdrawn:'已撤回',qwen:'识别与问答',image:'生图与润色'})[value]??value??(key.endsWith('_micros')?'待核对':'—'))));console.log(`[结束] 单元格 ${columnIndex+1}/${keys.length}`);});console.log('[结束] 记录单元格绘制');
  row.addEventListener('click',()=>SelectRecord(record));document.querySelector('#rows').append(row);console.log(`[结束] 记录 ${index+1}/${items.length}`);
 });console.log('[结束] 表格记录绘制');
}
function AddAction(label,handler){const button=Element('button',label);button.addEventListener('click',handler);document.querySelector('#actionButtons').append(button);}
function SelectRecord(record){
 OpenDrawer(record.title||record.name||'记录详情');
 Metadata(document.querySelector('#recordInfo'),Object.entries(record).filter(([key,value])=>['title','name','text','reason','status','state','created_at','user_id','task_id'].includes(key)&&typeof value!=='object').map(([key,value])=>[columnLabels[key]||key,key==='created_at'?FormatTime(value):statusNames[value]||value]));
 SelectLegacyRecord(record);
}
function SelectLegacyRecord(record){
 selected=record;document.querySelector('#detail').textContent=JSON.stringify(record,null,2);document.querySelector('#actionButtons').replaceChildren();
 console.log('[开始] 记录操作选择');
 if(activeSection==='users'){
  AddAction('重置登录密码',()=>ResetWebPassword(record));
  console.log('[开始] 注销账户操作');if(record.deleted_at){console.log('[分支] 提供重新发放');AddAction('清理完成后重新发放',()=>ResetWebPassword(record,true));}else{console.log('[分支] 普通账号');}console.log('[结束] 注销账户操作');
  console.log('[分支] 用户管理');document.querySelector('#quotaForm [name=user_id]').value=record.id;
  AddAction(record.active?'停用账号':'恢复账号',()=>SubmitPrompt('/users/'+record.id+'/status',{active:!record.active},'reason','请输入操作原因'));
 }else if(activeSection==='charges'){
  console.log('[分支] 费用核对');AddAction('录入实际账单',async()=>{const amount=await AskDialog('服务商账单实际金额（元），不能填写估计值');console.log('[开始] 对账金额确认');if(amount===null){console.log('[分支] 取消');console.log('[结束] 对账金额确认；提前结束');return;}console.log('[分支] 继续录入凭据');console.log('[结束] 对账金额确认');SubmitPrompt('/charges/'+record.task_id+'/settle',{amount},'evidence','服务商账单编号及核对说明');});
 }else if(['posts','comments'].includes(activeSection)){
  console.log('[分支] 内容审核');console.log('[开始] 帖子图片预览');if(activeSection==='posts'){console.log('[分支] 显示独立审核图片');PreviewImages('post',record.id,record.images.length);}else{console.log('[分支] 文字评论');}console.log('[结束] 帖子图片预览');const kind=activeSection==='posts'?'post':'comment';AddAction('审核通过',()=>Request('/review/'+kind+'/'+record.id,'POST',{status:'approved',reason:''}).then(()=>Load(),ShowError));AddAction('拒绝公开',()=>SubmitPrompt('/review/'+kind+'/'+record.id,{status:'rejected'},'reason','请输入未通过原因'));
 }else if(activeSection==='reports'){
  console.log('[分支] 举报处理');AddAction('处理并下架目标',()=>SubmitPrompt('/reports/'+record.id,{action:'hide'},'reason','处理原因'));AddAction('驳回举报',()=>SubmitPrompt('/reports/'+record.id,{action:'dismiss'},'reason','驳回原因'));
 }else if(activeSection==='announcements'){
  console.log('[分支] 公告修改');AddAction('撤回公告',()=>Request('/announcements/'+record.id,'PUT',{title:record.title,text:record.text,user_ids:record.user_ids,starts_at:record.starts_at,ends_at:record.ends_at,status:'withdrawn'}).then(()=>Load(),ShowError));AddAction('编辑公告',()=>{const form=document.querySelector('#announcementForm');form.elements.title.value=record.title;form.elements.text.value=record.text;form.elements.user_ids.value=record.user_ids.join(',');form.dataset.editId=record.id;document.querySelector('#detailDialog').close();document.querySelector('#notice').textContent='修改后重新选择生效时间，提交前会预览';});
 }else if(activeSection==='archives'){
  console.log('[分支] 删除归档');AddAction('预览归档首张图片',()=>PreviewImages('archive',record.id,1));AddAction('永久清理此归档',async()=>{const password=await ConfirmPassword();console.log('[开始] 永久清理确认');if(password&&await ConfirmDialog('永久清理归档 '+record.id+'？仍在笔记或其他会话中使用的内容会保留。')){console.log('[分支] 提交身份校验与明确目标');Request('/archives/'+record.id+'/purge','POST',{password,confirmation:record.id}).then(()=>Load(),ShowError);}else{console.log('[分支] 取消');}console.log('[结束] 永久清理确认');});
 }else if(activeSection==='feedback'){
  console.log('[分支] 反馈回复');AddAction('回复并标记处理中',()=>SubmitPrompt('/feedback/'+record.id+'/reply',{status:'processing'},'text','回复内容'));AddAction('回复并解决',()=>SubmitPrompt('/feedback/'+record.id+'/reply',{status:'resolved'},'text','回复内容'));
 }else if(activeSection==='species'){
  console.log('[分支] 总图鉴');AddAction('查看照片与拍摄者',()=>LoadAtlasPhotos(record.group_key));AddAction('调整汇总分组',()=>SubmitPrompt('/atlas/group',{species_ids:[record.id]},'group_key','输入要归入的分组编号（不会修改个人图鉴）'));AddAction('向用户发送更正建议',()=>SuggestCorrection(record));
 }else{console.log('[分支] 只读详情');}
 console.log('[结束] 记录操作选择');
}
async function SubmitPrompt(path,body,key,label){const value=await AskDialog(label);console.log('[开始] 管理操作输入确认');if(value===null||!value.trim()){console.log('[分支] 取消或空值');console.log('[结束] 管理操作输入确认；提前结束');return;}console.log('[分支] 提交管理操作');console.log('[结束] 管理操作输入确认');return Request(path,'POST',{...body,[key]:value}).then(()=>Load(),ShowError);}
function ChangeQuota(event){event.preventDefault();const values=FormValues(event.target);values.user_id=values.user_id||null;Request('/quotas','POST',values).then(async result=>{await Load();document.querySelector('#notice').textContent=result.mode==='topup'?'今日额度已追加，用户刷新额度后可见':'额度调整已保存，将于北京时间 '+result.effective_day+' 生效；如需今天生效，请使用“追加今日额度”。';},ShowError);}
async function CreateAnnouncement(event){event.preventDefault();const values=FormValues(event.target);values.user_ids=values.user_ids.split(',').map(value=>value.trim()).filter(Boolean);values.starts_at=new Date(values.starts_at).toISOString();values.ends_at=new Date(values.ends_at).toISOString();console.log('[开始] 公告预览确认');if(!await ConfirmDialog(values.title+'\n\n'+values.text+'\n\n接收范围：'+(values.user_ids.join(',')||'全部用户'))){console.log('[分支] 取消发布');console.log('[结束] 公告预览确认；提前结束');return;}console.log('[分支] 保存公告');console.log('[结束] 公告预览确认');const editId=event.target.dataset.editId;Request(editId?'/announcements/'+editId:'/announcements',editId?'PUT':'POST',values).then(()=>{delete event.target.dataset.editId;event.target.reset();Load();},ShowError);}

function PreviewImages(kind,id,count){
 console.log(`[开始] 管理图片预览，共 ${count} 张`);
 for(let imageIndex=0;imageIndex<count;imageIndex++){
  console.log(`[开始] 管理图片 ${imageIndex+1}/${count}`);const image=Element('img');image.src=apiBase+'/media/'+kind+'/'+encodeURIComponent(id)+'/'+imageIndex;image.alt='管理内容预览';image.style.maxWidth='240px';image.style.maxHeight='240px';document.querySelector('#detailMedia').append(image);console.log(`[结束] 管理图片 ${imageIndex+1}/${count}`);
 }
 console.log('[结束] 管理图片预览');
}
async function ConfigureProvider(provider){
 const concurrency=await AskDialog('全站 '+provider.id+' 同时执行的任务数',String(provider.concurrency));
 const reserve=await AskDialog('价格缺失时的暂占金额（元）；已配置单价的请求自动计算预留，暂占不代表实际扣费',String(provider.reserve_micros/1000000));
 const context=await AskDialog('模型上下文 token 上限，不能超过部署的模型上限',String(provider.context_limit));
 const output=await AskDialog('预留回答 token 数',String(provider.output_limit));
 console.log('[开始] 模型配置确认');
 if([concurrency,reserve,context,output].some(value=>value===null)){console.log('[分支] 已取消');console.log('[结束] 模型配置确认；提前结束');return;}
 console.log('[分支] 提交后台验证');console.log('[结束] 模型配置确认');
 Request('/providers/'+provider.id,'PUT',{enabled:provider.enabled,message:provider.message,concurrency:Number(concurrency),reserve_micros:Math.round(Number(reserve)*1000000),context_limit:Number(context),output_limit:Number(output)}).then(()=>Load(),ShowError);
}

async function ConfigurePricing(providerId){
 const result=await Request('/pricing/'+providerId);
 const pricing=result.pricing;
 const fields=providerId==='qwen'?[
  ['input_rate','输入单价（元/百万 token）'],['output_rate','输出单价（元/百万 token）'],
  ['tier_threshold','长上下文档位起点（输入 token，超过后整次使用高档）'],
  ['high_input_rate','高档输入单价（元/百万 token）'],['high_output_rate','高档输出单价（元/百万 token）']
 ]:[['per_call','每次成功生图单价（人民币元，须与当前模型和规格一致）']];
 const values={};
 console.log(`[开始] 单价输入，共 ${fields.length} 项`);
 for(let fieldIndex=0;fieldIndex<fields.length;fieldIndex++){
  const [field,label]=fields[fieldIndex];
  console.log(`[开始] 单价 ${fieldIndex+1}/${fields.length}`);
  const value=await AskDialog(result.model+'：'+label+'；留空表示未知，不能填 0 代替未知',String(pricing[field]??''));
  console.log('[开始] 单价输入确认');
  if(value===null){console.log('[分支] 取消');console.log('[结束] 单价输入确认');console.log(`[结束] 单价 ${fieldIndex+1}/${fields.length}；提前结束单价输入`);return;}
  else{console.log('[分支] 保存当前输入');}
  console.log('[结束] 单价输入确认');
  values[field]=value.trim()===''?null:value.trim();
  console.log(`[结束] 单价 ${fieldIndex+1}/${fields.length}`);
 }
 console.log('[结束] 单价输入');
 const evidence=await AskDialog('请输入合同/价目表依据。新价格只适用于新任务，旧任务使用原单价。',pricing.evidence||'');
 console.log('[开始] 单价凭据检查');
 if(evidence===null){console.log('[分支] 取消');console.log('[结束] 单价凭据检查；提前结束');return;}
 else{console.log('[分支] 提交服务端校验');}
 console.log('[结束] 单价凭据检查');
 await Request('/pricing/'+providerId,'PUT',{...values,evidence}).then(()=>{document.querySelector('#notice').textContent='计费单价已保存，仅影响新任务';Load();},ShowError);
}


function ConfirmPassword(){return AskDialog('再次输入管理员密码','','password');}
async function LoadAtlasPhotos(groupKey,cursor=''){
 const query=new URLSearchParams();query.set('cursor',cursor);
 const result=await Request('/atlas/'+encodeURIComponent(groupKey)+'/photos?'+query).catch(ShowError);
 console.log('[开始] 图鉴照片响应检查');
 if(!result){console.log('[分支] 读取失败');console.log('[结束] 图鉴照片响应检查；提前结束');return;}
 console.log('[分支] 显示当前页');console.log('[结束] 图鉴照片响应检查');
 document.querySelector('#detailMedia').replaceChildren();document.querySelector('#detail').textContent=JSON.stringify(result.items,null,2);
 console.log('[开始] 图鉴照片预览');
 result.items.forEach((item,imageIndex)=>{console.log(`[开始] 照片 ${imageIndex+1}/${result.items.length}`);document.querySelector('#detailMedia').append(Element('p','拍摄者：'+item.photographer+'（'+item.user_id+'）'));PreviewImages('asset',item.asset_id,1);console.log(`[结束] 照片 ${imageIndex+1}/${result.items.length}`);});
 console.log('[结束] 图鉴照片预览');console.log('[开始] 图鉴后续分页检查');
 if(result.next_cursor){console.log('[分支] 提供下一页');const nextButton=Element('button','下一页照片');nextButton.addEventListener('click',()=>LoadAtlasPhotos(groupKey,result.next_cursor));document.querySelector('#detailMedia').append(nextButton);}
 else{console.log('[分支] 已是最后一页');}console.log('[结束] 图鉴后续分页检查');
}
async function SuggestCorrection(record){
 const name=await AskDialog('建议的物种名称',record.name);
 console.log('[开始] 更正名称检查');
 if(name===null){console.log('[分支] 取消');console.log('[结束] 更正名称检查；提前结束');return;}
 console.log('[分支] 继续填写理由');console.log('[结束] 更正名称检查');
 const reason=await AskDialog('更正依据（由用户决定是否接受）');
 console.log('[开始] 更正理由检查');
 if(reason===null){console.log('[分支] 取消');console.log('[结束] 更正理由检查；提前结束');return;}
 console.log('[分支] 发送建议');console.log('[结束] 更正理由检查');
 await Request('/atlas/'+record.id+'/correction','POST',{name:name.trim(),scientific_name:'',reason:reason.trim()}).then(()=>{document.querySelector('#notice').textContent='更正建议已发送，等待用户确认';},ShowError);
}
async function ConfirmDialog(message){return (await AskDialog(message,'confirm','confirm'))==='confirm';}
function AskDialog(message,initial='',type='text'){
 return new Promise(resolve=>{
  const dialog=Element('dialog');const form=Element('form');form.method='dialog';
  const label=Element('label',message);const input=Element('input');input.type=type==='confirm'?'hidden':type;input.value=initial;input.autocomplete=type==='password'?'current-password':'off';input.required=true;label.append(input);
  const submit=Element('button',type==='confirm'?'确认':'保存');submit.type='submit';const cancel=Element('button','取消');cancel.type='button';
  cancel.addEventListener('click',()=>dialog.close());form.addEventListener('submit',event=>{event.preventDefault();dialog.close(input.value);});
  dialog.addEventListener('close',()=>{const value=dialog.returnValue;dialog.remove();resolve(value||null);});
  form.append(Element('h2',type==='password'?'管理员身份验证':'确认操作'),label,submit,cancel);dialog.append(form);document.body.append(dialog);dialog.showModal();
 });
}


async function CreateWebAccount(){
 const username=await AskDialog('登录账号（3至80位字母、数字或 ._-）');
 console.log('[开始] 创建账号输入');
 if(!username){console.log('[分支] 取消；[结束] 创建账号输入');return;}
 console.log('[分支] 输入密码；[结束] 创建账号输入');
 const password=await AskDialog('设置测试账号初始密码（至少12位）','','password');
 console.log('[开始] 初始密码确认');
 if(!password){console.log('[分支] 取消；[结束] 初始密码确认');return;}
 console.log('[分支] 创建账号；[结束] 初始密码确认');
 await Request('/accounts','POST',{username,password,nickname:username}).then(()=>Load(),ShowError);
}
async function ResetWebPassword(record,reissue=false){
 const password=await AskDialog('设置此账号的新密码（至少12位）','','password');
 console.log('[开始] 重置密码确认');
 if(!password){console.log('[分支] 取消；[结束] 重置密码确认');return;}
 console.log('[分支] 提交新密码，至少12位；[结束] 重置密码确认');
 await Request('/accounts/'+record.id+(reissue?'/reissue':'/password'),'POST',{password}).then(()=>Load(),ShowError);
}

function ConfigField(form,name,labelText,value,type='text',required=false){
 const label=Element('label',labelText), input=Element('input');
 input.name=name;input.type=type;input.value=value??'';input.required=required;input.autocomplete='off';
 console.log('[开始] 配置输入类型');
 if(type==='number'){console.log('[分支] 非负数值');input.min='0';input.step='0.000001';}
 else{console.log('[分支] 文本或密钥');}
 console.log('[结束] 配置输入类型');label.append(input);form.append(label);return input;
}

async function LoadRuntime(){
 const results=await Promise.all([Request('/runtime/services/image'),Request('/runtime/services/qwen'),Request('/runtime/map')]);
 const panel=document.querySelector('#runtimePanel');panel.replaceChildren();
 panel.append(Element('p','保存后新任务立即使用新配置，无需重启。正在处理的任务保留原配置和价格。API Key 不回显，留空保留原值；更换服务商时请填写新 Key。'));
 const serviceItems=[['image','生图与润色',results[0]],[ 'qwen','识别与问答',results[1]]];
 console.log('[开始] 服务配置表单绘制');
 serviceItems.forEach(([providerId,title,config],serviceIndex)=>{
  console.log(`[开始] 服务表单 ${serviceIndex+1}/${serviceItems.length}`);
  const card=Element('section');card.className='card';card.append(Element('h2',title));
  card.append(Element('p',config.source==='admin'?'当前使用后台保存的配置':'当前使用部署时的初始配置'));
  const form=Element('form');form.className='grid';form.dataset.provider=providerId;
  ConfigField(form,'base_url','API 地址（HTTPS）',config.base_url,'url',true);
  ConfigField(form,'model','模型名称',config.model,'text',true);
  const keyInput=ConfigField(form,'api_key','API Key（'+(config.key_configured?'已配置，留空保留':'尚未配置')+'）','','password',!config.key_configured);
  keyInput.autocomplete='new-password';
  const priceFields=providerId==='image'?[['per_call','每次成功生图单价（元）']]:[
   ['input_rate','输入单价（元 / 百万 token）'],['output_rate','输出单价（元 / 百万 token）'],
   ['tier_threshold','长上下文阈值（token）'],['high_input_rate','长上下文输入单价（元 / 百万 token）'],['high_output_rate','长上下文输出单价（元 / 百万 token）']];
  console.log('[开始] 配置价格字段');
  priceFields.forEach(([name,label],fieldIndex)=>{
   console.log(`[开始] 价格字段 ${fieldIndex+1}/${priceFields.length}`);
   ConfigField(form,name,label,config.pricing[name],'number',name==='tier_threshold');
   console.log(`[结束] 价格字段 ${fieldIndex+1}/${priceFields.length}`);
  });console.log('[结束] 配置价格字段');
  ConfigField(form,'evidence','价格依据',config.pricing.evidence,'text',true);
  const submit=Element('button','保存'+title+'配置');submit.type='submit';form.append(submit);
  form.addEventListener('submit',event=>{
   event.preventDefault();submit.disabled=true;
   const values=FormValues(form), pricing={evidence:values.evidence};
   console.log('[开始] 价格输入整理');
   priceFields.forEach(([name],fieldIndex)=>{
    console.log(`[开始] 价格输入 ${fieldIndex+1}/${priceFields.length}`);
    pricing[name]=values[name].trim()===''?null:values[name].trim();
    console.log(`[结束] 价格输入 ${fieldIndex+1}/${priceFields.length}`);
   });console.log('[结束] 价格输入整理');
   Request('/runtime/services/'+providerId,'PUT',{revision:config.revision,base_url:values.base_url,model:values.model,api_key:values.api_key,pricing})
    .then(async()=>{keyInput.value='';await LoadRuntime();document.querySelector('#notice').textContent=title+'配置已保存，新任务立即生效';},ShowError)
    .catch(ShowError).finally(()=>{submit.disabled=false;});
  });
  card.append(form,Element('p','价格须与所选模型及规格一致。不知道单价时留空，系统保留费用待核对。更换模型不会自动验证其可用性。'));
  console.log('[开始] 生图协议说明');
  if(providerId==='image'){console.log('[分支] 显示支持范围');card.append(Element('p','当前支持与现有异步生图接口兼容的服务；填写模型名不能自动适配其他 API 协议。'));}
  else{console.log('[分支] 问答服务');}console.log('[结束] 生图协议说明');
  panel.append(card);console.log(`[结束] 服务表单 ${serviceIndex+1}/${serviceItems.length}`);
 });console.log('[结束] 服务配置表单绘制');
 const mapCard=Element('section');mapCard.className='card';mapCard.append(Element('h2','腾讯地图'));
 const mapForm=Element('form');mapForm.className='grid';ConfigField(mapForm,'map_key','腾讯地图网页 Key',results[2].map_key);
 const mapSubmit=Element('button','保存地图配置');mapForm.append(mapSubmit);
 mapForm.addEventListener('submit',event=>{
  event.preventDefault();mapSubmit.disabled=true;
  Request('/runtime/map','PUT',{revision:results[2].revision,map_key:FormValues(mapForm).map_key})
   .then(async()=>{await LoadRuntime();document.querySelector('#notice').textContent='地图配置已保存，请重新打开手机网页使地图加载新 Key';},ShowError)
   .catch(ShowError).finally(()=>{mapSubmit.disabled=false;});
 });
 mapCard.append(mapForm,Element('p','网页 Key 会提供给浏览器使用，请在腾讯地图控制台限制授权域名。清空后停用地图展示，定位记录仍可使用。'));
 panel.append(mapCard);
}
