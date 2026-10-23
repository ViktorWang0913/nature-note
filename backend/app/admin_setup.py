"""Run once on the server: python -m app.admin_setup; no passwords in CLI arguments."""
from getpass import getpass
from .db import SessionLocal
from . import models as m
from .admin_security import HashPassword


def Main():
    username = input('管理员用户名：').strip()
    password = getpass('初始密码（至少 12 位）：')
    print('[开始] 初始管理账号参数检查')
    if not username or len(password) < 12:
        print('[分支] 参数不满足要求')
        raise ValueError('用户名不能为空，密码至少 12 位')
    else:
        print('[分支] 参数有效')
    print('[结束] 初始管理账号参数检查')
    with SessionLocal() as db:
        print('[开始] 唯一管理员检查')
        if db.get(m.AdminAccount, 'owner'):
            print('[分支] 已存在管理员，禁止覆盖')
            raise RuntimeError('管理员已存在')
        else:
            print('[分支] 创建唯一管理员')
        print('[结束] 唯一管理员检查')
        db.add(m.AdminAccount(id='owner', username=username, password_hash=HashPassword(password)))
        db.commit()
    print('管理员已创建，首次登录须修改密码。')


print('[开始] 管理账号工具入口检查')
if __name__ == '__main__':
    print('[分支] 命令行运行')
    Main()
else:
    print('[分支] 模块导入，不创建账号')
print('[结束] 管理账号工具入口检查')
