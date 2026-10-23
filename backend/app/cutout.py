"""Remove a plain, edge-connected backdrop; never claim semantic segmentation."""
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

# 参数设置：在有对比度的纯色底上工作，拒绝无法可靠分离的场景。
backgroundTolerance = 36
minimumForegroundRatio = 0.005
minimumBackgroundRatio = 0.05
maskMaximumSize = 1536


def RemoveBackground(picture):
    result = picture.convert('RGBA')
    originalAlpha = result.getchannel('A')
    alphaHistogram = originalAlpha.histogram()
    pixelCount = result.width * result.height
    print('[开始] 已有透明通道检查')
    if sum(alphaHistogram[:16]) / pixelCount >= minimumBackgroundRatio and sum(alphaHistogram[240:]) / pixelCount >= minimumForegroundRatio:
        print('[分支] 保留已有真实透明图片；[结束] 已有透明通道检查，提前结束')
        return result
    print('[分支] 本地分离纯色背景；[结束] 已有透明通道检查')

    # 仅以四周像素估计底色，不把主体内部同色区域全局擦除。
    sample = result.convert('RGB')
    sample.thumbnail((maskMaximumSize, maskMaximumSize))
    width, height = sample.size
    border = Image.new('RGB', (2 * (width + height), 1))
    border.paste(sample.crop((0, 0, width, 1)), (0, 0))
    border.paste(sample.crop((0, height - 1, width, height)), (width, 0))
    border.paste(sample.crop((0, 0, 1, height)).transpose(Image.Transpose.ROTATE_90), (2 * width, 0))
    border.paste(sample.crop((width - 1, 0, width, height)).transpose(Image.Transpose.ROTATE_90), (2 * width + height, 0))
    backgroundColor = tuple(ImageStat.Stat(border).median)
    difference = ImageChops.difference(sample, Image.new('RGB', sample.size, backgroundColor))
    red, green, blue = difference.split()
    distance = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    borderDifference = ImageChops.difference(border, Image.new('RGB', border.size, backgroundColor))
    borderRed, borderGreen, borderBlue = borderDifference.split()
    borderHistogram = ImageChops.lighter(ImageChops.lighter(borderRed, borderGreen), borderBlue).histogram()
    print('[开始] 背景一致性检查')
    if sum(borderHistogram[:backgroundTolerance + 1]) / border.width < 0.9:
        print('[分支] 复杂背景，不能可靠抠图；[结束] 背景一致性检查，提前结束')
        raise ValueError('图片背景过于复杂，自动抠图未完成；请按原任务编号核对图片和费用')
    print('[分支] 四周底色一致；[结束] 背景一致性检查')

    # 补一圈候选背景，让一次洪水填充覆盖与任何边缘连通的背景。
    candidate = distance.point(lambda value: 255 * (value <= backgroundTolerance))
    connected = ImageOps.expand(candidate, border=1, fill=255)
    ImageDraw.floodfill(connected, (0, 0), 128)
    connected = connected.crop((1, 1, width + 1, height + 1))
    foreground = connected.point(lambda value: 255 * (value != 128))
    foregroundRatio = ImageStat.Stat(foreground).mean[0] / 255
    print('[开始] 抠图有效面积检查')
    if not minimumForegroundRatio <= foregroundRatio <= 1 - minimumBackgroundRatio:
        print('[分支] 主体或背景面积无效；[结束] 抠图有效面积检查，提前结束')
        raise ValueError('无法分离有效主体，自动抠图未完成；请按原任务编号核对图片和费用')
    print('[分支] 主体与透明背景均有效；[结束] 抠图有效面积检查')

    # 轻微内缩和羽化减少纯色光边；保持原分辨率及原透明度。
    feathered = foreground.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    outputAlpha = feathered.resize(result.size, Image.Resampling.LANCZOS)
    result.putalpha(ImageChops.darker(originalAlpha, outputAlpha))
    return result
