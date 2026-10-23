"""Server-only administrator status and unlock; never changes the password."""
import argparse
import json
from app.db import SessionLocal
from app import models as m
from app.admin_security import Audit

# 参数设置
parser = argparse.ArgumentParser(description='检查管理员状态，或解除登录锁定（不修改密码）')
parser.add_argument('--unlock', action='store_true')


def Main():
    options = parser.parse_args()
    with SessionLocal() as db:
        account = db.get(m.AdminAccount, 'owner')
        print('[开始] 管理员状态检查')
        if account is None:
            print('[分支] 管理员未初始化；请检查数据库及 app.admin_setup')
            print('[结束] 管理员状态检查；提前结束')
            return
        else:
            print('[分支] 管理员已存在；[结束] 管理员状态检查')
        print(json.dumps({'username': account.username, 'locked_until': account.locked_until,
            'locked_now': bool(account.locked_until and account.locked_until > m.now()),
            'failed_attempts': account.failed_attempts, 'must_change': account.must_change}, ensure_ascii=False))
        print('[开始] 解锁操作选择')
        if options.unlock:
            print('[分支] 解除锁定，保留密码和所有数据')
            account.locked_until = None
            account.failed_attempts = 0
            Audit(db, account.id, 'admin_unlocked_by_server', account.id, {})
            db.commit()
        else:
            print('[分支] 只读检查')
        print('[结束] 解锁操作选择')


print('[开始] 管理状态工具入口')
if __name__ == '__main__':
    print('[分支] 执行管理状态工具')
    Main()
else:
    print('[分支] 仅导入工具')
print('[结束] 管理状态工具入口')
