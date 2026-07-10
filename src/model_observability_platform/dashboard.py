# ruff: noqa: E501
from __future__ import annotations

import html
from pathlib import Path


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def badge(value: bool) -> str:
    return f'<span class="badge {"pass" if value else "fail"}">{"PASS" if value else "FAIL"}</span>'


def severity_badge(value: str) -> str:
    klass = {"critical": "critical", "high": "high", "medium": "medium"}.get(value, "low")
    return f'<span class="sev {klass}">{esc(value.upper())}</span>'


LABELS = {
    "feature_drift": "Feature drift",
    "prediction_drift": "Prediction drift",
    "latency_slo": "Latency SLO",
    "error_rate": "Error rate",
    "null_rate": "Null rate",
    "freshness": "Freshness",
}


def observed_summary(check: dict) -> object:
    if check.get("name") == "feature_drift":
        psi_scores = check.get("observed", {}).get("psi", {})
        failed = check.get("failed_features", [])
        max_psi = max(psi_scores.values(), default=0.0)
        return f"{len(failed)} features, max PSI {max_psi:.3f}"
    return check.get("observed")


def compact_text(value: object, display: str | None = None) -> str:
    text = "" if value is None else str(value)
    label = text if display is None else display
    return f'<span class="nowrap" title="{esc(text)}">{esc(label)}</span>'


def root_cause_label(value: object, *, compact: bool = False) -> str:
    text = "" if value is None else str(value)
    readable = text.replace("_", " ")
    if text == "compound_population_shift_and_serving_degradation":
        readable = "population shift + serving degradation"
    if compact and readable == "population shift + serving degradation":
        readable = "population shift + serving"
    return compact_text(text, readable)


def root_cause_summary(value: object) -> str:
    text = "" if value is None else str(value)
    if text == "compound_population_shift_and_serving_degradation":
        return "population shift + serving degradation"
    return text.replace("_", " ")


def asset_chips(value: list[str]) -> str:
    if not value:
        return '<span class="chip muted">none</span>'
    return "".join(f'<span class="chip">{esc(asset.replace("_", " "))}</span>' for asset in value)


def rows(items: list[dict], columns: list[str]) -> str:
    if not items:
        return f"<tr><td colspan='{len(columns)}'>No records</td></tr>"
    rendered = []
    for item in items:
        cells = []
        for column in columns:
            value = item.get(column, "")
            if isinstance(value, str) and (value.startswith("<span class=") or value.startswith("<span class=\"sev")):
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rendered)


def render_dashboard(
    output_path: str | Path,
    *,
    report: dict,
    incident_summary: dict,
    reliability_plan: dict | None = None,
    runtime_contract: dict | None = None,
    notification_contract: dict | None = None,
    root_cause_evidence: dict | None = None,
    alert_routing: dict | None = None,
) -> Path:
    reliability_plan = reliability_plan or {}
    runtime_contract = runtime_contract or {}
    notification_contract = notification_contract or {}
    root_cause_evidence = root_cause_evidence or {}
    alert_routing = alert_routing or {}
    reliability_action = str(reliability_plan.get("recommended_action", "not planned")).replace("_", " ")
    impacted_assets = [str(asset) for asset in reliability_plan.get("impacted_assets", [])]
    runtime_checks = runtime_contract.get("checks", {})
    runtime_summary = runtime_contract.get("runtime", {}).get("summary", {})
    notification_checks = notification_contract.get("checks", {})
    notification_evidence = notification_contract.get("evidence", {})
    rca_evidence = root_cause_evidence.get("evidence", [])
    rca_facets = root_cause_evidence.get("lineage_facets", [])
    rca_flags = root_cause_evidence.get("feature_flag_context", [])
    alertmanager = alert_routing.get("alertmanager", {})
    alert_groups = alertmanager.get("groups", [])
    remediations = alert_routing.get("remediations", [])
    lineage_impact = alert_routing.get("lineage_impact", {})
    check_rows = [
        {
            "check": LABELS.get(check["name"], check["name"]),
            "status": badge(bool(check["passed"])),
            "severity": severity_badge(check.get("severity", "low")),
            "observed": observed_summary(check),
            "threshold": check.get("threshold", ""),
        }
        for check in report.get("checks", [])
    ]
    incident_rows = [
        {
            "incident": compact_text(incident["incident_id"], incident["incident_id"][:12]),
            "check": LABELS.get(incident["check"], incident["check"]),
            "severity": severity_badge(incident["severity"]),
            "root": root_cause_label(incident["root_cause"], compact=True),
            "status": incident["status"],
        }
        for incident in incident_summary.get("incidents", [])[-10:]
    ]
    drift_rows = [
        {
            "feature": feature.replace("_", " ").title(),
            "reference": report.get("reference_means", {}).get(feature),
            "current": report.get("current_means", {}).get(feature),
        }
        for feature in report.get("reference_means", {})
    ]
    rca_rows = [
        {
            "signal": str(item.get("signal", "")).replace("_", " "),
            "supports": root_cause_summary(item.get("supports", "")),
            "observed": item.get("observed", ""),
            "source": item.get("source", ""),
        }
        for item in rca_evidence[:6]
    ]
    body = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <title>Model Observability Incident Platform</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin:0; background:#f5f7fa; color:#1c2733; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
        header {{ background:#172026; color:white; padding:28px 36px; border-bottom:5px solid #f59e0b; }}
        main {{ max-width:1460px; margin:0 auto; padding:24px 36px 42px; }}
        h1 {{ margin:0; font-size:28px; line-height:1.2; }}
        h2 {{ margin:0 0 14px; font-size:17px; }}
        header p {{ margin:8px 0 0; color:#cbd5df; }}
        .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-bottom:18px; }}
        .metric,.panel {{ background:white; border:1px solid #d7dee7; border-radius:8px; box-shadow:0 1px 2px rgba(23,32,38,.04); }}
        .metric {{ min-height:112px; padding:16px; }}
        .metric span {{ display:block; color:#5b6b7d; font-size:13px; margin-bottom:10px; }}
        .metric strong {{ display:block; font-size:24px; line-height:1.2; overflow-wrap:anywhere; }}
        .metric .badge,.metric .sev {{ width:auto; max-width:max-content; }}
        .layout {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(380px,.43fr); gap:16px; align-items:start; }}
        .lower-grid {{ display:grid; grid-template-columns:minmax(340px,.72fr) minmax(0,1.28fr); gap:16px; align-items:start; }}
        .layout > div,.lower-grid > div,.panel {{ min-width:0; }}
        .panel {{ padding:16px; margin-top:16px; }}
        table {{ width:100%; table-layout:fixed; border-collapse:collapse; }}
        th,td {{ border-bottom:1px solid #e8edf3; padding:11px 12px; text-align:left; font-size:14px; overflow-wrap:anywhere; vertical-align:top; }}
        th {{ background:#f8fafc; color:#334155; }}
        tr:last-child td {{ border-bottom:0; }}
        .checks col:nth-child(1) {{ width:25%; }}
        .checks col:nth-child(2) {{ width:17%; }}
        .checks col:nth-child(3) {{ width:17%; }}
        .checks col:nth-child(4) {{ width:25%; }}
        .checks col:nth-child(5) {{ width:16%; }}
        .incidents col:nth-child(1) {{ width:19%; }}
        .incidents col:nth-child(2) {{ width:24%; }}
        .incidents col:nth-child(3) {{ width:17%; }}
        .incidents col:nth-child(4) {{ width:28%; }}
        .incidents col:nth-child(5) {{ width:12%; }}
        .badge,.sev {{ display:inline-block; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:800; white-space:nowrap; }}
        .pass {{ color:#166534; background:#dcfce7; }}
        .fail {{ color:#991b1b; background:#fee2e2; }}
        .critical,.high {{ color:#991b1b; background:#fee2e2; }}
        .medium {{ color:#92400e; background:#fef3c7; }}
        .low {{ color:#166534; background:#dcfce7; }}
        .chip {{ display:inline-block; margin:0 5px 5px 0; padding:4px 8px; border-radius:999px; background:#fff7ed; color:#9a3412; font-size:12px; font-weight:800; white-space:nowrap; }}
        .chip.muted {{ background:#f1f5f9; color:#475569; }}
        .facts {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:18px; }}
        .facts div {{ padding:11px 0; min-height:66px; border-bottom:1px solid #e8edf3; }}
        .facts span {{ display:block; color:#64748b; font-size:12px; margin-bottom:7px; }}
        .facts strong {{ display:block; font-size:16px; overflow-wrap:anywhere; }}
        .table-wrap {{ width:100%; max-width:100%; min-width:0; overflow-x:auto; }}
        .table-wrap table {{ min-width:680px; }}
        .nowrap {{ display:inline-block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; vertical-align:bottom; }}
        .response-lab {{ border-left:4px solid #d97706; margin:0 0 18px; }}
        .lab-heading {{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px; margin-bottom:17px; }}
        .lab-heading p {{ margin:5px 0 0; color:#64748b; font-size:13px; line-height:1.45; }}
        .api-status {{ min-width:118px; border-radius:6px; padding:9px 12px; background:#e2e8f0; color:#334155; font-size:12px; font-weight:800; text-align:center; }}
        .api-status.live {{ background:#dcfce7; color:#166534; }}
        .api-status.offline {{ background:#fee2e2; color:#991b1b; }}
        .response-grid {{ display:grid; grid-template-columns:minmax(330px,.72fr) minmax(0,1.28fr); gap:22px; align-items:start; }}
        .lab-controls {{ display:grid; gap:13px; }}
        .control-row {{ display:grid; grid-template-columns:130px minmax(0,1fr) 72px; gap:10px; align-items:center; }}
        .control-row label,.toggle-row > span {{ color:#475569; font-size:12px; font-weight:700; }}
        .control-row input {{ width:100%; accent-color:#d97706; }}
        .control-value {{ padding:6px 7px; border-radius:5px; background:#eef2f6; color:#0f172a; font-size:12px; font-weight:800; text-align:center; }}
        .toggle-row {{ display:flex; min-height:30px; align-items:center; justify-content:space-between; gap:18px; }}
        .switch {{ position:relative; display:inline-flex; align-items:center; gap:8px; cursor:pointer; }}
        .switch input {{ position:absolute; width:1px; height:1px; opacity:0; }}
        .switch-ui {{ position:relative; width:40px; height:22px; border-radius:999px; background:#cbd5e1; transition:background .15s ease; }}
        .switch-ui::after {{ content:""; position:absolute; width:16px; height:16px; left:3px; top:3px; border-radius:50%; background:white; box-shadow:0 1px 2px rgba(15,23,42,.25); transition:transform .15s ease; }}
        .switch input:checked + .switch-ui {{ background:#d97706; }}
        .switch input:checked + .switch-ui::after {{ transform:translateX(18px); }}
        .switch input:focus-visible + .switch-ui {{ outline:3px solid rgba(217,119,6,.22); outline-offset:2px; }}
        .switch-label {{ min-width:48px; color:#334155; font-size:12px; font-weight:800; text-align:right; }}
        .action-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:3px; }}
        .action {{ min-height:38px; border:1px solid #cbd5e1; border-radius:6px; padding:8px 12px; background:white; color:#334155; font:inherit; font-size:12px; font-weight:800; cursor:pointer; }}
        .action.primary {{ border-color:#b45309; background:#b45309; color:white; }}
        .action:disabled {{ cursor:wait; opacity:.55; }}
        .lab-message {{ min-height:36px; margin:1px 0 0; color:#64748b; font-size:11px; line-height:1.45; }}
        .lab-kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); border:1px solid #e4e9f0; border-radius:6px; overflow:hidden; }}
        .lab-kpis div {{ min-height:70px; padding:11px; background:#f8fafc; border-right:1px solid #e4e9f0; }}
        .lab-kpis div:last-child {{ border-right:0; }}
        .lab-kpis span {{ display:block; color:#64748b; font-size:11px; margin-bottom:7px; }}
        .lab-kpis strong {{ display:block; font-size:16px; overflow-wrap:anywhere; }}
        .freeze {{ color:#991b1b; }}
        .continue {{ color:#166534; }}
        .event-rail {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); margin:11px 0 9px; border-top:1px solid #dbe3ec; }}
        .event-step {{ min-width:0; padding:9px 8px; border-right:1px solid #e4e9f0; border-bottom:3px solid #94a3b8; }}
        .event-step:last-child {{ border-right:0; }}
        .event-step.complete {{ border-bottom-color:#16a34a; background:#f0fdf4; }}
        .event-step.alert {{ border-bottom-color:#dc2626; background:#fef2f2; }}
        .event-step.pending {{ border-bottom-color:#d97706; background:#fff7ed; }}
        .event-step span {{ display:block; color:#64748b; font-size:10px; text-transform:uppercase; margin-bottom:4px; }}
        .event-step strong {{ display:block; font-size:11px; overflow-wrap:anywhere; }}
        .live-incidents {{ display:grid; gap:6px; max-height:140px; overflow:auto; }}
        .live-incident {{ display:grid; grid-template-columns:minmax(0,1.3fr) 74px 84px auto; gap:8px; align-items:center; padding:7px 8px; border-top:1px solid #e8edf3; font-size:11px; }}
        .live-incident strong {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
        .mini-action {{ border:1px solid #cbd5e1; border-radius:5px; padding:5px 7px; background:white; color:#334155; font:inherit; font-size:10px; font-weight:800; cursor:pointer; }}
        @media (max-width:900px) {{ header {{ padding:22px 18px; }} main {{ padding:18px; }} .layout,.lower-grid,.response-grid {{ grid-template-columns:1fr; }} .facts {{ grid-template-columns:1fr; }} }}
        @media (max-width:620px) {{ .lab-heading {{ flex-direction:column; }} .api-status {{ width:100%; }} .control-row {{ grid-template-columns:106px minmax(0,1fr) 64px; }} .lab-kpis {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .lab-kpis div:nth-child(2) {{ border-right:0; }} .lab-kpis div:nth-child(-n+2) {{ border-bottom:1px solid #e4e9f0; }} .event-rail {{ grid-template-columns:1fr; }} .event-step {{ border-right:0; }} .live-incident {{ grid-template-columns:minmax(0,1fr) 70px 72px; }} .live-incident .mini-action {{ grid-column:1 / -1; }} .table-wrap table {{ min-width:0; }} th,td {{ padding:8px 7px; font-size:11px; }} .checks col:nth-child(1),.incidents col:nth-child(2) {{ width:24%; }} .checks col:nth-child(2),.checks col:nth-child(3),.incidents col:nth-child(3),.incidents col:nth-child(5) {{ width:15%; }} .checks col:nth-child(4),.incidents col:nth-child(4) {{ width:31%; }} .checks col:nth-child(5),.incidents col:nth-child(1) {{ width:15%; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>Model Observability Incident Platform</h1>
        <p>Feature drift, prediction drift, serving SLOs, idempotent incidents, likely root cause, and response guidance.</p>
      </header>
      <main>
        <section class="grid">
          <div class="metric"><span>Global health</span><strong>{badge(report.get('passed', False))}</strong></div>
          <div class="metric"><span>Generated open incidents</span><strong>{esc(incident_summary.get('open_count'))}</strong></div>
          <div class="metric"><span>Top severity</span><strong>{severity_badge(incident_summary.get('severity', 'low'))}</strong></div>
          <div class="metric"><span>Generated new incidents</span><strong>{esc(incident_summary.get('created_count'))}</strong></div>
          <div class="metric"><span>API runtime contract</span><strong>{badge(bool(runtime_contract.get('passed', False)))}</strong></div>
          <div class="metric"><span>Notification outbox</span><strong>{badge(bool(notification_contract.get('passed', False)))}</strong></div>
        </section>
        <section class="panel response-lab" data-testid="incident-response-lab">
          <div class="lab-heading">
            <div><h2>Live Incident Response Lab</h2><p>Submit bounded telemetry to the running API, inspect the durable incident transaction, and watch CloudEvents delivery recover.</p></div>
            <div id="labApiStatus" class="api-status" aria-live="polite">CONNECTING</div>
          </div>
          <div class="response-grid">
            <div class="lab-controls">
              <div class="control-row"><label for="populationShift">Population shift</label><input id="populationShift" type="range" min="0" max="100" step="5" value="100"><output id="populationShiftValue" class="control-value">100%</output></div>
              <div class="control-row"><label for="scenarioLatency">Latency p95</label><input id="scenarioLatency" type="range" min="25" max="160" step="5" value="120"><output id="scenarioLatencyValue" class="control-value">120 ms</output></div>
              <div class="control-row"><label for="scenarioErrors">Error rate</label><input id="scenarioErrors" type="range" min="0" max="10" step="2.5" value="5"><output id="scenarioErrorsValue" class="control-value">5.0%</output></div>
              <div class="toggle-row"><span id="freshWindowName">Current window fresh</span><label class="switch"><input id="freshWindow" type="checkbox" checked aria-labelledby="freshWindowName freshWindowLabel"><span class="switch-ui"></span><span id="freshWindowLabel" class="switch-label">YES</span></label></div>
              <div class="action-row">
                <button id="runIncidentScenario" class="action primary" type="button">Run evaluation</button>
                <button id="runRecovery" class="action" type="button">Send 2-window recovery</button>
              </div>
              <p id="labMessage" class="lab-message">The static evidence remains available when the API is offline.</p>
            </div>
            <div>
              <div class="lab-kpis">
                <div><span>Release decision</span><strong id="liveDecision">NO LIVE STATE</strong></div>
                <div><span>Open incidents</span><strong id="liveOpenIncidents">0</strong></div>
                <div><span>Outbox pending</span><strong id="livePendingNotifications">0</strong></div>
                <div><span>Delivered</span><strong id="liveDeliveredNotifications">0</strong></div>
              </div>
              <div class="event-rail" aria-label="Incident delivery path">
                <div class="event-step" data-live-stage="telemetry"><span>FastAPI</span><strong>Telemetry</strong></div>
                <div class="event-step" data-live-stage="checks"><span>Policy</span><strong>Six checks</strong></div>
                <div class="event-step" data-live-stage="incident"><span>SQLite WAL</span><strong>Incident tx</strong></div>
                <div class="event-step" data-live-stage="outbox"><span>CloudEvents</span><strong>Outbox</strong></div>
                <div class="event-step" data-live-stage="worker"><span>Worker</span><strong>Receipts</strong></div>
              </div>
              <div id="liveIncidents" class="live-incidents"><div class="live-incident"><strong>No live incidents</strong></div></div>
            </div>
          </div>
        </section>
        <section class="layout">
          <div>
            <div class="panel">
              <h2>Health Checks</h2>
              <div class="table-wrap"><table class="checks"><colgroup><col><col><col><col><col></colgroup><tr><th>Check</th><th>Status</th><th>Severity</th><th>Observed</th><th>Limit</th></tr>{rows(check_rows, ['check', 'status', 'severity', 'observed', 'threshold'])}</table></div>
            </div>
            <div class="panel">
              <h2>Open Incidents</h2>
              <div class="table-wrap"><table class="incidents"><colgroup><col><col><col><col><col></colgroup><tr><th>Incident</th><th>Check</th><th>Severity</th><th>Root Cause</th><th>State</th></tr>{rows(incident_rows, ['incident', 'check', 'severity', 'root', 'status'])}</table></div>
            </div>
          </div>
          <div>
            <div class="panel">
              <h2>Executable Runtime</h2>
              <div class="facts">
                <div><span>State backend</span><strong>{esc(runtime_contract.get('runtime', {}).get('state_backend', 'not exercised'))}</strong></div>
                <div><span>Durable evaluations</span><strong>{esc(runtime_summary.get('evaluation_count', 0))}</strong></div>
                <div><span>Evaluation replay</span><strong>{badge(bool(runtime_checks.get('evaluation_replay', False)))}</strong></div>
                <div><span>Lifecycle replay</span><strong>{badge(bool(runtime_checks.get('transition_replay', False)))}</strong></div>
                <div><span>Trace propagation</span><strong>{badge(bool(runtime_checks.get('stable_trace_header', False)))}</strong></div>
                <div><span>Metric cardinality</span><strong>{badge(bool(runtime_checks.get('low_cardinality_metrics', False)))}</strong></div>
                <div><span>Atomic event outbox</span><strong>{badge(bool(runtime_checks.get('transactional_outbox', False)))}</strong></div>
                <div><span>CloudEvents envelope</span><strong>{badge(bool(runtime_checks.get('cloudevents_envelope', False)))}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Notification Delivery</h2>
              <div class="facts">
                <div><span>Delivery semantics</span><strong>{esc(notification_contract.get('delivery_semantics', 'not exercised'))}</strong></div>
                <div><span>Runtime outbox rows</span><strong>{esc(runtime_summary.get('notification_count', 0))}</strong></div>
                <div><span>Receipts / injected DLQ</span><strong>{esc(notification_evidence.get('delivery_receipts', 0))} / {esc(notification_evidence.get('dead_letter_events', 0))}</strong></div>
                <div><span>Lease takeover</span><strong>{badge(bool(notification_checks.get('lease_takeover', False)))}</strong></div>
                <div><span>Stale worker fencing</span><strong>{badge(bool(notification_checks.get('stale_worker_rejected', False)))}</strong></div>
                <div><span>Per-incident ordering</span><strong>{badge(bool(notification_checks.get('ordered_delivery', False)))}</strong></div>
                <div><span>Dead-letter path</span><strong>{badge(bool(notification_checks.get('dead_letter_terminal_state', False)))}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Alert Routing And Remediation</h2>
              <div class="facts">
                <div><span>Routing readiness</span><strong>{badge(bool(alert_routing.get('passed', False)))}</strong></div>
                <div><span>Alert groups</span><strong>{esc(len(alert_groups))}</strong></div>
                <div><span>Inhibited alerts</span><strong>{esc(len(alertmanager.get('inhibited_alerts', [])))}</strong></div>
                <div><span>Human approval gates</span><strong>{esc(sum(1 for item in remediations if item.get('requires_human')))}</strong></div>
                <div><span>Lineage facet</span><strong>{compact_text(lineage_impact.get('facet', 'not planned'))}</strong></div>
                <div><span>Impacted assets</span><strong>{asset_chips(lineage_impact.get('impacted_assets', []))}</strong></div>
              </div>
            </div>
          </div>
        </section>
        <section class="lower-grid">
          <div>
            <div class="panel">
              <h2>Reliability Control Plane</h2>
              <div class="facts">
                <div><span>Recommended action</span><strong>{esc(reliability_action)}</strong></div>
                <div><span>Error burn rate</span><strong>{esc(reliability_plan.get('error_budget_burn_rate', 'n/a'))}</strong></div>
                <div><span>Owner</span><strong>{esc(reliability_plan.get('routing', {}).get('owner', 'n/a'))}</strong></div>
                <div><span>Impacted assets</span><strong>{asset_chips(impacted_assets)}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Root Cause Summary</h2>
              <div class="facts">
                <div><span>Primary root cause</span><strong>{esc(root_cause_summary(incident_summary.get('incidents', [{}])[-1].get('root_cause', 'none')))}</strong></div>
                <div><span>Incident status</span><strong>{esc('open' if incident_summary.get('open_count', 0) else 'clear')}</strong></div>
              </div>
            </div>
            <div class="panel">
              <h2>Root Cause Evidence</h2>
              <div class="facts">
                <div><span>Evidence gate</span><strong>{badge(bool(root_cause_evidence.get('passed', False)))}</strong></div>
                <div><span>Confidence</span><strong>{esc(root_cause_evidence.get('confidence', 'n/a'))}</strong></div>
                <div><span>Lineage facets</span><strong>{esc(len(rca_facets))}</strong></div>
                <div><span>Feature flags</span><strong>{esc(len(rca_flags))}</strong></div>
              </div>
              <div class="table-wrap"><table><tr><th>Signal</th><th>Supports</th><th>Observed</th><th>Source</th></tr>{rows(rca_rows, ['signal', 'supports', 'observed', 'source'])}</table></div>
            </div>
          </div>
          <div>
            <div class="panel">
              <h2>Feature Means</h2>
              <div class="table-wrap"><table><tr><th>Feature</th><th>Reference</th><th>Current</th></tr>{rows(drift_rows, ['feature', 'reference', 'current'])}</table></div>
            </div>
          </div>
        </section>
      </main>
      <script>
        const labById = (id) => document.getElementById(id);
        const modelVersion = "risk-model-2026-07-15";
        let labSequence = 0;
        let lastEvaluation = null;
        let liveRefreshTimer = null;

        function clamp(value, low, high) {{
          return Math.min(Math.max(value, low), high);
        }}

        function baseTelemetry(windowName, index, timestamp) {{
          const age = 38 + ((index * 7) % 11);
          const income = 65000 + ((index * 7919) % 23000);
          const debtRatio = 0.28 + ((index * 13) % 18) / 100;
          const utilization = 0.32 + ((index * 17) % 22) / 100;
          const delinquencies = index % 5 === 0 ? 1 : 0;
          const riskScore = clamp(0.08 + debtRatio * 0.34 + utilization * 0.28 + delinquencies * 0.09 - income / 500000, 0, 0.99);
          return {{
            timestamp,
            window: windowName,
            request_id: windowName + "_ui_" + labSequence + "_" + String(index).padStart(3, "0"),
            model_version: modelVersion,
            status: "success",
            latency_ms: 31 + (index % 7),
            prediction: riskScore >= 0.65 ? 1 : 0,
            risk_score: Number(riskScore.toFixed(6)),
            age,
            income: Number(income.toFixed(2)),
            debt_ratio: Number(debtRatio.toFixed(4)),
            utilization: Number(utilization.toFixed(4)),
            delinquencies,
          }};
        }}

        function buildEvaluation(overrides = null) {{
          labSequence += 1;
          const shift = overrides ? overrides.shift : Number(labById("populationShift").value) / 100;
          const latencyTarget = overrides ? overrides.latency : Number(labById("scenarioLatency").value);
          const errorRate = overrides ? overrides.errors : Number(labById("scenarioErrors").value) / 100;
          const fresh = overrides ? overrides.fresh : labById("freshWindow").checked;
          const now = Date.now();
          const reference = Array.from({{length: 40}}, (_, index) => baseTelemetry("reference", index, new Date(now - 86400000 + index * 8000).toISOString()));
          const errorCount = Math.round(errorRate * 40);
          const current = Array.from({{length: 40}}, (_, index) => {{
            const record = baseTelemetry("current", index, new Date(now - (fresh ? 0 : 3600000) - (39 - index) * 8000).toISOString());
            record.age = Math.max(18, Math.round(record.age - shift * 7));
            record.income = Number(Math.max(22000, record.income - shift * 18000).toFixed(2));
            record.debt_ratio = Number(clamp(record.debt_ratio + shift * 0.25, 0.02, 1.7).toFixed(4));
            record.utilization = Number(clamp(record.utilization + shift * 0.30, 0, 1.4).toFixed(4));
            record.delinquencies += Math.round(shift * 1.5);
            const score = clamp(0.08 + record.debt_ratio * 0.34 + record.utilization * 0.28 + record.delinquencies * 0.09 - record.income / 500000 + shift * 0.12, 0, 0.99);
            record.risk_score = Number(score.toFixed(6));
            record.prediction = score >= 0.65 ? 1 : 0;
            record.status = index < errorCount ? "error" : "success";
            record.latency_ms = Number((latencyTarget * (0.72 + ((index * 19) % 28) / 100)).toFixed(3));
            return record;
          }});
          return {{
            evaluation_id: "ui-eval-" + Date.now() + "-" + labSequence,
            model_name: "credit-risk-router",
            model_version: modelVersion,
            policy_version: "2026.07",
            reference_window: reference,
            current_window: current,
          }};
        }}

        async function apiJson(path, options = undefined) {{
          const response = await fetch(path, options);
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || payload.detail || "API request failed");
          return payload;
        }}

        function setStage(name, state) {{
          const stage = document.querySelector('[data-live-stage="' + name + '"]');
          if (stage) stage.className = "event-step " + state;
        }}

        function renderIncidentRows(incidents) {{
          const container = labById("liveIncidents");
          container.replaceChildren();
          if (!incidents.length) {{
            const row = document.createElement("div");
            row.className = "live-incident";
            const label = document.createElement("strong");
            label.textContent = "No live incidents";
            row.appendChild(label);
            container.appendChild(row);
            return;
          }}
          incidents.slice(0, 4).forEach((incident) => {{
            const row = document.createElement("div");
            row.className = "live-incident";
            const check = document.createElement("strong");
            check.textContent = (incident.check || "unknown").replaceAll("_", " ");
            check.title = incident.root_cause || "";
            const severity = document.createElement("span");
            severity.className = "sev " + incident.severity;
            severity.textContent = incident.severity.toUpperCase();
            const status = document.createElement("span");
            status.textContent = incident.status;
            row.append(check, severity, status);
            if (incident.status === "open") {{
              const button = document.createElement("button");
              button.type = "button";
              button.className = "mini-action";
              button.textContent = "Acknowledge";
              button.addEventListener("click", () => acknowledgeIncident(incident));
              row.appendChild(button);
            }}
            container.appendChild(row);
          }});
        }}

        async function refreshLiveState() {{
          try {{
            const [runtime, incidentResult, notificationResult] = await Promise.all([
              apiJson("/v1/runtime"),
              apiJson("/v1/incidents?limit=20"),
              apiJson("/v1/notifications?limit=100"),
            ]);
            const summary = runtime.summary;
            const notifications = summary.notifications_by_status;
            labById("labApiStatus").className = "api-status live";
            labById("labApiStatus").textContent = "API LIVE";
            labById("liveOpenIncidents").textContent = summary.open_count;
            labById("livePendingNotifications").textContent = notifications.pending + notifications.in_flight;
            labById("liveDeliveredNotifications").textContent = notifications.delivered;
            const frozen = lastEvaluation ? Boolean(lastEvaluation.decision?.release_frozen) : summary.open_count > 0;
            const decision = labById("liveDecision");
            decision.textContent = frozen ? "FREEZE RELEASE" : "CONTINUE";
            decision.className = frozen ? "freeze" : "continue";
            setStage("telemetry", "complete");
            setStage("checks", lastEvaluation && !lastEvaluation.passed ? "alert" : "complete");
            setStage("incident", summary.incident_count > 0 ? "complete" : "pending");
            setStage("outbox", summary.notification_count > 0 ? "complete" : "pending");
            setStage("worker", notifications.pending + notifications.in_flight > 0 ? "pending" : notifications.delivered > 0 ? "complete" : "pending");
            renderIncidentRows(incidentResult.incidents);
            return {{runtime, incidentResult, notificationResult}};
          }} catch (error) {{
            labById("labApiStatus").className = "api-status offline";
            labById("labApiStatus").textContent = "API OFFLINE";
            labById("labMessage").textContent = "Start make api-run to execute the live incident workflow. " + error.message;
            ["telemetry", "checks", "incident", "outbox", "worker"].forEach((name) => setStage(name, "pending"));
            return null;
          }}
        }}

        function setBusy(busy) {{
          labById("runIncidentScenario").disabled = busy;
          labById("runRecovery").disabled = busy;
        }}

        async function submitEvaluation(payload) {{
          return apiJson("/v1/evaluations", {{
            method: "POST",
            headers: {{"Content-Type": "application/json", "X-Request-ID": payload.evaluation_id}},
            body: JSON.stringify(payload),
          }});
        }}

        async function runScenario() {{
          setBusy(true);
          labById("labMessage").textContent = "Evaluating telemetry and committing incident changes...";
          try {{
            lastEvaluation = await submitEvaluation(buildEvaluation());
            const failed = lastEvaluation.failed_checks || [];
            labById("labMessage").textContent = lastEvaluation.passed
              ? "Healthy window recorded. Recovery requires two consecutive healthy windows."
              : failed.length + " checks failed; incident events and CloudEvents committed atomically.";
            await refreshLiveState();
          }} catch (error) {{
            labById("labMessage").textContent = error.message;
          }} finally {{
            setBusy(false);
          }}
        }}

        async function runRecovery() {{
          setBusy(true);
          labById("labMessage").textContent = "Sending the first healthy recovery window...";
          try {{
            const healthy = {{shift: 0, latency: 35, errors: 0, fresh: true}};
            await submitEvaluation(buildEvaluation(healthy));
            labById("labMessage").textContent = "First window accepted; sending the hysteresis confirmation...";
            lastEvaluation = await submitEvaluation(buildEvaluation(healthy));
            labById("labMessage").textContent = "Two healthy windows recorded. Active incidents auto-resolved with recovery evidence.";
            await refreshLiveState();
          }} catch (error) {{
            labById("labMessage").textContent = error.message;
          }} finally {{
            setBusy(false);
          }}
        }}

        async function acknowledgeIncident(incident) {{
          try {{
            await apiJson("/v1/incidents/" + incident.incident_id + "/acknowledge", {{
              method: "POST",
              headers: {{"Content-Type": "application/json"}},
              body: JSON.stringify({{
                transition_id: "ui-ack-" + Date.now(),
                expected_version: incident.version,
                actor: "judge-demo",
                note: "Acknowledged from the operator console",
              }}),
            }});
            labById("labMessage").textContent = "Incident acknowledged; the lifecycle CloudEvent is now in the delivery stream.";
            await refreshLiveState();
          }} catch (error) {{
            labById("labMessage").textContent = error.message;
          }}
        }}

        function renderControlValues() {{
          labById("populationShiftValue").textContent = labById("populationShift").value + "%";
          labById("scenarioLatencyValue").textContent = labById("scenarioLatency").value + " ms";
          labById("scenarioErrorsValue").textContent = Number(labById("scenarioErrors").value).toFixed(1) + "%";
          labById("freshWindowLabel").textContent = labById("freshWindow").checked ? "YES" : "NO";
        }}

        ["populationShift", "scenarioLatency", "scenarioErrors", "freshWindow"].forEach((id) => labById(id).addEventListener("input", renderControlValues));
        labById("runIncidentScenario").addEventListener("click", runScenario);
        labById("runRecovery").addEventListener("click", runRecovery);
        renderControlValues();
        refreshLiveState();
        liveRefreshTimer = window.setInterval(refreshLiveState, 2500);
        window.addEventListener("beforeunload", () => window.clearInterval(liveRefreshTimer));
      </script>
    </body>
    </html>
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body, encoding="utf-8")
    return output_path
