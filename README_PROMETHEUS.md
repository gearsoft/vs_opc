Prometheus metrics (optional)

This project exposes an optional Gauge metric `vs_opc_plc_last_backoff_seconds{plc="..."}`
when the Python package `prometheus_client` is installed. The code will update the
Gauge whenever the gateway computes an exponential backoff for a PLC reconnect.

How to enable metrics in-process

1. Install the prometheus client:

   pip install prometheus_client

2. In your application process (e.g. when starting the gateway) start the
   Prometheus HTTP endpoint, for example on port 8000:

   from prometheus_client import start_http_server
   start_http_server(8000)

   The metric will then be available at http://<host>:8000/metrics. The
   `last_backoff` Gauge is labeled by `plc` and contains the most recent
   backoff delay (seconds) computed for that PLC.

   Additional metrics

   - `vs_opc_plc_fail_count{plc="..."}`: Gauge reporting the current fail_count for each PLC.
   - `vs_opc_poll_latency_seconds`: Histogram observing the poll cycle latency (seconds) for the PLC poll loop.

   Test-only environment variables and readiness signal

   - `GATEWAY_MOCK_PLC=1` enables a mock PLC driver used by tests.
   - `GATEWAY_MOCK_FAIL_RECONNECT=1` forces the gateway to pre-populate a reconnect failure so health/backoff behavior can be tested deterministically.

   The server also exposes a small readiness probe useful for tests and orchestration:

   - HTTP: `GET /api/v1/hmi/ready` returns 200 and `{ "ready": true }` once the gateway has completed initialization and prepopulation; otherwise returns 503.
   - File: if you set the `READY_FILE` environment variable to a writable path, the gateway will write a small timestamp file there when it becomes ready.

Auto-start via environment variable

You can configure the gateway to automatically start a Prometheus HTTP
endpoint by setting the `METRICS_PORT` or `PROMETHEUS_PORT` environment
variable before launching the gateway. When set and `prometheus_client` is
installed, the gateway will call `start_http_server(<port>)` during startup.

Example (bash):

```bash
METRICS_PORT=8000 python -m vs_opc.plc_gateway_server
```

This is optional and non-fatal — if the package isn't installed or the port
cannot be opened the gateway will continue to run without metrics.

Notes
- The project is tolerant if `prometheus_client` is not installed — metrics
  code is a no-op in that case.
- For Kubernetes or production deployment, prefer running a sidecar exporter
  or scraping the application's metrics endpoint directly from Prometheus.
