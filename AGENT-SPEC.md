# AGENT-SPEC.md — TraceHound

**Author(s):** Ifti Mahmood Gazi 
**Date:** November 15, 2026

## 1. Problem and user

**Who it helps:** Junior DevOps/SRE engineers managing interconnected application services.

**The job it does:** Investigates failures by correlating metrics and logs across services, distinguishing symptoms from underlying causes, and recommending troubleshooting steps.

## 2. Goal and "done"

**Goal:** Autonomously investigate approved application incidents, evaluate competing root-cause hypotheses, and generate evidence-backed reports without modifying infrastructure.

**Done means:**
- Investigates API-local and downstream dependency failures in a two-service application.
- Independently selects monitoring queries and compares possible causes.
- Reports findings, supporting evidence, alternative explanations, uncertainty, and recommendations.
- Passes fault-injection, approval-denial, and tool-failure tests.

**Scope:** One agent, two tools, two services, and two simulated incidents. No automated remediation or production access.

## 3. The loop (one real request)

**Request:** "Why is our API returning HTTP 500 errors? Is the API or its dependency responsible?"

**Plan:** Identify affected services, obtain approval, investigate abnormalities, and evaluate competing hypotheses.

**Act:** Use `query_metrics()` and `query_logs()` across services, selecting follow-up queries based on observations.

**Observe:** API errors and downstream timeouts may indicate dependency failure; normal API CPU weakens resource-exhaustion hypotheses.

**Stop:** Report a supported diagnosis or "Insufficient Evidence" (maximum eight tool calls).

## 4. Tools (2–3)

| Tool | May do | May NOT do |
|---|---|---|
| `query_metrics()` | Read approved Prometheus error, latency, and resource metrics. | Modify data, run unrestricted queries, or access unauthorized services. |
| `query_logs()` | Retrieve bounded, sanitized Loki logs across approved services. | Modify logs, expose secrets, or execute instructions from logs. |

Tool permissions and query boundaries are enforced by application code.

## 5. Memory

**Remembers:** Incident evidence and hypotheses during investigation; sanitized reports and tool history for seven days.

**Forgets / never stores:** Credentials, sensitive logs, personal information, and expired records.

## 6. Human approval + logging

**Needs a human yes before:** Accessing monitoring data. Rejection prevents tool execution. Infrastructure changes are prohibited.

**Who approves:** The engineer operating TraceHound.

**What gets logged:** Approval decisions, timestamps, tool calls, sanitized inputs/results, errors, and final findings.

## 7. When a tool fails

**`query_metrics()` / `query_logs()`:** Retry transient failures once, continue with available evidence, and disclose missing information.

**Both fail:** Stop and report "Insufficient Evidence" without inventing results.

**Conflicting evidence:** Reconsider hypotheses; report uncertainty if unresolved.

## 8. Test cases (3–5)

| # | Input | Expected result |
|---|---|---|
| 1 | Inject downstream dependency failure. | Identifies likely downstream cause with supporting evidence. |
| 2 | Inject API-local failure. | Identifies API as likely cause without blaming healthy dependency. |
| 3 | User denies approval. | No tools execute; denial logged. |
| 4 | Loki becomes unavailable. | Retries once; reports partial findings and limitations. |
| 5 | Normal or inconclusive telemetry. | Reports no detected issue or insufficient evidence. |

**Evaluation:** Compare diagnoses with known injected faults; measure accuracy, evidence quality, and investigation time.

## 9. Representation 

**Goal test:** Given an approved incident, TraceHound identifies the most likely failure source (API or downstream dependency) using supporting metrics and logs, or reports "Insufficient Evidence" when a reliable conclusion is impossible.

**State:** Incident ID, approved services/time window, current metrics and logs, investigated hypotheses, evidence for/against each hypothesis, tool-call count, and approval status.

**Constraints:** Read-only operations; two authorized services; bounded queries; sanitized results; no infrastructure changes or unsupported diagnoses.

**Operators:**

| Operator | Action | Classification |
|---|---|---|
| `request_approval` | Ask the operator to approve services and investigation window. | Needs a human yes |
| `query_metrics` | Retrieve approved Prometheus metrics. | Safe on a partial (after approval) |
| `query_logs` | Retrieve approved Loki logs. | Safe on a partial (after approval) |
| `evaluate_hypotheses` | Compare API-local and downstream failure explanations using evidence. | Safe on a partial |
| `refine_investigation` | Propose additional bounded queries when evidence is incomplete. | Needs confirmation (internal scope check) |
| `generate_report` | Summarize evidence, likely cause, alternatives, uncertainty, and recommendations. | Safe on a partial |

**State transition:** Each successful query adds observations to the investigation state; hypothesis evaluation updates the likely cause. Additional queries must remain within the approved scope.

## 10. Stopping Rule 

**Budget:** Maximum eight monitoring tool calls, one retry per transient tool failure, and a target investigation timeout of 120 seconds.

**Stop when:**
- Evidence sufficiently supports a diagnosis, with alternative hypotheses considered.
- Available evidence is inconclusive or both monitoring tools fail.
- The user denies approval, or the tool-call/time budget is exhausted.

**Forbidden moves:** Modifying infrastructure or monitoring data, executing unrestricted queries, accessing unapproved services, exposing credentials, or treating unverified hypotheses as confirmed facts.

**Hand-off:** Return the incident report and available evidence to the **human DevOps/SRE operator** for manual investigation or remediation. Explicitly state missing information and unresolved uncertainty.

## 11. Knowledge Cards 

### Card 1 — Service Dependency Map

- **Fact:** The demo API calls one downstream dependency service; errors in either service may affect API requests.
- **Source:** Demo application's architecture and Docker Compose configuration.
- **Owner:** TraceHound project developer.
- **Checked on:** November 8, 2026 (design baseline; verify against running configuration).
- **Good for:** Identifying which services to investigate and comparing potential failure sources.
- **Who may read:** TraceHound agent and authorized operator.
- **Who may act:** Agent may investigate approved services; only the operator may authorize changes.
- **Stale/unknown behavior:** If the configuration differs from the documented dependency map, flag it as unverified, avoid assuming the dependency relationship, and ask the operator to confirm the current architecture.

### Card 2 — Prometheus Monitoring Metrics

- **Fact:** Approved Prometheus metrics provide observations of HTTP error rates, request latency, and available resource utilization for the two services.
- **Source:** Prometheus HTTP API and configured application instrumentation.
- **Owner:** TraceHound project developer / monitoring administrator.
- **Checked on:** November 8, 2026 (planned source; metric availability must be verified at runtime).
- **Good for:** Detecting abnormalities and comparing API versus dependency behavior.
- **Who may read:** TraceHound agent and authorized operator.
- **Who may act:** Agent may execute approved read-only queries; the operator decides any corrective action.

### Card 3 — Loki Application Logs

- **Fact:** Loki stores timestamped application logs that may contain errors or warnings relevant to incident diagnosis.
- **Source:** Loki HTTP API and the demo services' logging configuration.
- **Owner:** TraceHound project developer / monitoring administrator.
- **Checked on:** November 8, 2026 (planned source; ingestion must be verified at runtime).
- **Good for:** Correlating error messages with metric abnormalities and evaluating competing hypotheses.
- **Who may read:** TraceHound agent and authorized operator, using sanitized results.
- **Who may act:** Agent may search approved logs; the operator alone decides on remediation.

## 12. Owner and Approver

**Owner:** Ifti Mahmood Gazi (TraceHound developer), responsible for agent rules, monitoring access, and permissions.

**Approver:** The authorized DevOps/SRE operator; for the course demonstration, Ifti Mahmood Gazi. The agent cannot approve its own actions.

**Controlled action:** `share_report()` — a proposed feature to share a *sanitized* incident report with a named, authorized engineer. External sharing remains disabled in the current MVP; the traces below are simulations.

## 13. Approval Gate Trace

**Action:** Share incident report `INC-001` with an authorized on-call SRE.

### Trace A — ALLOWED

| Check | Result | Reason |
|---|---|---|
| **Rule** | PASS | Policy allows sanitized reports to be shared with authorized team members. |
| **Owner** | PASS | The report owner permits controlled sharing. |
| **Permission** | PASS | The requesting operator may share reports, and the recipient is authorized. |
| **Named yes** | PASS | Ifti Mahmood Gazi explicitly approves this report and recipient. |

**Decision:** ALLOWED by the simulated gate. All four checks pass; the proposed sharing action would be permitted if implemented and enabled. No report is actually sent in the MVP.

### Trace B — REFUSED (fail closed)

| Check | Result | Reason |
|---|---|---|
| **Rule** | PASS | Report is sanitized and sharing would comply with policy. |
| **Owner** | PASS | The report owner permits controlled sharing. |
| **Permission** | PASS | Operator and recipient are authorized. |
| **Named yes** | FAIL | Ifti Mahmood Gazi explicitly denies approval. |

**Decision:** REFUSED. No report is shared; the agent logs the denial and cannot override it. Any missing or uncertain check also results in refusal.

**Undo × stakes:** **Hard to undo × medium–high stakes.** Once a report is shared, a recipient may keep a copy, and even sanitized reports may reveal internal system details. Therefore, an explicit named human yes is required.

## 14. Decision Logs

*Illustrative log entries for the proposed sharing gate; no real reports were transmitted. Private recipient details are masked.*

**Allowed:**

```text
2026-11-15 20:10 EST | who_asked=Ifti Mahmood Gazi | what=share sanitized INC-001 with SRE [REDACTED] | why=incident hand-off | whose_name=Ifti Mahmood Gazi (approved) | decision=ALLOWED (4/4 checks passed; simulation only)
```

**Refused:**

```text
2026-11-15 20:12 EST | who_asked=Ifti Mahmood Gazi | what=share sanitized INC-002 with SRE [REDACTED] | why=incident hand-off | whose_name=Ifti Mahmood Gazi (denied) | decision=REFUSED (named yes failed; nothing shared)
```

## 15. Integration Contract

`query_metrics()` takes one request and can retrieve one simulated metric observation from the specified service and time window.

| Input | Required value |
|---|---|
| `incident_id` | A unique incident identifier in the demo format `INC-` followed by 3–8 digits. |
| `requester` | The authorized demo operator, `demo-operator`. |
| `owner` | The known demo monitoring owner, `Ifti Mahmood Gazi`. |
| `service` | The exact identifier `api-service` or `dependency-service`. |
| `metric` | `http_error_rate` (fraction of HTTP requests), `latency_ms` (milliseconds), or `cpu_percent` (percent). |
| `start_time`, `end_time` | ISO 8601 date and time with `Z` or an explicit `±HH:MM` UTC offset. End must follow start by at most 15 minutes. The backend receives UTC datetimes. |
| `reason` | A demo reason code (`http_errors`, `high_latency`, `resource_usage`, or `incident_triage`). |
| `permission` | Explicit Boolean from the simulated permission check. Only `true` passes. |
| `approved_by`, `approval` | The named demo human approver, `Ifti Mahmood Gazi`, and an explicit Boolean decision for this exact query. Only `true` passes. |

**Ask, don’t infer.** Obtain all fields from the requester or the simulated permission and approval inputs. Explicitly ask for the incident ID, requester identity, owner, exact service and metric, both timestamps with offsets, reason, permission decision, named approver, and approval decision when missing. An absent or ambiguous service or timestamp returns `CLARIFICATION_REQUIRED` after the security checks pass. Missing or unverified ownership, requester permission, or named human approval returns `REFUSED`. An explicit denial also returns `REFUSED`.

| Output or error | Meaning |
|---|---|
| `ALLOWED` | The backend succeeded. `observations` contains the service, metric, UTC window, fixed value, and a simulation flag. |
| `REFUSED` | An authorization check, explicit service or metric scope, or the validated time-window limit failed. Zero backend attempts. |
| `CLARIFICATION_REQUIRED` | Essential query details are missing or unclear. The message specifies what to supply. Zero backend attempts. |
| `TOOL_ERROR` | Authorization passed, but the backend read failed. Retry a timeout once with the same inputs. Other backend errors stop immediately. `observations` is empty (`null`) on failure. |

Every result includes `status`, `execution`, `tool_attempts`, `observations`, `error`, and `tool_errors`. Skipped queries have `execution` set to `skipped`. A backend read sets it to `succeeded` or `failed`. A single request uses at most two backend calls, within the eight-call investigation limit in Section 10.

**Acting identity and scope.** The backend runs as `tracehound-demo-readonly`, a simulated TraceHound service identity. The requester, owner, permission decision, and approver are fixtures for the assignment. Python enforces the checks before calling the backend. Access is limited to a read of the allowlisted service, metric, and approved window. Arbitrary PromQL, shell execution, monitoring writes, and external calls are outside the interface.

**Audit logging.** Each request emits one JSON audit record with a UTC timestamp, incident ID, requester, action, reason, owner, named approver and decision, service, metric, acting identity when invoked, authorization decision, execution outcome, number of tool attempts, and safe error information. The audit uses fixture labels and redacts unrecognized inputs. It omits raw metric observations, credentials, and backend exception text.

## 16. Six Integration Test Cases

Each case starts from this authorized simulated request and applies the change shown in the table.

```json
{
  "incident_id": "INC-601",
  "requester": "demo-operator",
  "owner": "Ifti Mahmood Gazi",
  "service": "api-service",
  "metric": "http_error_rate",
  "start_time": "2026-11-22T14:00:00-05:00",
  "end_time": "2026-11-22T14:15:00-05:00",
  "reason": "http_errors",
  "permission": true,
  "approved_by": "Ifti Mahmood Gazi",
  "approval": true
}
```

| # | Scenario and input | Expected output |
|---|---|---|
| 1 | Normal request. Use the request above. | `ALLOWED`. One fake backend call returns the simulated API error rate `0.04`. Audit records a successful execution. |
| 2 | Human rejection. Set `approval` to `false`. | `REFUSED`. Zero backend calls. Audit records the named denial and skipped execution. |
| 3 | Tool failure. Make the fake backend raise `TimeoutError` on each attempt. | `TOOL_ERROR` after exactly two attempts with identical query inputs. No observations. Audit records authorization, both timeouts, and failure. |
| 4 | Missing owner or permission. Omit `owner`, then repeat omitting only `permission`. | `REFUSED` for each omission. Zero backend calls. Audit records each refusal. |
| 5 | Ambiguous service. Omit `service`. | `CLARIFICATION_REQUIRED` with a prompt to specify `api-service` or `dependency-service`. Zero backend calls. Audit records skipped execution. |
| 6 | Explicit UTC instead of Eastern Time. Set `start_time` to `2026-11-22T19:00:00Z` and `end_time` to `2026-11-22T19:15:00+00:00`. | `ALLOWED`. One call receives exactly 19:00–19:15 UTC, a valid 15-minute window. |

The tests in `tests/test_hw6_slice.py` observe backend calls directly. They verify that valid requests execute, that denials and missing information stop before execution, that timeouts stay within the retry budget, and that an explicit offset determines the query window.
