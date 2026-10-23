from app import models as m


def test_node_attachments_preserve_coordinates_and_reject_foreign_updates(client, users):
    _, ownerHeaders = users[0]
    _, otherHeaders = users[1]
    track = client.post('/api/v1/tracks',headers=ownerHeaders,json={}).json()
    node = client.post('/api/v1/tracks/'+track['id']+'/nodes',headers=ownerHeaders,json={'latitude':31.3,'longitude':121.5,'text':'原观察'}).json()
    assets = client.get('/api/v1/assets?source=public',headers=ownerHeaders).json()['items'][:2]
    endpoint = '/api/v1/nodes/'+node['id']
    saved = client.patch(endpoint,headers=ownerHeaders,json={'asset_ids':[assets[0]['id']],'cover_asset_id':assets[0]['id']})
    assert saved.status_code == 200, saved.text
    assert saved.json()['latitude'] == node['latitude']
    assert saved.json()['longitude'] == node['longitude']
    assert saved.json()['text'] == node['text']
    assert client.patch(endpoint,headers=otherHeaders,json={'text':'越权'}).status_code == 404
    assert client.patch(endpoint,headers=ownerHeaders,json={'cover_asset_id':assets[1]['id']}).status_code == 422
    assert client.get(endpoint,headers=ownerHeaders).json()['cover_asset_id'] == assets[0]['id']
    assert client.patch(endpoint,headers=ownerHeaders,json={'asset_ids':[]}).status_code == 200
    assert client.get(endpoint,headers=ownerHeaders).json()['cover_asset_id'] is None


def test_obsolete_layout_cannot_rewrite_node_attachments(client, users):
    _, ownerHeaders = users[0]
    project = client.post('/api/v1/projects',headers=ownerHeaders,json={'title':'旧协议隔离'}).json()
    track = client.post('/api/v1/tracks',headers=ownerHeaders,json={'project_id':project['id']}).json()
    node = client.post('/api/v1/tracks/'+track['id']+'/nodes',headers=ownerHeaders,json={'latitude':31.3,'longitude':121.5}).json()
    layout = {'schema_version':1,'width':3600,'height':2400,'background':'#ffffff','elements':[{'id':'old-route','type':'route','x':0,'y':0,'width':100,'height':100,'route':{'track_id':track['id'],'nodes':[{'id':node['id'],'asset_ids':['invalid']}],'points':[]}}]}
    response = client.patch('/api/v1/projects/'+project['id'],headers=ownerHeaders,json={'base_version':1,'layout':layout})
    assert response.status_code in {404,422}
    assert client.get('/api/v1/nodes/'+node['id'],headers=ownerHeaders).json()['asset_ids'] == []
    assert client.get('/api/v1/projects/'+project['id'],headers=ownerHeaders).json()['version'] == 1
