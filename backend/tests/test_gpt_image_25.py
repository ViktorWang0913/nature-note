"""Image generation request protocol."""
import pytest
from app import visual_ai


@pytest.mark.parametrize('references,size,operation', [
    ([], '1024x1024', 'generations'),
    (['data:image/jpeg;base64,anBlZw=='], '1024x1024', 'edits'),
    (['data:image/png;base64,cG5n', 'data:image/jpeg;base64,anBlZw=='], '1024x1536', 'edits'),
])
def test_gpt_25_documented_protocol(references, size, operation):
    endpoint, body = visual_ai.BuildImageRequest('https://www.rightapi.ai', 'gpt-image-2.5',
        '保留主体轮廓，绘制水彩风格，纯白背景', references, size)
    assert endpoint == 'https://www.rightapi.ai/v1/images/' + operation
    assert body['model'] == 'gpt-image-2.5' and body['async'] is True and body['n'] == 1
    assert body['size'] == size and body.get('image', []) == references
    assert not {'background', 'response_format', 'generationConfig', 'mask'}.intersection(body)
