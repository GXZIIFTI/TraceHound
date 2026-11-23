"""Run a permission-gated metric query against simulated monitoring data."""

from datetime import datetime, timedelta, timezone
import json
import re


DEMO_OPERATOR = "demo-operator"
DEMO_OWNER_AND_APPROVER = "Ifti Mahmood Gazi"
DEMO_EXECUTION_IDENTITY = "tracehound-demo-readonly"
DEMO_VALUES = {
    "api-service": {"http_error_rate": 0.04, "latency_ms": 185, "cpu_percent": 28},
    "dependency-service": {"http_error_rate": 0.01, "latency_ms": 70, "cpu_percent": 19},
}
METRICS = ("http_error_rate", "latency_ms", "cpu_percent")
REASONS = ("http_errors", "high_latency", "resource_usage", "incident_triage")
INCIDENT_ID = re.compile(r"INC-[0-9]{3,8}")
SERVICE_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-service")
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?"
    r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
MAX_WINDOW = timedelta(minutes=15)


def parse_timestamp(value):
    """Parse an explicitly zoned timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value) or value.endswith("-00:00"):
        raise ValueError("An explicit, known UTC offset is required.")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def authorize(request):
    """Return the authorization decision, message, and validated window."""
    # These identities and flags are demo fixtures. Only a named human yes opens the gate.
    if request.get("owner") != DEMO_OWNER_AND_APPROVER:
        return "REFUSED", "Supply the known monitoring owner.", None
    if request.get("requester") != DEMO_OPERATOR or request.get("permission") is not True:
        return "REFUSED", "Verified requester permission is required.", None
    if request.get("approval") is False:
        return "REFUSED", "The human approver denied the request.", None
    if request.get("approved_by") != DEMO_OWNER_AND_APPROVER or request.get("approval") is not True:
        return "REFUSED", "Explicit approval from the named human approver is required.", None

    service = request.get("service")
    if not isinstance(service, str) or not SERVICE_ID.fullmatch(service):
        return "CLARIFICATION_REQUIRED", "Specify api-service or dependency-service.", None
    if service not in DEMO_VALUES:
        return "REFUSED", "The requested service is outside the demo scope.", None
    metric = request.get("metric")
    if not isinstance(metric, str) or not metric.strip():
        return "CLARIFICATION_REQUIRED", "Specify http_error_rate, latency_ms, or cpu_percent.", None
    if metric not in METRICS:
        return "REFUSED", "The requested metric is outside the demo scope.", None
    incident_id = request.get("incident_id")
    if not isinstance(incident_id, str) or not INCIDENT_ID.fullmatch(incident_id):
        return "CLARIFICATION_REQUIRED", "Specify an incident ID such as INC-001.", None
    if request.get("reason") not in REASONS:
        return "CLARIFICATION_REQUIRED", "Specify a supported incident reason code.", None

    try:
        start = parse_timestamp(request.get("start_time"))
        end = parse_timestamp(request.get("end_time"))
    except (ValueError, OverflowError):
        return "CLARIFICATION_REQUIRED", "Supply ISO 8601 start and end times with explicit UTC offsets.", None
    if not timedelta(0) < end - start <= MAX_WINDOW:
        return "REFUSED", "The end must follow the start by at most 15 minutes.", None
    return "ALLOWED", None, (start, end)


def fake_monitoring(service, metric, start, end):
    """Read one fixed observation for the requested demo service and metric."""
    return {
        "simulated": True,
        "service": service,
        "metric": metric,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "value": DEMO_VALUES[service][metric],
    }


def query_metrics(request, *, audit, backend=fake_monitoring):
    """Gate the backend call and record every request through the supplied audit sink."""
    request = dict(request)
    decision, error, window = authorize(request)
    result = {
        "status": decision, "execution": "skipped", "tool_attempts": 0,
        "observations": None, "error": error, "tool_errors": [],
    }
    if decision == "ALLOWED":
        for attempt in (1, 2):
            result["tool_attempts"] = attempt
            try:
                result["observations"] = backend(request["service"], request["metric"], *window)
            except TimeoutError:
                result["tool_errors"].append("timeout")
                # A timeout can be transient. The same approved read gets one retry.
                if attempt == 1:
                    continue
                result.update(status="TOOL_ERROR", execution="failed", error="Monitoring timed out twice.")
            except Exception:
                # Only fixed error messages reach the result and audit record.
                result["tool_errors"].append("backend_error")
                result.update(status="TOOL_ERROR", execution="failed", error="Monitoring read failed.")
            else:
                result["execution"] = "succeeded"
            break

    # Only documented fixture identities, labels, and incident IDs may enter the audit log.
    incident_id = request.get("incident_id")
    audit({
        "event": "audit",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "simulated": True,
        "incident_id": incident_id if isinstance(incident_id, str) and INCIDENT_ID.fullmatch(incident_id) else None,
        "requester": audit_value(request, "requester", (DEMO_OPERATOR,)),
        "action": "query_metrics",
        "reason": audit_value(request, "reason", REASONS),
        "owner": audit_value(request, "owner", (DEMO_OWNER_AND_APPROVER,)),
        "approved_by": audit_value(request, "approved_by", (DEMO_OWNER_AND_APPROVER,)),
        "approval": request.get("approval") if isinstance(request.get("approval"), bool) else None,
        "service": audit_value(request, "service", tuple(DEMO_VALUES)),
        "metric": audit_value(request, "metric", METRICS),
        "execution_identity": DEMO_EXECUTION_IDENTITY if result["tool_attempts"] else None,
        "authorization": decision,
        "outcome": result["status"],
        "execution": result["execution"],
        "tool_attempts": result["tool_attempts"],
        "error": result["error"],
        "tool_errors": result["tool_errors"],
    })
    return result


def audit_value(request, field, allowed):
    value = request.get(field)
    if value is None:
        return None
    return value if isinstance(value, str) and value in allowed else "[redacted]"


def print_json(record):
    print(json.dumps(record))


def main():
    request = {
        "incident_id": "INC-601",
        "requester": DEMO_OPERATOR,
        "owner": DEMO_OWNER_AND_APPROVER,
        "service": "api-service",
        "metric": "http_error_rate",
        "start_time": "2026-11-22T14:00:00-05:00",
        "end_time": "2026-11-22T14:15:00-05:00",
        "reason": "http_errors",
        "permission": True,
        "approved_by": DEMO_OWNER_AND_APPROVER,
        "approval": True,
    }
    denied_request = {**request, "incident_id": "INC-602", "approval": False}
    for demo_request in (request, denied_request):
        result = query_metrics(demo_request, audit=print_json)
        print_json({"event": "result", "incident_id": demo_request["incident_id"], **result})


if __name__ == "__main__":
    main()
