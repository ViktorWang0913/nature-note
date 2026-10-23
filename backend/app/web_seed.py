"""Idempotent baseline import; existing admin changes are never overwritten."""
import json
from pathlib import Path
from . import models as m, storage
from .db import SessionLocal
from .seed import seed

seedPath = Path(__file__).resolve().parents[1] / 'seed-assets'
snapshotPath = seedPath / 'web-baseline.json'
modelMap = {'assets': m.Asset, 'templates': m.Template, 'providers': m.Provider, 'platform_controls': m.PlatformControl}


def ImportBaseline():
    print('[开始] 基线选择')
    if not snapshotPath.exists():
        print('[分支] 使用随附公共资源；[结束] 基线选择')
        seed()
        return
    print('[分支] 使用迁移快照；[结束] 基线选择')
    snapshot = json.loads(snapshotPath.read_text(encoding='utf-8'))
    mediaKeys = {record[key] for records in snapshot.values() for record in records for key in ('key', 'original_key', 'thumbnail_key', 'cover_key') if record.get(key)}
    print(f'[开始] 导入公共文件，共 {len(mediaKeys)} 个')
    for fileIndex, key in enumerate(sorted(mediaKeys), 1):
        print(f'[开始] 公共文件 {fileIndex}/{len(mediaKeys)}')
        sourcePath = (seedPath / 'web-files' / key).resolve()
        print('[开始] 基线文件路径检查')
        if not sourcePath.is_relative_to((seedPath / 'web-files').resolve()):
            print('[分支] 路径越界；[结束] 基线文件路径检查')
            raise ValueError('基线文件路径越界')
        print('[分支] 路径有效；[结束] 基线文件路径检查')
        targetPath = storage.local_path(key)
        print('[开始] 已有公共文件检查')
        if not targetPath.exists():
            print('[分支] 首次写入')
            targetPath.parent.mkdir(parents=True, exist_ok=True)
            targetPath.write_bytes(sourcePath.read_bytes())
        else:
            print('[分支] 保留已有文件')
        print('[结束] 已有公共文件检查')
        print(f'[结束] 公共文件 {fileIndex}/{len(mediaKeys)}')
    print('[结束] 导入公共文件')
    with SessionLocal() as db:
        print(f'[开始] 导入基线表，共 {len(modelMap)} 表')
        for tableIndex, (tableName, model) in enumerate(modelMap.items(), 1):
            print(f'[开始] 基线表 {tableIndex}/{len(modelMap)}')
            records = snapshot[tableName]
            print(f'[开始] 基线记录，共 {len(records)} 条')
            for recordIndex, record in enumerate(records, 1):
                print(f'[开始] 基线记录 {recordIndex}/{len(records)}')
                print('[开始] 已有记录检查')
                if not db.get(model, record['id']):
                    print('[分支] 首次导入')
                    db.add(model(**record))
                else:
                    print('[分支] 保留现有设置')
                print('[结束] 已有记录检查')
                print(f'[结束] 基线记录 {recordIndex}/{len(records)}')
            print('[结束] 基线记录')
            db.commit()
            print(f'[结束] 基线表 {tableIndex}/{len(modelMap)}')
        print('[结束] 导入基线表')


if __name__ == '__main__':
    print('[开始] 公共基线导入入口')
    ImportBaseline()
    print('[结束] 公共基线导入入口')
