// 路径与参数：登录凭据只用于确定本机数据所属账号，业务键始终分区。
const globalKeys = new globalThis.Set(['nature:token', 'nature:user', 'nature:device', 'nature:signedOut']);

export function AccountId(): string {
  return wx.getStorageSync('nature:user')?.id || '';
}

export function EnsureAccount(accountId: string): void {
  console.log('[开始] 异步操作账号一致性');
  if (!accountId || accountId !== AccountId()) {
    console.log('[分支] 账号已改变，拒绝跨账号写入');
    throw new Error('账号已切换，原操作已停止，请重新打开页面');
  }
  console.log('[分支] 仍为原账号');
  console.log('[结束] 异步操作账号一致性');
}

function StorageKey(key: string): string {
  console.log('[开始] 本机存储账号选择');
  if (globalKeys.has(key)) {
    console.log('[分支] 登录状态键');
    console.log('[结束] 本机存储账号选择');
    return key;
  }
  console.log('[分支] 账号专属业务键');
  const userId = AccountId();
  console.log('[开始] 当前账号检查');
  if (!userId) {
    console.log('[分支] 无登录账号，隔离至空访客空间');
    console.log('[结束] 当前账号检查；结束本机存储账号选择');
    return 'nature:guest:' + key;
  }
  console.log('[分支] 已登录账号');
  console.log('[结束] 当前账号检查');
  console.log('[结束] 本机存储账号选择');
  return 'nature:account:' + userId + ':' + key;
}

export function Get(key: string): any { return wx.getStorageSync(StorageKey(key)); }
export function Set(key: string, value: any): void { wx.setStorageSync(StorageKey(key), value); }
export function Remove(key: string): void { wx.removeStorageSync(StorageKey(key)); }
export function Info(): WechatMiniprogram.GetStorageInfoSyncOption {
  const info = wx.getStorageInfoSync();
  const prefix = 'nature:account:' + AccountId() + ':';
  return {...info, keys: info.keys.filter(key => key.startsWith(prefix)).map(key => key.slice(prefix.length))};
}
