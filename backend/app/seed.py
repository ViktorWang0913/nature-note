"""Import project-supplied artwork; never create fictional personal observations."""
import hashlib
import json
import zipfile
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal
from . import models as m, storage

ROOT = Path(__file__).resolve().parents[1] / 'seed-assets'
PLANTS = {'二球悬铃木', '凌霄', '木犀', '火棘', '玉兰', '睡莲', '石榴', '紫叶李', '红豆杉', '银杏', '鹅掌楸'}
MAMMALS = {'东北刺猬', '赤腹松鼠', '黄鼬'}



def install(db, asset_id, title, data, category='birds'):
    obj = db.get(m.Asset, asset_id)
    if obj:
        return obj
    stored = storage.store_image(data, public=True, keep_original=False)
    obj = m.Asset(id=asset_id, user_id=None, title=title, source='public', category=category, **stored)
    db.add(obj)
    db.flush()
    return obj


def layout(bulbul_id, title, route_style='smooth'):
    return {
        'schema_version': 1, 'width': 3600, 'height': 2400, 'background': '#fff8dc',
        'elements': [
            {'id': 'title', 'type': 'text', 'x': 160, 'y': 90, 'width': 2400, 'height': 170, 'rotation': 0, 'z': 1, 'text': title, 'fontSize': 104, 'color': '#453c2d'},
            {'id': 'subtitle', 'type': 'text', 'x': 166, 'y': 270, 'width': 1800, 'height': 100, 'rotation': 0, 'z': 2, 'text': '自然记 Nature Note · 观察路线示意', 'fontSize': 48, 'color': '#756a55'},
            {'id': 'route', 'type': 'route', 'x': 260, 'y': 530, 'width': 2880, 'height': 1450, 'rotation': 0, 'z': 3,
             'route': {'style': route_style, 'points': [{'x': 150, 'y': 800}, {'x': 700, 'y': 400}, {'x': 1400, 'y': 720}, {'x': 2100, 'y': 350}, {'x': 2650, 'y': 850}],
                       'nodes': [{'id': 'demo-node-1', 'x': 150, 'y': 800, 'label': '01'}, {'id': 'demo-node-2', 'x': 1400, 'y': 720, 'label': '02'}, {'id': 'demo-node-3', 'x': 2650, 'y': 850, 'label': '03'}], 'color': '#bbb7af', 'lineWidth': 35}},
            {'id': 'bird', 'type': 'image', 'x': 880, 'y': 30, 'width': 670, 'height': 620, 'rotation': 0, 'z': 4, 'parent_id': 'route', 'node_id': 'demo-node-2', 'asset_id': bulbul_id},
            {'id': 'note', 'type': 'text', 'x': 460, 'y': 1760, 'width': 2700, 'height': 190, 'rotation': 0, 'z': 5, 'text': '添加你的照片与观察文字', 'fontSize': 66, 'color': '#534735'},
            {'id': 'footer', 'type': 'text', 'x': 170, 'y': 2180, 'width': 3000, 'height': 90, 'rotation': 0, 'z': 6, 'text': '观察日期：待填写    观察地点：待填写', 'fontSize': 48, 'color': '#756a55'},
        ],
    }


def seed():
    with SessionLocal() as db:
        by_name = {}
        archive = ROOT / 'illustrations.zip'
        if archive.exists():
            with zipfile.ZipFile(archive) as source:
                for entry in source.infolist():
                    if Path(entry.filename).suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
                        continue
                    title = Path(entry.filename).stem
                    if len(title) > 25:
                        continue
                    asset_id = 'public-bulbul' if title == '白头鹎' else 'public-' + hashlib.sha256(title.encode()).hexdigest()[:16]
                    category = 'plants' if title in PLANTS else 'mammals' if title in MAMMALS else 'birds'
                    by_name[title] = install(db, asset_id, title, source.read(entry), category)
        if '白头鹎' not in by_name:
            path = ROOT / 'cartoon-style-02-bulbul.png'
            if path.exists():
                by_name['白头鹎'] = install(db, 'public-bulbul', '白头鹎', path.read_bytes())
        for index, filename in enumerate(['photo-a-bulbul-stone.jpg', 'photo-b-bulbul-high-perch.jpg']):
            path = ROOT / filename
            if path.exists():
                install(db, f'public-photo-bulbul-{index + 1}', f'白头鹎 · 示例原图 {index + 1}', path.read_bytes())
        cover_path = ROOT / 'notebook-style.png'
        cover = install(db, 'public-notebook-style', '校园观鸟笔记 · 风格参考', cover_path.read_bytes(), 'environment') if cover_path.exists() else None
        for template_id, title, route_style in [('campus-birds', '校园观鸟笔记', 'smooth'), ('daily-observation', '我的自然观察', 'orthogonal'), ('weekend-walk', '周末观察手记', 'smooth')]:
            if not db.get(m.Template, template_id):
                db.add(m.Template(id=template_id, title=title, cover_key=cover.key if cover else '', layout=layout('public-bulbul', title, route_style)))
        db.commit()
        print('Seed ready: public artwork and 3 editable templates; personal atlases start empty. No personal observations or community posts were fabricated.')


if __name__ == '__main__':
    seed()
