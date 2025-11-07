def test_try_reconnect_helper_sets_backoff():
    import importlib
    gw = importlib.import_module('vs_opc.plc_gateway_server')
    key = 'compactlogix'
    # reset health
    gw.plc_health[key]['fail_count'] = 0
    gw.plc_health[key]['recent_errors'].clear()

    class BrokenDriver:
        connected = False

    class RaisingDriverCls:
        def __init__(self, ip):
            raise RuntimeError('create-failed')

    driver = BrokenDriver()
    # call helper which should catch the creation error and set backoff
    res = gw.try_reconnect_helper(driver, RaisingDriverCls, '127.0.0.1', key)

    assert gw.plc_health[key]['fail_count'] >= 1
    assert float(gw.plc_health[key].get('last_backoff', 0.0)) > 0.0
