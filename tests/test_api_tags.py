import json
import pytest
from flask import Flask

from vs_opc import api as tags_api_module
from vs_opc.tag_store import TagStore


def create_test_app():
    app = Flask(__name__)
    ts = TagStore()
    # attach fresh TagStore to blueprint
    tags_api_module.bp.tag_store = ts
    app.register_blueprint(tags_api_module.bp)
    return app, ts


def test_create_and_get_tag():
    app, ts = create_test_app()
    client = app.test_client()

    # create a tag
    resp = client.post('/api/v1/tags', json={
        'tag_id': 'T1',
        'name': 'T1',
        'plc_id': 'plcA',
        'address': 'ADDR1',
        'data_type': 'Boolean',
        'initial_value': False
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert 'created' in data and 'T1' in data['created']

    # list tags
    r = client.get('/api/v1/tags')
    assert r.status_code == 200
    tags = r.get_json()['tags']
    assert any(t['tag_id'] == 'T1' for t in tags)

    # get single tag
    r = client.get('/api/v1/tags/T1')
    assert r.status_code == 200
    tag = r.get_json()['tag']
    assert tag['tag_id'] == 'T1'
    assert tag['value'] is False


def test_patch_update_and_delete():
    app, ts = create_test_app()
    client = app.test_client()

    # create tag
    r = client.post('/api/v1/tags', json={'tag_id': 'T2', 'name': 'T2', 'initial_value': 123})
    assert r.status_code == 201

    # patch metadata and value
    r = client.patch('/api/v1/tags/T2', json={'name': 'TWO', 'value': 456})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get('updated') == 'T2'

    # get and verify changes
    r = client.get('/api/v1/tags/T2')
    assert r.status_code == 200
    tag = r.get_json()['tag']
    assert tag['name'] == 'TWO'
    assert tag['value'] == 456

    # delete
    r = client.delete('/api/v1/tags/T2')
    assert r.status_code == 200
    assert r.get_json().get('deleted') == 'T2'

    # subsequent get -> 404
    r = client.get('/api/v1/tags/T2')
    assert r.status_code == 404


def test_import_replace_all_and_batch_create():
    app, ts = create_test_app()
    client = app.test_client()

    # batch create using POST
    r = client.post('/api/v1/tags', json={'tags': [
        {'tag_id': 'A', 'name': 'A', 'initial_value': 1},
        {'tag_id': 'B', 'name': 'B', 'initial_value': 2}
    ]})
    assert r.status_code == 201
    assert set(r.get_json()['created']) >= {'A', 'B'}

    # import with replace_all should clear and add new set
    payload = {'tags': [
        {'tag_id': 'X', 'name': 'X', 'initial_value': 9}
    ]}
    r = client.put('/api/v1/tags/import?replace_all=true', json=payload)
    assert r.status_code == 200
    imported = r.get_json().get('imported', [])
    assert imported == ['X']

    # list now only contains X
    r = client.get('/api/v1/tags')
    tags = r.get_json()['tags']
    ids = [t['tag_id'] for t in tags]
    assert ids == ['X']
