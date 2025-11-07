import sys
import subprocess


# Simpler subprocess-based test: import the gateway module in a short-lived
# subprocess, force the reconnect-helper to exercise the failure/recreate
# path (by providing a driver_cls that raises on construction), and print the
# resulting last_backoff for the compactlogix entry. This avoids starting the
# full OPC UA server while still validating the backoff bookkeeping in a
# separate process.


def test_gateway_backoff_sets_last_backoff(tmp_path):
    py = sys.executable
    # Build a short python snippet that sets the env var and invokes the helper
    snippet = (
        "import os, importlib;"
        "os.environ['GATEWAY_MOCK_FAIL_RECONNECT']='1';"
        "gw=importlib.import_module('vs_opc.plc_gateway_server');"
        "Broken=type('Broken',(),{'connected':False});"
        "RaisingCls=type('RaisingCls',(),{'__init__':lambda self,ip: (_ for _ in ()).throw(RuntimeError('boom'))});"
        "gw.try_reconnect_helper(Broken(), RaisingCls, '127.0.0.1', 'compactlogix');"
        "print(float(gw.plc_health['compactlogix'].get('last_backoff', 0.0)))"
    )

    proc = subprocess.Popen([py, '-c', snippet], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=10)
    assert proc.returncode == 0, f"Subprocess failed: {err}"
    val = float(out.strip() or 0.0)
    assert val > 0.0, f"Expected last_backoff>0, got {val}"
