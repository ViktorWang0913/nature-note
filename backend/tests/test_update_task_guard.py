"""Check installer decisions using an isolated database, including five pending charges."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import runpy
import sys

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app import db as database, models as m


@pytest.mark.parametrize('scenario', ['pending', 'queued', 'running', 'leased', 'idle', 'report'])
def test_update_guard(tmp_path, monkeypatch, scenario):
    engine = create_engine('sqlite:///' + str(tmp_path / 'guard.db'))
    m.Base.metadata.create_all(engine)
    sessionFactory = sessionmaker(bind=engine)
    taskStatus = {'queued': 'queued', 'running': 'running', 'report': 'running'}.get(scenario, 'failed')
    leaseUntil = {'leased': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}.get(scenario)
    with sessionFactory.begin() as db:
        db.add(m.Task(id='test', user_id='user', kind='image_generation', status=taskStatus, lease_until=leaseUntil))
        print('[开始] 历史账单准备')
        if scenario == 'pending':
            print('[分支] 五笔待核对费用')
            for chargeIndex in range(5):
                print(f'[开始] 账单 {chargeIndex + 1}/5')
                db.add(m.Charge(task_id='pending-' + str(chargeIndex), user_id='user', budget_id='budget',
                    slot_id='slot', provider_id='image', state='pending', reserved_micros=50000))
                print(f'[结束] 账单 {chargeIndex + 1}/5')
        else:
            print('[分支] 无待核对费用')
        print('[结束] 历史账单准备')
    monkeypatch.setattr(database, 'SessionLocal', sessionFactory)
    monkeypatch.setattr(sys, 'argv', ['check-tasks.py'] + {'report': ['--report-only']}.get(scenario, []))
    scriptPath = Path(__file__).resolve().parents[2] / 'scripts/check-tasks.py'
    print('[开始] 更新检查验证')
    if scenario in {'running', 'leased'}:
        print('[分支] 保护真实执行任务')
        with pytest.raises(SystemExit) as exitInfo:
            runpy.run_path(str(scriptPath), run_name='__main__')
        assert exitInfo.value.code == 2
    else:
        print('[分支] 历史账单和排队任务不阻断')
        runpy.run_path(str(scriptPath), run_name='__main__')
    print('[结束] 更新检查验证')
    with sessionFactory() as db:
        assert db.get(m.Task, 'test').status == taskStatus
        assert db.scalar(select(func.count()).select_from(m.Charge)) == {'pending': 5}.get(scenario, 0)
    engine.dispose()
