import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

// 路径
const frontendPath = fileURLToPath(new URL('..', import.meta.url));
const sourcePath = path.join(frontendPath, 'src', 'admin-preview.ts');
const outputPath = path.join(frontendPath, '..', 'backend', 'app', 'static', 'admin-preview.js');

// 主程序
await build({entryPoints: [sourcePath], outfile: outputPath, bundle: true,
  format: 'iife', platform: 'browser', target: 'es2022', minify: true});
console.log('已构建管理后台作品预览，复用现有画布渲染器。');
