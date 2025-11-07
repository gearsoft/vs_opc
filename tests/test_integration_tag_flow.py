import os
import sys
import time
import subprocess
import urllib.request
import json


def test_post_tag_becomes_ready_and_visible(tmp_path):
    """Integration: start gateway (mock), POST a tag, expect readiness true and tag in /api/v1/hmi/data

    This test mirrors the production flow: the gateway is started in MOCK mode
    (so no hardware required), the REST API is used to create a tag, then we
    poll readiness and finally assert the tag appears in the data dump.
    """
    env = os.environ.copy()
    env['GATEWAY_MOCK_PLC'] = '1'
    # Ensure mock mode does not pre-populate reconnect failures
    env['GATEWAY_MOCK_FAIL_RECONNECT'] = '0'

    py = sys.executable
    log_file = tmp_path / "integration.log"
    err_file = tmp_path / "integration.err"

    proc = subprocess.Popen([py, "-m", "vs_opc.plc_gateway_server"], stdout=open(log_file, "wb"), stderr=open(err_file, "wb"), env=env)
    try:
        # wait until the REST endpoint responds (server up)
        for _ in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/ready", timeout=1) as r:
                    # server may return 503 before first poll completes
                    break
            except Exception:
                time.sleep(0.5)
        # POST a new tag
        payload = {
            "tag_id": "INT_TEST",
            "name": "INT_TEST",
            "plc_id": "compactlogix",
            "address": "INT_TEST_ADDR",
            "data_type": "Double",
            "initial_value": 9.81
        }
        req = urllib.request.Request("http://127.0.0.1:5000/api/v1/tags", data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"}, method='POST')
        with urllib.request.urlopen(req, timeout=3) as r:
            assert r.status == 201

        # wait for readiness to become true (some runs mark ready after first poll)
        for _ in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/ready", timeout=1) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.25)

        # finally read data and assert our tag is present
        with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/data", timeout=2) as r:
            assert r.status == 200
            data = json.loads(r.read().decode('utf-8'))
            tags = data.get('tags', {})
            assert 'INT_TEST' in tags

    finally:
        # request graceful shutdown
        try:
            req = urllib.request.Request("http://127.0.0.1:5000/api/v1/hmi/stop", method='POST')
            with urllib.request.urlopen(req, timeout=2):
                pass
        except Exception:
            pass
        # ensure process is gone
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
