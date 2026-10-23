"""Export the API schema from the current application."""
import json
from pathlib import Path
import sys

# 路径
rootPath = Path(__file__).resolve().parents[1]
backendPath = rootPath / 'backend'
outputPath = rootPath / 'contracts' / 'openapi.json'
sys.path.insert(0, str(backendPath))

from app.main import app

# 主程序
outputPath.parent.mkdir(parents=True, exist_ok=True)
outputPath.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'接口定义已保存：{outputPath}')
