import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json

# Full-gateway integration test (mock PLC) that starts the gateway subprocess,
# forces the reconnect/backoff path to be exercised (via GATEWAY_MOCK_FAIL_RECONNECT=1),
# then queries /api/v1/hmi/health until last_backoff is visible.

def test_gateway_full_integration_backoff(tmp_path):
    env = os.environ.copy()
    env['GATEWAY_MOCK_PLC'] = '1'
    env['GATEWAY_MOCK_FAIL_RECONNECT'] = '1'

    py = sys.executable
    log_file = tmp_path / "gateway_full.log"
    err_file = tmp_path / "gateway_full.err"

    proc = subprocess.Popen([py, "-m", "vs_opc.plc_gateway_server"],
                            stdout=open(log_file, "wb"), stderr=open(err_file, "wb"),
                            env=env)

    try:
        # wait for Flask to start and health endpoint to respond
        for _ in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/health", timeout=1) as r:
                    data = json.loads(r.read().decode('utf-8'))
                    if 'plc_health' in data:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("Gateway did not start or health endpoint not available")

        # Poll health until last_backoff appears
        saw = False
        for _ in range(20):
            with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/health", timeout=1) as r:
                data = json.loads(r.read().decode('utf-8'))
                cl = data.get('plc_health', {}).get('compactlogix', {})
                lb = float(cl.get('last_backoff', 0.0))
                if lb > 0.0:
                    saw = True
                    break
            time.sleep(0.5)

        assert saw, 'Expected last_backoff to be set and > 0'

        # request shutdown
        req = urllib.request.Request("http://127.0.0.1:5000/api/v1/hmi/stop", method='POST')
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read().decode('utf-8'))
            assert data.get('status') == 'shutting_down'

        time.sleep(1)
        with open(err_file, 'r', encoding='utf-8', errors='ignore') as f:
            errtxt = f.read()
            assert 'Traceback' not in errtxt
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
