import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app import chat, models as m, visual_ai, jobs
from app.config import settings
from app.db import SessionLocal
from test_management import NewUser


def MockProvider(monkeypatch, completed=True, cumulative=False):
    requests = []
    clientClass = httpx.Client

    def Respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        print('[开始] 本地模型模拟响应')
        if not payload.get('stream'):
            print('[分支] 返回历史摘要及实际用量')
            result = httpx.Response(200, json={'choices': [{'message': {'content': '用户观察自然物种，要求保留不确定性。'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20}})
        else:
            print('[分支] 返回流式文字和实际用量')
            events = ['data: ' + json.dumps({'choices': [{'delta': {'content': '观察到了鸟类。'}}]})]
            print('[开始] 累计用量模拟')
            if cumulative:
                print('[分支] 首段也带有尚未完成的累计用量')
                events.insert(0, 'data: ' + json.dumps({'choices': [], 'usage': {'prompt_tokens': 200, 'completion_tokens': 1}}))
            else:
                print('[分支] 只在最后返回用量')
            print('[结束] 累计用量模拟')
            print('[开始] 模拟完整性选择')
            if completed:
                print('[分支] 返回明确完成及计费事件')
                events += ['data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]}),
                    'data: ' + json.dumps({'choices': [], 'usage': {'prompt_tokens': 200, 'completion_tokens': 30}}), 'data: [DONE]']
            else:
                print('[分支] 模拟连接中途结束')
            print('[结束] 模拟完整性选择')
            result = httpx.Response(200, text='\n\n'.join(events) + '\n\n', headers={'content-type': 'text/event-stream'})
        print('[结束] 本地模型模拟响应')
        return result

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://model.invalid', 'local-test', 'not-a-real-key'))
    monkeypatch.setattr(chat.httpx, 'Client', CreateClient)
    monkeypatch.setattr(settings(), 'qwen_input_cny_per_million', 2)
    monkeypatch.setattr(settings(), 'qwen_output_cny_per_million', 6)
    return requests


def test_streamed_answer_cost_context_and_no_automatic_replay(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    requests = MockProvider(monkeypatch)
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': 'rag', 'input': {'chat_session_id': session['id'], 'question': '这是什么？'}})
    taskId = response.json()['id']
    task = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert task['status'] == 'succeeded', task
    assert task['result']['answer'] == '观察到了鸟类。'
    assert '_actual_micros' not in task['result']
    detail = client.get('/api/v1/chats/' + session['id'], headers=headers).json()
    assert detail['messages'][-1]['status'] == 'complete'
    assert detail['context']['last_measured_tokens'] == 230
    with SessionLocal() as db:
        assert db.get(m.Charge, taskId).actual_micros == 580
    assert jobs.run_task(taskId) == 0
    assert len(requests) == 1
    assert requests[0]['messages'][0]['role'] == 'system'


def test_cumulative_stream_usage_settles_final_total(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    requests = MockProvider(monkeypatch, cumulative=True)
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': 'rag', 'input': {'chat_session_id': session['id'], 'question': '观察到了什么？'}})
    with SessionLocal() as database:
        charge = database.get(m.Charge, response.json()['id'])
        assert charge.actual_micros == 580
        assert charge.metering['calls']['answer']['usage']['completion_tokens'] == 30
    assert requests[0]['enable_thinking'] is False


def test_truncated_stream_keeps_partial_answer_and_pending_charge(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    requests = MockProvider(monkeypatch, completed=False)
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': 'rag', 'input': {'chat_session_id': session['id'], 'question': '你好'}})
    taskId = response.json()['id']
    task = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert task['status'] == 'failed'
    assert task['result']['answer'] == '观察到了鸟类。'
    with SessionLocal() as db:
        assert db.get(m.Charge, taskId).state == 'pending'
        assert db.scalar(select(m.ChatMessage).where(m.ChatMessage.task_id == taskId, m.ChatMessage.role == 'assistant')).status == 'failed'
        assert db.get(m.UserTaskSlot, db.get(m.Charge, taskId).slot_id).task_id is None
    assert jobs.run_task(taskId) == 0
    assert len(requests) == 1


def test_context_compression_preserves_original_messages_and_accounts_usage(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    with SessionLocal() as db:
        provider = db.get(m.Provider, 'qwen')
        previousLimit = provider.context_limit
        provider.context_limit = 8000
        startTime = datetime.now(timezone.utc) - timedelta(hours=1)
        print('[开始] 准备长对话，共 10 条')
        for messageIndex in range(10):
            print(f'[开始] 原始消息 {messageIndex + 1}/10')
            db.add(m.ChatMessage(user_id=user['id'], session_id=session['id'], role='user', text='自然观察。' * 120,
                created_at=(startTime + timedelta(seconds=messageIndex)).isoformat()))
            print(f'[结束] 原始消息 {messageIndex + 1}/10')
        print('[结束] 准备长对话')
        db.commit()
    requests = MockProvider(monkeypatch)
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': 'rag', 'input': {'chat_session_id': session['id'], 'question': '总结一下'}})
    taskId = response.json()['id']
    task = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert task['status'] == 'succeeded', task
    detail = client.get('/api/v1/chats/' + session['id'], headers=headers).json()
    assert len(detail['messages']) == 12
    assert detail['context']['compressed'] is True
    assert len(requests) == 3  # 两段摘要，一次正式回答。
    assert task['result']['usage']['compression']['prompt_tokens'] == 200
    with SessionLocal() as db:
        assert db.get(m.Charge, taskId).actual_micros == 1220
        db.get(m.Provider, 'qwen').context_limit = previousLimit
        db.commit()
