import base64
import io
from datetime import datetime, timedelta, timezone

import httpx
from PIL import Image, ImageDraw
from sqlalchemy import select

from app import billing, jobs, models as m, visual_ai
from app.db import SessionLocal
from app.config import settings
from test_management import NewUser


def test_submitted_image_cancellation_tracks_original_job_without_resubmission(client,monkeypatch):
    monkeypatch.setattr(settings(), 'image_cny_per_call', None)
    user, headers = NewUser(client)
    imageBytes = io.BytesIO()
    image = Image.new('RGB', (128, 128), 'white')
    ImageDraw.Draw(image).ellipse((30, 20, 98, 108), fill='#345634')
    image.save(imageBytes, format='PNG')
    calls = []
    clientClass = httpx.Client

    def Respond(request):
        calls.append(request.method)
        print('[开始] 本地生图异步模拟')
        if request.method == 'POST':
            print('[分支] 首次提交上游任务')
            response = httpx.Response(200,json={'task_id':'upstream-cancel-test'})
        else:
            print('[分支] 模拟用户取消等待，但上游仍完成')
            with SessionLocal() as db:
                task = db.scalar(select(m.Task).where(m.Task.user_id == user['id'],m.Task.kind == 'image_generation'))
                task.status = 'cancelled'
                billing.Abort(db,task.id)
                db.commit()
                charge = db.get(m.Charge,task.id)
                assert charge.state == 'pending'
                assert db.get(m.UserTaskSlot,charge.slot_id).task_id == task.id
            response = httpx.Response(200,json={'status':'completed','data':[{'b64_json':base64.b64encode(imageBytes.getvalue()).decode()}], 'usage':{'images':1}})
        print('[结束] 本地生图异步模拟')
        return response

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond),**options)

    monkeypatch.setattr(visual_ai,'_configuration',lambda kind, db, task:('https://image.invalid','local-test','fake-key'))
    monkeypatch.setattr(visual_ai.httpx,'Client',CreateClient)
    task = client.post('/api/v1/tasks',headers=headers,json={'kind':'image_generation','input':{'prompt':'本地测试'}}).json()
    with SessionLocal() as db:
        saved = db.get(m.Task,task['id'])
        charge = db.get(m.Charge,task['id'])
        assert saved.status == 'cancelled'
        assert saved.result['provider_task_id'] == 'upstream-cancel-test'
        assert charge.state == 'pending' and charge.usage == {'images':1}
        assert saved.lease_owner is None
        assert db.get(m.UserTaskSlot,charge.slot_id).task_id is None
    assert calls == ['POST','GET']
    assert jobs.run_task(task['id']) == 0
    assert calls == ['POST','GET']
