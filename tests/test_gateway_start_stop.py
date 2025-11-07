import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json

# This test starts the gateway as a subprocess, polls /api/v1/hmi/health,
# posts to /api/v1/hmi/stop and ensures the process exits without leaving a
# 'Traceback' string in stderr.

def test_start_stop_gateway(tmp_path):
    env = os.environ.copy()
    # Run gateway in mock PLC mode so it doesn't try to reach real PLCs during tests
    env['GATEWAY_MOCK_PLC'] = '1'
    # Use the current python executable for a subprocess invocation
    py = sys.executable

    log_file = tmp_path / "gateway_test.log"
    err_file = tmp_path / "gateway_test.err"

    proc = subprocess.Popen([py, "-m", "vs_opc.plc_gateway_server"],
                            stdout=open(log_file, "wb"), stderr=open(err_file, "wb"),
                            env=env)

    try:
        # wait for Flask to start (give it a few seconds)
        for _ in range(20):
            try:
                with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/hmi/health", timeout=1) as r:
                    body = r.read().decode("utf-8")
                    # health endpoint should respond with JSON
                    data = json.loads(body)
                    assert "status" in data
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("Gateway did not start or health endpoint not available")

        # Request shutdown
        req = urllib.request.Request("http://127.0.0.1:5000/api/v1/hmi/stop", method="POST")
        with urllib.request.urlopen(req, timeout=2) as r:
            body = r.read().decode("utf-8")
            data = json.loads(body)
            assert data.get("status") == "shutting_down"

        # give the gateway a brief moment to process shutdown and write any errors
        time.sleep(1)
        # read stderr and ensure no Traceback left
        with open(err_file, "r", encoding="utf-8", errors="ignore") as f:
            errtxt = f.read()
            assert "Traceback" not in errtxt
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
