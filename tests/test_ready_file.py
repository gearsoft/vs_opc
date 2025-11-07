import os
import sys
import time
import subprocess
import urllib.request
import json

# Test that the readiness endpoint returns 200 and READY_FILE is written

def test_ready_file_and_endpoint(tmp_path):
    env = os.environ.copy()
    env['GATEWAY_MOCK_PLC'] = '1'
    env['GATEWAY_MOCK_FAIL_RECONNECT'] = '1'
    ready_file = str(tmp_path / "gateway.ready")
    env['READY_FILE'] = ready_file

    py = sys.executable
    log_file = tmp_path / "gateway_ready.log"
    err_file = tmp_path / "gateway_ready.err"

    proc = subprocess.Popen([py, "-m", "vs_opc.plc_gateway_server"],
                            stdout=open(log_file, "wb"), stderr=open(err_file, "wb"),
                            env=env)
    try:
        # wait for readiness endpoint
        for _ in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/ready", timeout=1) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("Gateway did not become ready in time")

        # check the ready file exists
        assert os.path.exists(ready_file), "READY_FILE was not written"

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
