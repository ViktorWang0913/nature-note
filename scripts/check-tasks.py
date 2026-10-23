"""Report historical charges; only active workers prevent a service restart."""
import argparse
from sqlalchemy import select, func
from app.db import SessionLocal
from app import models as m

# 参数设置
parser = argparse.ArgumentParser()
parser.add_argument('--report-only', dest='reportOnly', action='store_true')
options = parser.parse_args()

# 主程序
with SessionLocal() as db:
    runningCount = db.scalar(select(func.count()).select_from(m.Task).where(
        (m.Task.status == 'running') | (m.Task.lease_until > m.now())))
    queuedCount = db.scalar(select(func.count()).select_from(m.Task).where(m.Task.status == 'queued'))
    unresolvedCount = db.scalar(select(func.count()).select_from(m.Charge).where(m.Charge.state.in_(['submitted', 'pending'])))
    print(f'任务状态：执行中 {runningCount}，排队 {queuedCount}，待核对费用 {unresolvedCount}；历史账单不阻止更新')
    print('[开始] 正在执行的任务检查')
    if runningCount:
        print(f'[分支] 仍有 {runningCount} 个任务在执行')
        print('[开始] 检查模式')
        if options.reportOnly:
            print('[分支] 仅报告状态；不修改任务或账单')
        else:
            print('[分支] 等正在执行的任务完成后再更新；[结束] 检查模式；[结束] 正在执行的任务检查；提前结束')
            raise SystemExit(2)
        print('[结束] 检查模式')
    else:
        print('[分支] 无执行中任务，可以更新；排队任务和历史账单保持原样')
    print('[结束] 正在执行的任务检查')
