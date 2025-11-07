import importlib


def test_compute_backoff_delay():
    gw = importlib.import_module('vs_opc.plc_gateway_server')
    old_base = gw.RECONNECT_BASE
    old_max = gw.RECONNECT_MAX
    try:
        gw.RECONNECT_BASE = 1.0
        gw.RECONNECT_MAX = 4.0
        assert gw.compute_backoff_delay(0) == 0.0
        assert gw.compute_backoff_delay(1) == 1.0
        assert gw.compute_backoff_delay(2) == 2.0
        # With base=1, delays are 1,2,4 and capped at RECONNECT_MAX=4
        assert gw.compute_backoff_delay(3) == 4.0
        assert gw.compute_backoff_delay(4) == 4.0
    finally:
        gw.RECONNECT_BASE = old_base
        gw.RECONNECT_MAX = old_max


def test_health_includes_last_backoff():
    gw = importlib.import_module('vs_opc.plc_gateway_server')
    # set a known backoff and verify the health endpoint exposes it
    gw.plc_health['compactlogix']['last_backoff'] = 2.5
    client = gw.app.test_client()
    resp = client.get('/api/v1/hmi/health')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'plc_health' in body
    assert 'compactlogix' in body['plc_health']
    assert float(body['plc_health']['compactlogix'].get('last_backoff', 0.0)) == 2.5
