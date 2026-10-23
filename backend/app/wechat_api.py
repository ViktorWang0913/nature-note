"""Server-side WeChat calls. Never return credentials or raw upstream errors."""
import time
from threading import Lock

import httpx

from .config import settings
from .security import fail

tokenCache = {'value': '', 'expires': 0.0}
tokenLock = Lock()
apiBase = 'https://api.weixin.qq.com'


def ReadResponse(path, body, token=None, required=True):
    # This exception boundary only covers reading the remote API response.
    try:
        response = httpx.post(apiBase + path, params={'access_token': token} if token else None, json=body, timeout=15)
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError):
        print('[开始] 微信读取失败处理')
        if required:
            print('[分支] 授权请求明确失败')
            fail(503, 'wechat_unavailable', '微信接口暂时不可用，请稍后重试')
        else:
            print('[分支] 自动审核保留待人工状态')
            print('[结束] 微信读取失败处理；提前返回失败状态')
            return {'errcode': -1}

    print('[开始] 微信接口业务结果检查')
    if result.get('errcode', 0) != 0 and required:
        print('[分支] 微信返回不可用状态，不输出凭据和上游报文')
        fail(503, 'wechat_rejected', '微信接口未完成，请核对接口权限或重新授权')
    else:
        print('[分支] 微信返回有效结果')
    print('[结束] 微信接口业务结果检查')
    return result


def AccessToken(required=True):
    cfg = settings()
    print('[开始] 微信配置检查')
    if not cfg.wechat_app_id or not cfg.wechat_app_secret:
        print('[分支] 尚未配置微信服务端凭据')
        fail(503, 'wechat_unconfigured', '微信授权服务尚未配置')
    else:
        print('[分支] 已配置服务端凭据')
    print('[结束] 微信配置检查')
    with tokenLock:
        print('[开始] 微信凭据缓存检查')
        if tokenCache['expires'] <= time.time():
            print('[分支] 获取稳定凭据，不强制刷新')
            result = ReadResponse('/cgi-bin/stable_token', {'grant_type':'client_credential',
                'appid':cfg.wechat_app_id, 'secret':cfg.wechat_app_secret, 'force_refresh':False}, required=required)
            print('[开始] 稳定凭据读取结果')
            if not result.get('access_token'):
                print('[分支] 无凭据，转人工审核')
                print('[结束] 稳定凭据读取结果；提前退出')
                return ''
            else:
                print('[分支] 有效凭据')
            print('[结束] 稳定凭据读取结果')
            tokenCache['value'] = result['access_token']
            tokenCache['expires'] = time.time() + max(0, int(result['expires_in']) - 60)
        else:
            print('[分支] 复用有效凭据')
        print('[结束] 微信凭据缓存检查')
        return tokenCache['value']


def Phone(code, openid):
    result = ReadResponse('/wxa/business/getuserphonenumber', {'code':code, 'openid':openid}, AccessToken())
    info = result.get('phone_info', {})
    number = info.get('purePhoneNumber', '')
    print('[开始] 微信手机号校验')
    if not number.isdigit() or not 5 <= len(number) <= 20 or info.get('watermark', {}).get('appid') != settings().wechat_app_id:
        print('[分支] 返回内容不匹配当前小程序')
        fail(503, 'phone_invalid', '手机号授权未完成，请重新授权')
    else:
        print('[分支] 微信已验证手机号及账号对应关系')
    print('[结束] 微信手机号校验')
    return str(info.get('countryCode', '')) + ':' + number, number[:3] + '****' + number[-4:]
