// 地图适配回归：模拟 SDK 与浏览器定位，不代表真机或地图服务验收。
import { expect, test, vi } from 'vitest';
import { reactive, nextTick } from 'vue';

const hooks = vi.hoisted(() => ({ mounted: [] as (() => void)[] }));
vi.mock('vue', async importOriginal => ({
  ...await importOriginal<typeof import('vue')>(),
  onMounted: (callback: () => void) => hooks.mounted.push(callback),
  onBeforeUnmount: vi.fn(),
}));
vi.mock('./storage', () => ({
  ReadValue: vi.fn(), WriteValue: vi.fn(), RemoveValue: vi.fn(),
  StorageInfo: vi.fn(), ReadFile: vi.fn(), WriteFile: vi.fn(), CurrentAccount: () => 'review-account',
}));
vi.mock('./media', () => ({ ReadBlob: vi.fn(), MediaUrl: vi.fn() }));
import { WebMap } from './components';
import { InstallPlatform, StopLocation } from './platform';

test('定位按钮请求新位置，转换地图坐标但不启动轨迹监听', () => {
  const geoMock = { getCurrentPosition: vi.fn(), watchPosition: vi.fn(), clearWatch: vi.fn() };
  vi.stubGlobal('navigator', { geolocation: geoMock });
  vi.stubGlobal('window', { addEventListener: vi.fn(), dispatchEvent: vi.fn() });
  InstallPlatform();
  wx.createMapContext('route-map').moveToLocation({});
  expect(geoMock.getCurrentPosition).toHaveBeenCalledOnce();
  geoMock.getCurrentPosition.mock.calls[0][0]({coords:{latitude:31.3,longitude:121.5,accuracy:10},timestamp:1});
  const event=vi.mocked(window.dispatchEvent).mock.calls[0][0] as CustomEvent;
  expect(event.detail.mapId).toBe('route-map');
  expect(event.detail.coordinate_system).toBe('gcj02');
  expect(event.detail.longitude).not.toBe(121.5);
  expect(geoMock.watchPosition).not.toHaveBeenCalled();
  const failure=vi.fn();
  wx.createMapContext('route-map').moveToLocation({fail:failure});
  geoMock.getCurrentPosition.mock.calls[1][1]({message:'permission denied'});
  expect(failure).toHaveBeenCalledOnce();
  wx.createMapContext('route-map').moveToLocation({fail:failure});
  StopLocation();
  geoMock.getCurrentPosition.mock.calls[2][0]({coords:{latitude:31.3,longitude:121.5,accuracy:10},timestamp:1});
  expect(window.dispatchEvent).toHaveBeenCalledOnce();
});

test('首个定位点到达后地图应离开默认中心', async () => {
  const centerMock = vi.fn();
  const geometryMock = vi.fn();
  const markerGeometry = vi.fn();
  const mapApi = {
    Map: class { setCenter = centerMock; destroy = vi.fn(); },
    LatLng: class { constructor(public latitude: number, public longitude: number) {} },
    MultiPolyline: class { setGeometries = geometryMock; },
    MultiMarker: class { setGeometries = markerGeometry; on = vi.fn(); },
    PolylineStyle: class {}, MarkerStyle: class {},
  };
  vi.stubGlobal('window', { TMap: mapApi, addEventListener: vi.fn() });
  vi.stubGlobal('document', {
    createElement: () => ({}), head: { append: (script: any) => script.onload() },
  });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ map_key: 'mock-map-key' }) }));
  const props = reactive({ id:'route-map',located:false,latitude: 31.3, longitude: 121.5, polyline: [], markers: [], scale: 17 });
  (WebMap as any).setup(props, { emit: vi.fn() });
  hooks.mounted[0]();
  await vi.waitFor(() => expect(geometryMock).toHaveBeenCalled());
  props.latitude = 22.5;
  props.longitude = 114.1;
  props.located = true;
  await nextTick();
  expect(centerMock).toHaveBeenCalledOnce();
  expect(centerMock.mock.calls[0][0]).toMatchObject({latitude:22.5,longitude:114.1});
  expect(markerGeometry).toHaveBeenCalledWith([{id:'current-location',styleId:'current',position:expect.objectContaining({latitude:22.5,longitude:114.1})}]);
  props.latitude = 22.6;
  await nextTick();
  expect(centerMock).toHaveBeenCalledOnce();
  expect(markerGeometry).toHaveBeenLastCalledWith([{id:'current-location',styleId:'current',position:expect.objectContaining({latitude:22.6,longitude:114.1})}]);
  const locateListener=vi.mocked(window.addEventListener).mock.calls.find(call=>call[0]==='nature-map-locate')![1] as EventListener;
  locateListener(new CustomEvent('nature-map-locate',{detail:{mapId:'another-map',latitude:23,longitude:115}}));
  expect(centerMock).toHaveBeenCalledOnce();
  locateListener(new CustomEvent('nature-map-locate',{detail:{mapId:'route-map',latitude:23,longitude:115}}));
  expect(centerMock).toHaveBeenCalledTimes(2);
  expect(centerMock.mock.calls[1][0]).toMatchObject({latitude:23,longitude:115});
});
