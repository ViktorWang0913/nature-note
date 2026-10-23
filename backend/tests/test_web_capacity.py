"""Exercise local scheduling with 22 isolated tasks; no remote model calls."""
import asyncio
import threading
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app import jobs, models as models


def test_each_provider_runs_ten_and_eleventh_waits(tmp_path, monkeypatch):
    databasePath = tmp_path / 'capacity.db'
    engine = create_engine('sqlite:///' + databasePath.as_posix(), connect_args={'check_same_thread': False, 'timeout': 30}, pool_size=30, max_overflow=10)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(jobs, 'SessionLocal', factory)
    monkeypatch.setattr(jobs.billing, 'Finalize', Mock())
    monkeypatch.setattr(jobs.svc, 'notify', Mock())
    lock = threading.Lock()
    release = threading.Event()
    counts = {'image': 0, 'qwen': 0}
    peaks = dict(counts)
    taskIds = []
    with factory() as database:
        print('[开始] 隔离并发数据，共 22 个任务')
        for taskIndex in range(22):
            print(f'[开始] 隔离任务 {taskIndex+1}/22')
            providerId = ['image', 'qwen'][taskIndex % 2]
            user = models.User(identity='capacity-' + str(taskIndex), name='并发验收')
            database.add(user)
            database.flush()
            task = models.Task(user_id=user.id, kind={'image': 'image_generation', 'qwen': 'image_recognition'}[providerId], input={})
            database.add(task)
            database.flush()
            database.add(models.Charge(task_id=task.id, user_id=user.id, provider_id=providerId, budget_id='isolated', slot_id=str(taskIndex), reserved_micros=0))
            taskIds.append(task.id)
            print(f'[结束] 隔离任务 {taskIndex+1}/22')
        print('[结束] 隔离并发数据')
        database.add_all([models.Provider(id='image', concurrency=10), models.Provider(id='qwen', concurrency=10)])
        database.commit()

    def Execute(database, task, user):
        providerId = jobs.billing.ProviderId(task.kind)
        with lock:
            counts[providerId] += 1
            peaks[providerId] = max(peaks[providerId], counts[providerId])
        assert release.wait(15), '未能并行启动 10 个任务'
        with lock:
            counts[providerId] -= 1
        return {'is_mock': True, 'text': '隔离调度结果'}

    monkeypatch.setattr(jobs.visual_ai, 'execute', Execute)

    async def Run():
        pending = [asyncio.create_task(jobs.RunInline(taskId)) for taskId in taskIds]
        print('[开始] 并发占位观察，共 100 次')
        for checkIndex in range(100):
            print(f'[开始] 占位观察 {checkIndex+1}/100')
            print('[开始] 双模型容量检查')
            if counts == {'image': 10, 'qwen': 10}:
                print('[分支] 两组均达到 10；[结束] 双模型容量检查；提前结束占位观察')
                break
            print('[分支] 等待任务领取；[结束] 双模型容量检查')
            await asyncio.sleep(.1)
            print(f'[结束] 占位观察 {checkIndex+1}/100')
        print('[结束] 并发占位观察')
        with factory() as database:
            states = list(database.scalars(select(models.Task.status)))
        release.set()
        await asyncio.gather(*pending)
        assert states.count('running') == 20
        assert states.count('queued') == 2

    asyncio.run(Run())
    assert peaks == {'image': 10, 'qwen': 10}
    with factory() as database:
        assert set(database.scalars(select(models.Task.status))) == {'succeeded'}
