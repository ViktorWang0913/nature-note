// 路径与参数设置
const explorerSections = ['users','tasks','generated','projects','assets'];
const pictureSections = ['generated','projects','assets'];
const statusNames = {queued:'排队中',running:'处理中',succeeded:'已完成',failed:'失败',cancelled:'已停止',
  settled:'已结算',pending:'待核对',reserved:'已预占',submitted:'已提交',released:'已释放',
  photo:'上传照片',edited:'编辑副本',generated:'AI 生成',image_generation:'图片生成',
  image_polish:'笔记生成',image_recognition:'图片识别',rag:'知识问答',qwen:'识别与问答',image:'生图与润色'};
let scopedUser = null, pageCursors = [null], currentPage = 0, loadEpoch = 0, detailEpoch = 0;
let projectObserver;

// 自编函数
function FormatTime(value) {
  console.log('[开始] 时间格式检查');
  if (!value) {console.log('[分支] 尚无记录；[结束] 时间格式检查，提前返回');return '暂无记录';}
  console.log('[分支] 北京时间；[结束] 时间格式检查');
  return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
}
function Money(value) {return value == null ? '待核对' : '¥'+(value/1000000).toFixed(4);}
function Button(label, handler, className='secondary') {
  const button=Element('button',label);button.type='button';button.className=className;
  button.addEventListener('click',handler);return button;
}
function Badge(value) {const badge=Element('span',statusNames[value]||value||'—');badge.className='badge status-'+value;return badge;}
function Navigate(section, user=null) {
  activeSection=section;scopedUser=user;currentPage=0;pageCursors=[null];
  document.querySelector('#filterForm').reset();Load();
}
function BuildNavigation() {
  const groups=[['', ['overview','users','generated','tasks','charges']],['内容与反馈',['posts','comments','reports','feedback','announcements','species']],['设置',['runtime','archives','audit']]];
  console.log('[开始] 分组导航');
  groups.forEach(([label,items],groupIndex)=>{
    console.log(`[开始] 导航组 ${groupIndex+1}/${groups.length}`);
    const group=Element(label?'details':'div');group.className='navGroup';
    console.log('[开始] 导航分组标题');
    if(label){console.log('[分支] 可折叠分组');group.append(Element('summary',label));}
    else{console.log('[分支] 主要工作入口');}
    console.log('[结束] 导航分组标题');
    console.log('[开始] 导航按钮');
    items.forEach((section,itemIndex)=>{
      console.log(`[开始] 入口 ${itemIndex+1}/${items.length}`);
      const button=Button(sections[section],()=>Navigate(section));button.dataset.section=section;group.append(button);
      console.log(`[结束] 入口 ${itemIndex+1}/${items.length}`);
    });console.log('[结束] 导航按钮');
    document.querySelector('#navigation').append(group);
    console.log(`[结束] 导航组 ${groupIndex+1}/${groups.length}`);
  });console.log('[结束] 分组导航');
}
function OpenDrawer(title) {
  detailEpoch+=1;document.querySelector('#detailTitle').textContent=title;
  console.log('[开始] 详情区域重置');
  ['recordInfo','detailMedia','relatedLinks','userContent','actionButtons'].forEach((id,index)=>{
    console.log(`[开始] 详情区域 ${index+1}/5`);document.getElementById(id).replaceChildren();console.log(`[结束] 详情区域 ${index+1}/5`);
  });console.log('[结束] 详情区域重置');
  document.querySelector('#detail').textContent='';
  document.querySelector('#technicalDetails').open=false;
  document.querySelector('#quotaPanel').hidden=true;
  console.log('[开始] 详情窗口状态');
  if(!document.querySelector('#detailDialog').open){console.log('[分支] 打开详情');document.querySelector('#detailDialog').showModal();}
  else{console.log('[分支] 更新详情');}
  console.log('[结束] 详情窗口状态');
  document.querySelector('#detailDialog').scrollTop=0;
  return detailEpoch;
}
function Metadata(container, fields) {
  const list=Element('dl');list.className='metadata';
  console.log('[开始] 详情信息');
  fields.forEach(([label,value],index)=>{
    console.log(`[开始] 字段 ${index+1}/${fields.length}`);
    list.append(Element('dt',label),Element('dd',value??'—'));
    console.log(`[结束] 字段 ${index+1}/${fields.length}`);
  });console.log('[结束] 详情信息');container.append(list);
}
function ShowPicture(container,url,title) {
  const figure=Element('figure');figure.className='pictureViewer';figure.dataset.background='checker';
  const controls=Element('div');controls.className='pictureControls';
  const frame=Element('div');frame.className='pictureFrame';
  const image=Element('img');image.alt=title;image.src=url;
  image.addEventListener('error',()=>{frame.replaceChildren(Element('p','图片不可用，请刷新或检查关联内容是否已删除。'));});
  const zoomLabel=Element('label','缩放');const zoom=Element('input');zoom.type='range';zoom.min='50';zoom.max='200';zoom.value='100';zoom.setAttribute('aria-label','图片缩放');
  zoom.addEventListener('input',()=>{image.style.width=zoom.value+'%';image.style.maxWidth='none';});
  zoomLabel.append(zoom);controls.append(zoomLabel);
  console.log('[开始] 预览背景选项');
  [['checker','棋盘格'],['light','浅色'],['dark','深色']].forEach(([value,label],index)=>{
    console.log(`[开始] 背景 ${index+1}/3`);controls.append(Button(label,()=>{figure.dataset.background=value;}));console.log(`[结束] 背景 ${index+1}/3`);
  });console.log('[结束] 预览背景选项');
  const original=Element('a','打开原图');original.href=url;original.target='_blank';original.rel='noopener';controls.append(original);
  frame.append(image);figure.append(Element('figcaption',title),controls,frame);container.append(figure);
}
function RenderCards(items,container,section) {
  console.log('[开始] 图片卡片列表');
  items.forEach((record,index)=>{
    console.log(`[开始] 图片卡片 ${index+1}/${items.length}`);
    const card=Element('article');card.className='artCard';
    const open=Button('',()=>OpenContentDetail(record.record_section||section,record.id).catch(ShowError),'artOpen');
    open.setAttribute('aria-label','查看 '+record.title);
    const preview=Element('div');preview.className='artPreview';
    console.log('[开始] 卡片预览类型');
    if(section==='projects'){
      console.log('[分支] 按需渲染已保存作品');
      const canvas=Element('canvas');canvas.hidden=true;canvas.setAttribute('aria-label',record.title+'完整作品预览');
      preview.append(canvas,Element('span','正在准备作品预览'));
      projectObserver.observe(preview);preview.dataset.projectId=record.id;
    }else{
      console.log('[分支] 已有图片缩略图');
      const image=Element('img');image.alt=record.title;image.src=record.thumbnail_url;image.loading='lazy';
      image.addEventListener('error',()=>preview.replaceChildren(Element('span','图片暂不可用')));preview.append(image);
    }
    console.log('[结束] 卡片预览类型');
    open.append(preview,Element('h3',record.title));card.append(open);
    const caption=Element('div');caption.className='artCaption';
    caption.append(Element('span',record.user.name),Element('time',FormatTime(record.updated_at)));
    card.append(caption);
    console.log('[开始] 卡片状态');
    if(section==='generated'){console.log('[分支] 图片保存状态');card.append(Badge(record.saved_asset_id?'已存入图库':'未存入图库'));}
    else if(section==='projects'){console.log('[分支] 作品保存版本');card.append(Badge((record.design_mode==='manual'?'手动设计':'自然笔记')+' · 版本 '+record.version));}
    else{console.log('[分支] 素材类型');card.append(Badge(record.source));}
    console.log('[结束] 卡片状态');
    container.append(card);console.log(`[结束] 图片卡片 ${index+1}/${items.length}`);
  });console.log('[结束] 图片卡片列表');
}
async function PreviewProject(preview) {
  const record=await Request('/explorer/projects/'+encodeURIComponent(preview.dataset.projectId));
  const canvas=preview.querySelector('canvas');
  await window.RenderAdminProject(canvas,record.layout);
  canvas.hidden=false;preview.querySelector('span').remove();
}
function RenderExplorerRows(items,section) {
  const headers=section==='users'?['用户','登录账号','状态','最近登录','创建时间']:['用户','任务类型','状态','结果','提交时间','费用'];
  const head=Element('tr');
  console.log('[开始] 专用表头');
  headers.forEach((label,index)=>{console.log(`[开始] 表头 ${index+1}/${headers.length}`);head.append(Element('th',label));console.log(`[结束] 表头 ${index+1}/${headers.length}`);});
  console.log('[结束] 专用表头');document.querySelector('#columns').append(head);
  console.log('[开始] 专用列表');
  items.forEach((record,index)=>{
    console.log(`[开始] 列表记录 ${index+1}/${items.length}`);
    const row=Element('tr');const title=Button(record.name||record.user.name,()=>OpenContentDetail(section,record.id).catch(ShowError),'textButton');
    const first=Element('td');first.append(title);row.append(first);
    console.log('[开始] 专用行类型');
    if(section==='users'){
      console.log('[分支] 用户列表');
      row.append(Element('td',record.username||'—'),Element('td',record.deleted_at?'已注销':record.active?'正常':'已停用'),
        Element('td',FormatTime(record.last_seen_at)),Element('td',FormatTime(record.created_at)));
    }else{
      console.log('[分支] 任务列表');
      row.append(Element('td',statusNames[record.kind]||record.kind));
      const state=Element('td');state.append(Badge(record.status));row.append(state);
      const output=Element('td');
      console.log('[开始] 任务缩略图');
      if(record.thumbnail_url){
        console.log('[分支] 成图预览');
        const button=Button('',()=>OpenContentDetail(section,record.id).catch(ShowError),'thumbButton');
        const image=Element('img');image.src=record.thumbnail_url;image.alt='查看生成结果';image.loading='lazy';button.append(image);output.append(button);
      }else{console.log('[分支] 查看文字或异常');output.append(Button('查看详情',()=>OpenContentDetail(section,record.id).catch(ShowError),'textButton'));}
      console.log('[结束] 任务缩略图');
      row.append(output,Element('td',FormatTime(record.created_at)),
        Element('td',record.charge?Money(record.charge.actual_micros)+' / '+(statusNames[record.charge.state]||record.charge.state):'无费用记录'));
    }
    console.log('[结束] 专用行类型');document.querySelector('#rows').append(row);
    console.log(`[结束] 列表记录 ${index+1}/${items.length}`);
  });console.log('[结束] 专用列表');
}
async function OpenContentDetail(section,itemId) {
  const epoch=OpenDrawer('正在读取详情');
  const record=await Request('/explorer/'+section+'/'+encodeURIComponent(itemId));
  console.log('[开始] 详情响应时序');
  if(epoch!==detailEpoch||!document.querySelector('#detailDialog').open){console.log('[分支] 已切换或关闭；[结束] 详情响应时序，提前结束');return;}
  console.log('[分支] 当前详情；[结束] 详情响应时序');
  selected=record;document.querySelector('#detailTitle').textContent=record.title||record.name||'任务详情';
  document.querySelector('#detail').textContent=JSON.stringify(record,null,2);
  const info=document.querySelector('#recordInfo'),media=document.querySelector('#detailMedia'),links=document.querySelector('#relatedLinks');
  console.log('[开始] 详情布局类型');
  if(section==='users'){
    console.log('[分支] 用户概况、额度与关联内容');
    Metadata(info,[['登录账号',record.username||'—'],['账号状态',record.deleted_at?'已注销':record.active?'正常':'已停用'],
      ['最近登录',FormatTime(record.last_seen_at)],['作品 / 素材 / 任务',record.counts.projects+' / '+record.counts.assets+' / '+record.counts.tasks]]);
    console.log('[开始] 用户额度列表');
    record.budgets.forEach((budget,index)=>{
      console.log(`[开始] 今日额度 ${index+1}/${record.budgets.length}`);
      info.append(Element('p',(statusNames[budget.provider_id]||budget.provider_id)+'：今日额度 '+Money(budget.limit_micros)+'，已结算 '+Money(budget.spent_micros)+'，暂占 '+Money(budget.held_micros)));
      console.log(`[结束] 今日额度 ${index+1}/${record.budgets.length}`);
    });console.log('[结束] 用户额度列表');
    console.log('[开始] 今日额度记录检查');
    if(!record.budgets.length){console.log('[分支] 未建立今日预算');info.append(Element('p','今日尚无额度记录；不表示额度为零。'));}
    else{console.log('[分支] 已显示今日预算');}
    console.log('[结束] 今日额度记录检查');
    console.log('[开始] 用户内容入口');
    [['generated','生成图片'],['projects','设计作品'],['assets','上传与编辑'],['tasks','任务记录']].forEach(([target,label],index)=>{
      console.log(`[开始] 用户入口 ${index+1}/4`);links.append(Button(label,()=>Navigate(target,record)));console.log(`[结束] 用户入口 ${index+1}/4`);
    });console.log('[结束] 用户内容入口');
    AddAction('重置登录密码',()=>ResetWebPassword(record));
    AddAction(record.active?'停用账号':'恢复账号',()=>SubmitPrompt('/users/'+record.id+'/status',{active:!record.active},'reason','请输入操作原因'));
    AddAction('调整此用户额度',()=>{document.querySelector('#quotaPanel').hidden=false;document.querySelector('#quotaForm [name=user_id]').value=record.id;});
    console.log('[开始] 注销账号管理');
    if(record.deleted_at){
      console.log('[分支] 注销账号仅提供重新发放');
      document.querySelector('#actionButtons').replaceChildren();AddAction('清理完成后重新发放',()=>ResetWebPassword(record,true));
    }else{console.log('[分支] 现有账号管理');}
    console.log('[结束] 注销账号管理');
    const recent=await Request('/explorer/generated?user_id='+encodeURIComponent(record.id));
    console.log('[开始] 用户最近内容时序');
    if(epoch===detailEpoch&&document.querySelector('#detailDialog').open){
      console.log('[分支] 展示最近生成图片');
      const content=document.querySelector('#userContent');content.append(Element('h3','最近生成图片'));
      const grid=Element('div');grid.className='contentGrid';content.append(grid);RenderCards(recent.items.slice(0,4),grid,'generated');
      console.log('[开始] 最近生成空状态');
      if(!recent.items.length){console.log('[分支] 尚未生成');content.append(Element('p','尚无成功生成的图片。'));}
      else{console.log('[分支] 已有图片');}
      console.log('[结束] 最近生成空状态');
    }else{console.log('[分支] 已离开当前详情');}
    console.log('[结束] 用户最近内容时序');
  }else{
    console.log('[分支] 创作内容详情');
    Metadata(info,[['所属用户',record.user.name+' '+record.user.username],['创建时间',FormatTime(record.created_at)],['最后更新',FormatTime(record.updated_at)]]);
    links.append(Button('查看用户',()=>OpenContentDetail('users',record.user_id).catch(ShowError)));
    console.log('[开始] 作品或任务详情');
    if(section==='projects'){
      console.log('[分支] 渲染当前保存版本');
      info.append(Element('p','云端保存版本 '+record.version+' · '+record.width+' × '+record.height+'。不包含尚未同步的设备修改。'));
      const canvas=Element('canvas');canvas.className='projectCanvas';canvas.setAttribute('aria-label','完整设计作品');
      const stage=Element('div');stage.className='projectStage';stage.append(canvas);media.append(stage);
      await window.RenderAdminProject(canvas,record.layout);
    }else{
      console.log('[分支] 查看图片或任务输出');
      console.log('[开始] 结果图片');
      if(record.image_url){console.log('[分支] 显示结果图');ShowPicture(media,record.image_url,'结果图片');}
      else{console.log('[分支] 无结果图');}
      console.log('[结束] 结果图片');
      console.log('[开始] 任务信息');
      if(section==='tasks'||section==='generated'){
        console.log('[分支] 状态、输入与费用');
        Metadata(info,[['任务类型',statusNames[record.kind]||record.kind],['任务状态',statusNames[record.status]||record.status],
          ['费用',record.charge?Money(record.charge.actual_micros)+' / '+(statusNames[record.charge.state]||record.charge.state):'无费用记录'],
          ['模型',record.charge?.model||'未记录'],['提交至完成',record.duration_seconds==null?'尚无完成时长':record.duration_seconds+' 秒'],
          ['任务编号',record.id],['上游任务编号',record.upstream_id||'未记录']]);
        info.append(Element('p',record.timing_note));
        info.append(Element('h3','输入文字'),Element('p',record.prompt||'此任务未填写文字'));
        console.log('[开始] 任务异常或回答');
        if(record.error){console.log('[分支] 显示失败信息');info.append(Element('p',record.error.message||'任务失败，请查看技术详情'));}
        else if(record.answer){console.log('[分支] 显示回答');info.append(Element('p',record.answer));}
        else{console.log('[分支] 无文字输出');}
        console.log('[结束] 任务异常或回答');
        console.log('[开始] 参考图列表');
        record.references.forEach((reference,index)=>{console.log(`[开始] 参考图 ${index+1}/${record.references.length}`);ShowPicture(media,reference.url,'参考图 · '+reference.title);console.log(`[结束] 参考图 ${index+1}/${record.references.length}`);});
        console.log('[结束] 参考图列表');
        links.append(Button('查看费用记录',()=>{Navigate('charges');document.querySelector('#search').value=record.id;Load();}));
        console.log('[开始] 关联设计');
        if(record.project_id){console.log('[分支] 查看关联作品');links.append(Button('查看关联作品',()=>OpenContentDetail('projects',record.project_id).catch(ShowError)));}
        else{console.log('[分支] 独立生成');}
        console.log('[结束] 关联设计');
        AddAction('刷新任务状态',()=>OpenContentDetail(section,itemId).catch(ShowError));
      }else{console.log('[分支] 素材尺寸与来源');Metadata(info,[['来源',statusNames[record.source]||record.source],['尺寸',record.width+' × '+record.height]]);}
      console.log('[结束] 任务信息');
    }
    console.log('[结束] 作品或任务详情');
  }
  console.log('[结束] 详情布局类型');
}
async function LoadWorkspace(cursor=null) {
  const epoch=++loadEpoch,section=activeSection;
  document.querySelector('#detailDialog').close();detailEpoch+=1;
  projectObserver?.disconnect();
  projectObserver=new IntersectionObserver(entries=>{
    console.log('[开始] 可见作品预览');
    entries.forEach((entry,index)=>{
      console.log(`[开始] 可见区域 ${index+1}/${entries.length}`);
      console.log('[开始] 作品可见检查');
      if(entry.isIntersecting){
        console.log('[分支] 加载作品');projectObserver.unobserve(entry.target);
        PreviewProject(entry.target).catch(error=>entry.target.replaceChildren(Element('span',error.message)));
      }else{console.log('[分支] 等待进入视口');}
      console.log('[结束] 作品可见检查');console.log(`[结束] 可见区域 ${index+1}/${entries.length}`);
    });console.log('[结束] 可见作品预览');
  },{rootMargin:'120px'});
  document.querySelector('#notice').textContent='正在读取…';
  document.querySelector('#sectionTitle').textContent=sections[section];
  document.querySelector('#sectionDescription').textContent=({
    overview:'查看近期创作与需要处理的问题',generated:'按生成任务展示结果，包含尚未存入图库的图片',
    projects:'完整预览云端已保存作品，按最后保存时间排列',assets:'查看用户上传照片及手动编辑副本',
    users:'从账户进入每位用户的作品与使用记录',tasks:'查看输入、结果、费用与异常，不重复提交任务',
    runtime:'统一管理模型、价格、并发与地图配置'})[section]||'选择记录查看详情及可用操作';
  console.log('[开始] 导航状态同步');
  document.querySelectorAll('#navigation button').forEach((button,index)=>{
    console.log(`[开始] 导航状态 ${index+1}`);
    const matched=button.dataset.section===section||(pictureSections.includes(section)&&button.dataset.section==='generated');
    button.classList.toggle('active',matched);
    console.log('[开始] 当前分组展开');
    if(matched&&button.closest('details')){console.log('[分支] 展开当前分组');button.closest('details').open=true;}
    else{console.log('[分支] 保留分组');}
    console.log('[结束] 当前分组展开');console.log(`[结束] 导航状态 ${index+1}`);
  });console.log('[结束] 导航状态同步');
  console.log('[开始] 工作区清空');
  ['summary','contentGrid','columns','rows','pageActions','contentTabs','scopeBar'].forEach((id,index)=>{
    console.log(`[开始] 清空 ${index+1}/7`);document.getElementById(id).replaceChildren();console.log(`[结束] 清空 ${index+1}/7`);
  });console.log('[结束] 工作区清空');
  document.querySelector('#empty').hidden=true;document.querySelector('#next').hidden=true;document.querySelector('#previous').hidden=true;
  document.querySelector('#filterForm').hidden=['overview','runtime'].includes(section);
  document.querySelector('#statusLabel').hidden=section!=='tasks';
  document.querySelector('#startLabel').hidden=!explorerSections.includes(section);
  document.querySelector('#endLabel').hidden=!explorerSections.includes(section);
  document.querySelector('#runtimePanel').hidden=section!=='runtime';
  document.querySelector('#announcementPanel').hidden=section!=='announcements';
  document.querySelector('.tableWrap').hidden=pictureSections.includes(section)||['overview','runtime'].includes(section);
  document.querySelector('#scopeBar').hidden=!scopedUser;
  document.querySelector('#pageNumber').textContent='';
  console.log('[开始] 用户筛选范围');
  if(scopedUser){console.log('[分支] 固定用户');document.querySelector('#scopeBar').append(Element('span','当前用户：'+scopedUser.name),Button('查看全部用户',()=>Navigate(section)));}
  else{console.log('[分支] 全部用户');}
  console.log('[结束] 用户筛选范围');
  console.log('[开始] 图片类型标签');
  if(pictureSections.includes(section)){
    console.log('[分支] 展示三类内容');
    [['generated','AI 生成'],['projects','设计作品'],['assets','上传与编辑']].forEach(([target,label],index)=>{
      console.log(`[开始] 内容标签 ${index+1}/3`);
      document.querySelector('#contentTabs').append(Button(label,()=>Navigate(target,scopedUser),target===section?'active':'secondary'));
      console.log(`[结束] 内容标签 ${index+1}/3`);
    });
  }else{console.log('[分支] 无图片标签');}
  console.log('[结束] 图片类型标签');
  console.log('[开始] 当前分页参数');
  if(cursor===null){console.log('[分支] 从第一页读取');currentPage=0;pageCursors=[null];}
  else{console.log('[分支] 读取指定页');}
  console.log('[结束] 当前分页参数');
  console.log('[开始] 工作模块加载');
  if(section==='runtime'){
    console.log('[分支] 集中服务配置');
    await LoadRuntime();
    const overview=await Request('/overview');
    RenderServiceControls(overview);
  }else if(section==='overview'){
    console.log('[分支] 运行与作品概览');
    const [overview,recent]=await Promise.all([Request('/overview'),Request('/explorer/generated')]);
    console.log('[开始] 概览时序');
    if(epoch!==loadEpoch){console.log('[分支] 已切换；[结束] 概览时序，提前结束');return;}
    console.log('[分支] 当前概览；[结束] 概览时序');
    RenderWorkspaceOverview(overview,recent);
  }else{
    console.log('[分支] 分页数据');
    const query=new URLSearchParams({q:document.querySelector('#search').value});
    console.log('[开始] 筛选参数');
    [['cursor',cursor],['user_id',scopedUser?.id],['status',document.querySelector('#statusFilter').value],
      ['start',document.querySelector('#startFilter').value],['end',document.querySelector('#endFilter').value]].forEach(([key,value],index)=>{
      console.log(`[开始] 筛选项 ${index+1}/5`);console.log('[开始] 非空参数');
      if(value){console.log('[分支] 添加筛选');query.set(key,value);}else{console.log('[分支] 不设置');}
      console.log('[结束] 非空参数');console.log(`[结束] 筛选项 ${index+1}/5`);
    });console.log('[结束] 筛选参数');
    const result=await Request((explorerSections.includes(section)?'/explorer/':'/list/')+section+'?'+query);
    console.log('[开始] 列表时序');
    if(epoch!==loadEpoch){console.log('[分支] 已切换；[结束] 列表时序，提前结束');return;}
    console.log('[分支] 当前列表；[结束] 列表时序');
    nextCursor=result.next_cursor;document.querySelector('#next').hidden=!nextCursor;
    document.querySelector('#previous').hidden=currentPage===0;document.querySelector('#pageNumber').textContent='第 '+(currentPage+1)+' 页';
    console.log('[开始] 列表呈现方式');
    if(pictureSections.includes(section)){console.log('[分支] 图片网格');RenderCards(result.items,document.querySelector('#contentGrid'),section);}
    else if(explorerSections.includes(section)){console.log('[分支] 业务表格');RenderExplorerRows(result.items,section);}
    else{console.log('[分支] 保留管理表格');RenderRows(result.items);}
    console.log('[结束] 列表呈现方式');
    document.querySelector('#empty').hidden=result.items.length>0;
    document.querySelector('#empty').textContent='暂无符合条件的记录。可以调整筛选条件或稍后刷新。';
    console.log('[开始] 账户创建入口');
    if(section==='users'){console.log('[分支] 创建测试账号');document.querySelector('#pageActions').append(Button('创建测试账号',CreateWebAccount,'primary'));}
    else{console.log('[分支] 其他模块');}
    console.log('[结束] 账户创建入口');
  }
  console.log('[结束] 工作模块加载');
  console.log('[开始] 加载完成状态');
  if(epoch===loadEpoch){console.log('[分支] 清除当前加载提示');document.querySelector('#notice').textContent='';}
  else{console.log('[分支] 保留新页面提示');}
  console.log('[结束] 加载完成状态');
}
function RenderWorkspaceOverview(overview,recent) {
  const summary=document.querySelector('#summary');
  const settled=overview.billing.filter(row=>row.state==='settled').reduce((total,row)=>total+(row.actual_micros||0),0);
  const held=overview.billing.filter(row=>['reserved','submitted','pending'].includes(row.state)).reduce((total,row)=>total+(row.reserved_micros||0),0);
  const metrics=[['今日使用人数',overview.active_today,'users'],['排队 / 运行',overview.queued_tasks+' / '+overview.running_tasks,'tasks'],
    ['今日失败任务',overview.failed_today,'tasks'],['今日账面结算',Money(settled),'charges']];
  console.log('[开始] 概览指标');
  metrics.forEach(([label,value,target],index)=>{
    console.log(`[开始] 指标 ${index+1}/${metrics.length}`);
    const card=Button('',()=>Navigate(target),'metric');card.append(Element('span',label),Element('strong',String(value)));summary.append(card);
    console.log(`[结束] 指标 ${index+1}/${metrics.length}`);
  });console.log('[结束] 概览指标');
  const notes=Element('p','使用人数按今日提交任务或保存作品统计。今日暂占 '+Money(held)+'；待核对费用不计入已结算金额。');
  const issues=Element('div');issues.className='tabs';
  issues.append(Button('待处理反馈 '+overview.pending_feedback,()=>Navigate('feedback')),Button('待审核帖子 '+overview.pending_posts,()=>Navigate('posts')));
  document.querySelector('#pageActions').append(notes,issues);
  const heading=Element('div');heading.className='sectionHeading';heading.append(Element('h2','最近生成'),Button('查看全部作品',()=>Navigate('generated')));
  document.querySelector('#pageActions').append(heading);RenderCards(recent.items.slice(0,6),document.querySelector('#contentGrid'),'generated');
  document.querySelector('#empty').hidden=recent.items.length>0;document.querySelector('#empty').textContent='尚无成功生成的图片。用户完成生成后会显示在这里。';
}
function RenderServiceControls(overview) {
  const panel=document.querySelector('#runtimePanel'),card=Element('section');card.className='card';
  card.append(Element('h2','执行容量与默认额度'));
  console.log('[开始] 服务控制列表');
  overview.providers.forEach((provider,index)=>{
    console.log(`[开始] 服务控制 ${index+1}/${overview.providers.length}`);
    const row=Element('div');row.className='serviceControls';
    row.append(Element('p',statusNames[provider.id]+'：'+(provider.enabled?'已启用':'已暂停')+'，应用并发上限 '+provider.concurrency+'，每日默认额度 '+Money(provider.daily_micros)));
    row.append(Button('调整并发与参数',()=>ConfigureProvider(provider)));
    row.append(Button(provider.enabled?'暂停服务':'恢复服务',()=>Request('/providers/'+provider.id,'PUT',{
      enabled:!provider.enabled,message:provider.message,concurrency:provider.concurrency,reserve_micros:provider.reserve_micros,
      context_limit:provider.context_limit,output_limit:provider.output_limit}).then(()=>Load(),ShowError)));
    card.append(row);console.log(`[结束] 服务控制 ${index+1}/${overview.providers.length}`);
  });console.log('[结束] 服务控制列表');
  card.append(Button('调整默认每日额度',()=>{OpenDrawer('默认每日额度');document.querySelector('#quotaPanel').hidden=false;
    document.querySelector('#quotaForm [name=user_id]').value='';document.querySelector('#quotaForm [name=mode]').value='default';}));
  card.append(Button(overview.community.enabled?'暂停社区发布':'恢复社区发布',()=>Request('/community','PUT',{...overview.community,enabled:!overview.community.enabled}).then(()=>Load(),ShowError)));
  panel.prepend(card);
}
