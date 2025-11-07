# vs_opc Gateway — Quick start

This small README explains how to run the `vs_opc` PLC gateway in MOCK mode (for development and tests) and in real-PLC mode, and how the gateway handles Decimal values when returning JSON to clients (important for the Flutter HMI).

## Purpose

`vs_opc` is a Python gateway that reads PLC tags (CompactLogix and SLC 5/05), exposes them via OPC UA and a REST API, and uses an in-memory `TagStore` as the authoritative source of tag values. By default the server does not load PLC or tag configuration from files — tags are added/managed via the REST API.

## Prerequisites

- Python 3.10+ recommended
- Activate your project venv (example assumes `.venv` in the `vs_opc` folder)

PowerShell example to activate the venv:

```powershell
cd 'C:\Users\John\Documents\vscode\visualpanel_workspace\vs_opc'
.\.venv\Scripts\Activate.ps1
```

Install optional runtime/test dependencies as needed (for example `asyncua` if you want the full OPC UA server in non-MOCK runs):

```powershell
pip install -r requirements.txt   # if provided
pip install asyncua               # optional: full OPC UA server
```

## Run in MOCK mode (recommended for development and CI)

When running in MOCK mode the gateway provides deterministic drivers and does not require real PLC hardware. This is the recommended mode during development.

PowerShell example:

```powershell
# Set mock drivers
$env:GATEWAY_MOCK_PLC = '1'
.\.venv\Scripts\Activate.ps1
# start gateway (logs redirected to server.log / server.err if you like)
python -m vs_opc.plc_gateway_server > server.log 2> server.err
```

Once started you can use the REST API to add tags and to probe readiness and data. Example (PowerShell):

```powershell
# Create a tag via REST (example JSON body; adjust fields as required by your API schema)
$body = '{"id":"TEST_TEMP","plc":"compactlogix","address":"Main.Temp","datatype":"Decimal","value":"1.2300"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/v1/tags -Body $body -ContentType 'application/json'

# Check readiness
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/v1/hmi/ready

# Fetch current HMI data
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/v1/hmi/data
```

## Run against real PLCs

If you want the gateway to connect to actual PLC hardware, unset/mock mode and provide PLC IPs via environment variables. The gateway will attempt persistent connections with reconnect/backoff behavior.

PowerShell example:

```powershell
$env:GATEWAY_MOCK_PLC = '0'
$env:COMPACTLOGIX_IP = '192.168.32.201'
$env:SLC500_IP = '192.168.32.146'
.\.venv\Scripts\Activate.ps1
python -m vs_opc.plc_gateway_server
```

Notes:
- If you set `GATEWAY_MOCK_PLC` to `'0'` the gateway will attempt to use the native drivers (pycomm3). Ensure `pycomm3` is installed and that the PLCs are reachable.
- Other env vars supported: `POLL_PERIOD`, `RECONNECT_BASE`, `RECONNECT_MAX`, `PLC_SOCKET_TIMEOUT`, and `READY_FILE` (if you want creation of a readiness file on disk).

## Decimal serialization behavior (important for clients/HMI)

- Internally the gateway uses Python's `decimal.Decimal` for precise numeric storage where appropriate.
- When the REST API returns tag values, the gateway chooses how to serialize values to JSON as follows:
  - If the raw stored value is a plain Python `int` or `float`, the API returns a JSON number (no quotes). Clients receive a numeric JSON value.
  - If the raw stored value is a `decimal.Decimal`, the API returns it as a JSON string (preserving the exact textual representation and scale). Example: Decimal('1.2300') -> returned as the string "1.2300". This preserves trailing zeros and formatting that an HMI may depend on.

Why this rule?
- Returning Decimal as a string preserves user-visible formatting and avoids loss of precision/scale (important for fixed-point displays). For numeric computation clients can parse the string into their Decimal representation; for simple numeric clients, the server will return numbers when the stored value was a numeric type.

## Useful REST endpoints (quick list)

- `POST /api/v1/tags` — add a tag (JSON body)
- `GET /api/v1/tags` — list tags
- `GET /api/v1/tags/{id}` — get tag metadata/value
- `PATCH /api/v1/tags/{id}` — update tag (value, metadata)
- `DELETE /api/v1/tags/{id}` — remove tag
- `GET /api/v1/hmi/data` — current data snapshot for HMI
- `GET /api/v1/hmi/ready` — readiness probe
- `GET /api/v1/hmi/health` — health details
- `POST /api/v1/hmi/stop` — graceful stop

## Tests

Run unit/integration tests from the `vs_opc` folder:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

## Troubleshooting

- If you see OPC UA type mismatch errors in non-MOCK mode, ensure PLC tag datatypes match the OPC UA node variants and that tags are configured correctly.
- Use the logs (`server.log`, `server.err`) in the `vs_opc` working directory when troubleshooting startup or poller issues.

If you'd like I can add a short `README` section into the main project README or create sample Postman/HTTPie snippets — tell me which and I'll add them.
