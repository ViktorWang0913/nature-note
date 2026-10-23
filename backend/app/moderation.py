"""WeChat automatic review; unavailable or uncertain results stay private."""
import hashlib
import json

from sqlalchemy import select, update

from . import models as m, services as svc, storage, wechat_api
from .config import settings
from .db import SessionLocal


def Snapshot(db, item, kind):
    result = {'text': item.text}
    print('[开始] 审核快照类型')
    if kind == 'post':
        print('[分支] 帖子及待审修改版本')
        result.update(title=item.title, location_text=item.location_text, images=item.images)
        pending = db.get(m.PlatformControl, 'edit:' + item.id)
        result.update(getattr(pending, 'value', {}))
    else:
        print('[分支] 评论正文')
    print('[结束] 审核快照类型')
    return result


def Fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def Queue(db, item, kind):
    recordId = 'review:' + kind + ':' + item.id
    control = db.get(m.PlatformControl, recordId)
    print('[开始] 审核任务创建检查')
    if control is None:
        print('[分支] 创建审核任务')
        control = m.PlatformControl(id=recordId)
        db.add(control)
    else:
        print('[分支] 新版本替换待审核任务')
    print('[结束] 审核任务创建检查')
    control.value = {'kind':kind, 'item_id':item.id, 'user_id':item.user_id, 'state':'queued',
        'fingerprint':Fingerprint(Snapshot(db, item, kind)), 'text':'pending', 'media':{}}


def Apply(db, control):
    state = control.value
    model = {'post':m.Post, 'comment':m.Comment}[state['kind']]
    item = db.scalar(select(model).where(model.id == state['item_id']).with_for_update())
    print('[开始] 自动审核版本一致性')
    if not item or item.deleted or Fingerprint(Snapshot(db,item,state['kind'])) != state['fingerprint'] or state['state'] == 'manual_override':
        print('[分支] 内容已改变、删除或管理员已处理，忽略旧回调')
        print('[结束] 自动审核版本一致性；提前结束')
        return
    else:
        print('[分支] 当前审核版本')
    print('[结束] 自动审核版本一致性')
    decisions = [state['text']] + list(state['media'].values())
    print('[开始] 自动审核最终决定')
    if 'risky' in decisions:
        print('[分支] 拒绝当前内容公开')
        decision = 'rejected'
    elif decisions and all(value == 'pass' for value in decisions):
        print('[分支] 文字和全部图片均通过')
        decision = 'approved'
    else:
        print('[分支] 未完成或不确定，继续待人工审核')
        print('[结束] 自动审核最终决定；提前结束')
        return
    print('[结束] 自动审核最终决定')
    revision = db.get(m.PlatformControl,'edit:'+item.id) if state['kind'] == 'post' else None
    print('[开始] 自动审核发布版本')
    if revision:
        print('[分支] 修改版本处理')
        print('[开始] 修改版本通过检查')
        if decision == 'approved':
            print('[分支] 替换公开内容')
            item.title = revision.value.get('title',item.title)
            item.text = revision.value.get('text',item.text)
            item.location_text = revision.value.get('location_text',item.location_text)
        else:
            print('[分支] 旧版继续公开')
        print('[结束] 修改版本通过检查')
        db.delete(revision)
    else:
        print('[分支] 首次发布审核')
        item.review_status = decision
    print('[结束] 自动审核发布版本')
    item.review_reason = '' if decision == 'approved' else '内容未通过自动审核，可修改后重新提交'
    control.value = {**state, 'state':'complete', 'decision':decision}
    svc.notify(db,item.user_id,item.user_id,'review',state['kind'],item.id,'你的内容审核状态已更新')
    db.add(m.Audit(actor_id='wechat-review',action='automatic_review',target_id=item.id,detail={'decision':decision}))


def Run(recordId):
    with SessionLocal() as db:
        control = db.get(m.PlatformControl,recordId)
        print('[开始] 自动审核运行资格')
        if not control or control.value['state'] != 'queued':
            print('[分支] 已处理或已提交，不自动重放')
            print('[结束] 自动审核运行资格；提前结束')
            return
        else:
            print('[分支] 检查微信审核配置')
        print('[结束] 自动审核运行资格')
        state = control.value
        user = db.get(m.User,state['user_id'])
        item = db.get({'post':m.Post,'comment':m.Comment}[state['kind']],state['item_id'])
        cfg = settings()
        print('[开始] 自动审核服务可用性')
        if not cfg.wechat_moderation_enabled or not cfg.wechat_app_id or not cfg.wechat_app_secret or not user or not user.active or not user.identity.startswith('wx:') or not item or item.deleted:
            print('[分支] 条件不齐备，转人工审核')
            control.value = {**state, 'state':'manual'}
            db.commit()
            print('[结束] 自动审核服务可用性；提前结束')
            return
        else:
            print('[分支] 准備自动审核')
        print('[结束] 自动审核服务可用性')
        snapshot = Snapshot(db,item,state['kind'])
        text = '\n'.join([snapshot.get('title',''),snapshot['text'],snapshot.get('location_text','')])
        print('[开始] 文字接口长度检查')
        if len(text) > 2500:
            print('[分支] 超出微信单次文字上限，转人工审核')
            control.value = {**state, 'state':'manual'}
            db.commit()
            print('[结束] 文字接口长度检查；提前结束')
            return
        else:
            print('[分支] 文字长度可审核')
        print('[结束] 文字接口长度检查')
        claimed = db.execute(update(m.PlatformControl).where(m.PlatformControl.id == recordId,
            m.PlatformControl.value['state'].as_string() == 'queued',
            m.PlatformControl.value['fingerprint'].as_string() == state['fingerprint']).values(value={**state,'state':'processing'}))
        db.commit()
        print('[开始] 审核任务领取结果')
        if claimed.rowcount != 1:
            print('[分支] 已被另一进程领取或内容已改变')
            print('[结束] 审核任务领取结果；提前结束')
            return
        else:
            print('[分支] 本进程取得审核权')
        print('[结束] 审核任务领取结果')
        db.refresh(control)
        token = wechat_api.AccessToken(required=False)
        print('[开始] 审核凭据结果')
        if not token:
            print('[分支] 凭据不可用，保留人工审核')
            control.value = {**control.value,'state':'manual'}
            db.commit()
            print('[结束] 审核凭据结果；提前结束')
            return
        else:
            print('[分支] 可以提交审核')
        print('[结束] 审核凭据结果')
        response = wechat_api.ReadResponse('/wxa/msg_sec_check',{'openid':user.identity[3:], 'scene':4 if state['kind']=='post' else 2,
            'version':2, 'content':text},token,required=False)
        print('[开始] 文字审核返回版本检查')
        if not IsCurrent(db,control,state['fingerprint']):
            print('[分支] 新版或人工审核已接管')
            print('[结束] 文字审核返回版本检查；提前结束')
            return
        else:
            print('[分支] 继续当前版本')
        print('[结束] 文字审核返回版本检查')
        textDecision = response.get('result',{}).get('suggest','review') if response.get('errcode',0)==0 else 'review'
        images = snapshot.get('images',[])
        media = {str(index):'pending' for index in range(len(images))}
        control.value = {**control.value,'text':textDecision,'media':media,'state':'awaiting'}
        db.commit()
        print(f'[开始] 图片审核提交，共 {len(images)} 张')
        for imageIndex, key in enumerate(images):
            print(f'[开始] 审核图片 {imageIndex+1}/{len(images)}')
            response = wechat_api.ReadResponse('/wxa/media_check_async',{'openid':user.identity[3:], 'scene':4,'version':2,
                'media_type':2,'media_url':storage.url(key,'post',item.id)},token,required=False)
            print('[开始] 图片审核返回版本检查')
            if not IsCurrent(db,control,state['fingerprint']):
                print('[分支] 新版或人工审核已接管')
                print('[结束] 图片审核返回版本检查；提前结束图片循环')
                return
            else:
                print('[分支] 继续当前版本')
            print('[结束] 图片审核返回版本检查')
            print('[开始] 图片审核提交结果')
            if response.get('errcode',0)==0 and response.get('trace_id'):
                print('[分支] 保存审核回调关联')
                db.add(m.PlatformControl(id='trace:'+response['trace_id'],value={'record_id':recordId,'fingerprint':state['fingerprint'],'index':str(imageIndex)}))
            else:
                print('[分支] 图片审核不可用，转人工')
                control.value = {**control.value,'media':{**control.value['media'],str(imageIndex):'review'}}
            print('[结束] 图片审核提交结果')
            db.commit()
            print(f'[结束] 审核图片 {imageIndex+1}/{len(images)}')
        print('[结束] 图片审核提交')
        db.refresh(control)
        Apply(db,control)
        db.commit()


def Callback(db, payload):
    trace = db.get(m.PlatformControl,'trace:'+str(payload.get('trace_id','')))
    print('[开始] 审核回调关联')
    if payload.get('Event') != 'wxa_media_check' or not trace:
        print('[分支] 无对应审核任务')
        print('[结束] 审核回调关联；提前结束')
        return
    else:
        print('[分支] 检查审核版本')
    print('[结束] 审核回调关联')
    control = db.scalar(select(m.PlatformControl).where(m.PlatformControl.id == trace.value['record_id']).with_for_update())
    print('[开始] 审核回调幂等检查')
    if not control or control.value['fingerprint'] != trace.value['fingerprint'] or control.value['state'] in {'complete','manual_override'}:
        print('[分支] 已处理或已不是当前版本')
        print('[结束] 审核回调幂等检查；提前结束')
        return
    else:
        print('[分支] 记录当前图片结果')
    print('[结束] 审核回调幂等检查')
    decision = payload.get('result',{}).get('suggest','review') if payload.get('errcode')==0 else 'review'
    control.value = {**control.value,'media':{**control.value['media'],trace.value['index']:decision}}
    Apply(db,control)
    db.commit()


def IsCurrent(db, control, fingerprint):
    db.refresh(control,with_for_update=True)
    return control.value['fingerprint'] == fingerprint and control.value['state'] in {'processing','awaiting'}


def Recover():
    with SessionLocal() as db:
        ids = list(db.scalars(select(m.PlatformControl.id).where(m.PlatformControl.id.startswith('review:'),
            m.PlatformControl.value['state'].as_string() == 'queued').limit(50)))
    print(f'[开始] 审核调度恢复，共 {len(ids)} 条')
    for recordIndex, recordId in enumerate(ids,1):
        print(f'[开始] 审核恢复 {recordIndex}/{len(ids)}')
        Run(recordId)
        print(f'[结束] 审核恢复 {recordIndex}/{len(ids)}')
    print('[结束] 审核调度恢复')
