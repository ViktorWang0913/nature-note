from datetime import datetime, timedelta, timezone
from app import models as m, chat
from unittest.mock import Mock
from app.db import SessionLocal
from app.jobs import claim_task, run_task


def test_expired_worker_lease_recovery_and_duplicate_delivery(client, users, monkeypatch):
    monkeypatch.setattr(chat, 'Execute', Mock(return_value={'is_mock':False,'answer':'lease test'}))
    owner, _ = users[0]
    with SessionLocal() as db:
        task = m.Task(user_id=owner['id'], kind='rag', input={'question': '白头鹎', 'scope': 'public'})
        db.add(task)
        db.commit()
        task_id = task.id
        first_owner, _, wait = claim_task(db, task_id)
        assert first_owner and wait == 0
        duplicate_owner, _, wait = claim_task(db, task_id)
        assert duplicate_owner is None and 0 < wait <= 901
        task = db.get(m.Task, task_id)
        task.lease_until = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()
    assert run_task(task_id) == 0
    with SessionLocal() as db:
        completed = db.get(m.Task, task_id)
        assert completed.status == 'succeeded'
        assert completed.result['is_mock'] is False
        assert completed.lease_owner is None and completed.lease_until is None
        updated_at = completed.updated_at
    assert run_task(task_id) == 0
    with SessionLocal() as db:
        assert db.get(m.Task, task_id).updated_at == updated_at
