import os
import time
import threading
import asyncio

import pytest

from vs_opc import plc_gateway_server as gateway
from vs_opc import api as tags_api


def _start_opc_server_in_thread():
    # Ensure MOCK mode so we don't need real PLCs
    os.environ['GATEWAY_MOCK_PLC'] = '1'

    def _run():
        try:
            asyncio.run(gateway.run_opcua_server())
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def test_opcua_node_lifecycle():
    # start OPC UA server (mock drivers)
    th = _start_opc_server_in_thread()

    # wait for server to initialize
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if getattr(gateway, 'opcua_loop', None) is not None:
            break
        time.sleep(0.05)
    assert gateway.opcua_loop is not None

    # attach TagStore to blueprint for test client
    tags_api.bp.tag_store = gateway.tag_store
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(tags_api.bp)
    client = app.test_client()

    # create a new tag via API; this should schedule an OPC UA node creation
    r = client.post('/api/v1/tags', json={'tag_id': 'IT1', 'name': 'Integration1', 'data_type': 'Int32', 'initial_value': 5})
    assert r.status_code == 201

    # wait for the scheduled creation to run
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if 'IT1' in gateway.opcua_vars:
            break
        time.sleep(0.05)
    assert 'IT1' in gateway.opcua_vars

    # delete via API
    r = client.delete('/api/v1/tags/IT1')
    assert r.status_code == 200

    # wait for deletion to propagate
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if 'IT1' not in gateway.opcua_vars:
            break
        time.sleep(0.05)
    assert 'IT1' not in gateway.opcua_vars

    # schedule server shutdown
    try:
        gateway._schedule_on_opc_loop(gateway._shutdown_gateway)
    except Exception:
        pass
