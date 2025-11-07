# Prometheus queries and suggested Grafana panels for vs_opc metrics

This file lists example PromQL queries and simple guidance for creating Grafana panels for the metrics exported by this gateway.

Metrics available (labels: plc, ip where applicable)

- vs_opc_plc_last_backoff_seconds{plc, ip}
- vs_opc_plc_fail_count{plc, ip}
- vs_opc_plc_reconnect_total{plc, ip}
- vs_opc_plc_connected{plc, ip}
- vs_opc_poll_latency_seconds

Suggested PromQL and panels

1) PLC fail count (Gauge)
- Query: vs_opc_plc_fail_count
- Panel: Stat or Gauge per PLC (use "Group by" on `plc` or create repeated panels per `plc` variable)

2) Last backoff delay
- Query: vs_opc_plc_last_backoff_seconds
- Panel: Time series (max over time or current value). Useful to see when backoff increases during outages.

3) Total reconnect attempts (counter)
- Query: increase(vs_opc_plc_reconnect_total[5m])
- Panel: Time series showing reconnect attempts per 5-minute window.

4) Connected boolean
- Query: vs_opc_plc_connected
- Panel: Stat or Single Stat per PLC showing 1 (connected) or 0 (disconnected). Use `transform` or thresholds to color green/red.

5) Poll latency
- Query: histogram_quantile(0.95, sum(rate(vs_opc_poll_latency_seconds_bucket[5m])) by (le))
- Panel: Time series for P95 poll latency; alternative: `sum(rate(vs_opc_poll_latency_seconds_sum[5m]))/sum(rate(vs_opc_poll_latency_seconds_count[5m]))` for average.

Quick import notes for Grafana

- Create a dashboard and add a Panel for each metric query above.
- Use the `plc` label to split or repeat panels across PLCs.
- For counters, use `increase(...)` to show increments over a window.

Example small JSON snippet for a single Grafana panel (useful as a starting point when drafting a dashboard):

{
  "type": "timeseries",
  "title": "PLC Fail Count",
  "targets": [
    {
      "expr": "vs_opc_plc_fail_count",
      "legendFormat": "{{plc}} @ {{ip}}"
    }
  ]
}

You can paste queries into Grafana's query editor for Prometheus when creating panels. The labels `plc` and `ip` make it easy to filter and group metrics in dashboards.
