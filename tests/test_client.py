from vs_opc.client import get_status


def test_get_status():
    status = get_status()
    assert isinstance(status, dict)
    assert status.get("status") == "ok"
