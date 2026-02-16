# SLO Definitions — Trade Nexus Backend

> Alpha-stage targets for a scale-to-zero Azure Container Apps deployment.
> These SLOs will tighten as the system matures toward GA.

## Service Context

| Property | Value |
|----------|-------|
| Service | trade-nexus-backend |
| Platform | Azure Container Apps |
| Region | West Europe |
| Scaling | 0–5 replicas (scale-to-zero enabled) |
| Measurement Window | 7-day rolling |

## SLO Targets

### SLO-1: Availability

- **Target**: 99.0% (7-day rolling)
- **Measurement**: Synthetic `GET /health` probe every 5 minutes
- **Calculation**: `(successful_probes / total_probes) * 100`
- **Excludes**: Planned maintenance windows, scale-from-zero cold starts (first probe after idle)
- **Breach response**: Page on-call if < 98% over 1-hour window

### SLO-2: Warm Response Latency

- **Target**: p95 < 500ms
- **Measurement**: `GET /health` and `GET /v1/health` response times when container is warm
- **Tool**: `smoke-check.sh` warm-request timings
- **Excludes**: First request after scale-from-zero (cold start)
- **Breach response**: Investigate if p95 > 500ms over 15-minute window

### SLO-3: Cold-Start Latency

- **Target**: p95 < 45 seconds
- **Measurement**: Time from first request to 200 OK after scale-from-zero
- **Tool**: `smoke-check.sh` cold-start detection
- **Note**: Azure Container Apps cold starts include image pull + app initialization
- **Breach response**: Review container image size, startup dependencies

### SLO-4: Error Rate

- **Target**: < 5% 5xx responses per hour (excluding cold-start timeouts)
- **Measurement**: Azure Log Analytics query:
  ```kql
  ContainerAppConsoleLogs_CL
  | where RevisionName_s startswith "trade-nexus-backend"
  | where StatusCode_d >= 500
  | summarize errors=count() by bin(TimeGenerated, 1h)
  ```
- **Breach response**: Check application logs, recent deployments

### SLO-5: Rollback Time

- **Target**: < 5 minutes (from trigger to healthy on previous revision)
- **Measurement**: `rollback.sh` execution timer
- **Includes**: Revision activation + traffic shift + smoke check
- **Breach response**: Review rollback procedure, pre-warm previous revision

## SLO Status Tracking

| SLO | Target | Current Status | Last Measured |
|-----|--------|---------------|---------------|
| Availability | 99.0% | TBD | — |
| Warm Latency | p95 < 500ms | TBD | — |
| Cold-Start Latency | p95 < 45s | TBD | — |
| Error Rate | < 5% 5xx/hr | TBD | — |
| Rollback Time | < 5 min | TBD | — |

## Review Cadence

- **Weekly**: Review SLO dashboards, update status table
- **Monthly**: Evaluate if targets need adjustment
- **Post-incident**: Update SLOs if breach reveals unrealistic targets
