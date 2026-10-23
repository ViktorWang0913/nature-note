import {renderScene} from './engine/render';
import type {Layout} from './types/models';

// 参数设置：列表及详情均按同一个已保存版本绘制，不读取用户离线缓存。
const previewMaxEdge = 1800;

// 自编函数
async function RenderAdminProject(canvas: HTMLCanvasElement, layout: Layout) {
  const images = new Map<string, HTMLImageElement>();
  const imageElements = layout.elements.filter(element => element.type === 'image');
  console.log(`[开始] 管理作品图片加载，共 ${imageElements.length} 项`);
  await Promise.all(imageElements.map(async (element, imageIndex) => {
    console.log(`[开始] 管理图片 ${imageIndex + 1}/${imageElements.length}`);
    console.log('[开始] 管理图片地址检查');
    if (!element.url?.startsWith('/api/admin/content-media/')) {
      console.log('[分支] 缺少已授权素材；[结束] 管理图片地址检查，提前结束图片加载');
      throw new Error('作品素材不可用，请刷新后重试');
    }
    console.log('[分支] 已授权的管理图片；[结束] 管理图片地址检查');
    const picture = new Image();
    await new Promise<void>((resolve, reject) => {
      picture.onload = () => resolve();
      picture.onerror = () => reject(new Error('部分素材已移除或版本已变化，请刷新作品'));
      picture.src = element.url!;
    });
    images.set(element.url!, picture);
    console.log(`[结束] 管理图片 ${imageIndex + 1}/${imageElements.length}`);
  }));
  console.log('[结束] 管理作品图片加载');
  const scale = Math.min(1, previewMaxEdge / Math.max(layout.width, layout.height));
  canvas.width = Math.round(layout.width * scale);
  canvas.height = Math.round(layout.height * scale);
  await document.fonts.ready;
  renderScene(canvas.getContext('2d'), layout, images, {viewport: {x: 0, y: 0, scale}});
}

// 主程序
Object.assign(window, {RenderAdminProject});
