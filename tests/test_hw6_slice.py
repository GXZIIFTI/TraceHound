from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, call

from agent.hw6_slice import fake_monitoring, query_metrics


class QueryMetricsTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "incident_id": "INC-601",
            "requester": "demo-operator",
            "owner": "Ifti Mahmood Gazi",
            "service": "api-service",
            "metric": "http_error_rate",
            "start_time": "2026-11-22T14:00:00-05:00",
            "end_time": "2026-11-22T14:15:00-05:00",
            "reason": "http_errors",
            "permission": True,
            "approved_by": "Ifti Mahmood Gazi",
            "approval": True,
        }
        self.backend = Mock(wraps=fake_monitoring)
        self.audit = Mock()

    def query(self):
        return query_metrics(self.request, audit=self.audit, backend=self.backend)

    def audit_record(self):
        self.audit.assert_called_once()
        return self.audit.call_args.args[0]

    def test_01_authorized_request_runs_fake_monitoring(self):
        result = self.query()
        self.backend.assert_called_once()
        self.assertEqual(result["status"], "ALLOWED")
        self.assertEqual(result["execution"], "succeeded")
        self.assertEqual(result["tool_attempts"], 1)
        self.assertTrue(result["observations"]["simulated"])
        self.assertEqual(result["observations"]["value"], 0.04)
        record = self.audit_record()
        self.assertEqual(record["authorization"], "ALLOWED")
        self.assertEqual(record["execution"], "succeeded")
        self.assertEqual(record["execution_identity"], "tracehound-demo-readonly")
        self.assertIsNotNone(datetime.fromisoformat(record["timestamp"]).utcoffset())
        self.assertNotIn("observations", record)

    def test_02_human_denial_skips_monitoring(self):
        self.request["approval"] = False
        result = self.query()
        self.backend.assert_not_called()
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["tool_attempts"], 0)
        record = self.audit_record()
        self.assertIs(record["approval"], False)
        self.assertEqual(record["authorization"], "REFUSED")
        self.assertEqual(record["execution"], "skipped")

    def test_03_persistent_timeout_is_retried_once(self):
        self.backend.side_effect = TimeoutError("backend details")
        result = self.query()
        expected_call = call(
            "api-service", "http_error_rate",
            datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 22, 19, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(self.backend.call_args_list, [expected_call, expected_call])
        self.assertEqual(result["status"], "TOOL_ERROR")
        self.assertEqual(result["tool_attempts"], 2)
        self.assertIsNone(result["observations"])
        record = self.audit_record()
        self.assertEqual(record["authorization"], "ALLOWED")
        self.assertEqual(record["outcome"], "TOOL_ERROR")
        self.assertEqual(record["execution"], "failed")
        self.assertEqual(record["tool_errors"], ["timeout", "timeout"])
        self.assertNotIn("backend details", str(record))

    def test_04_missing_owner_or_permission_skips_monitoring(self):
        for field in ("owner", "permission"):
            with self.subTest(missing=field):
                original = self.request.pop(field)
                self.audit.reset_mock()
                result = self.query()
                self.backend.assert_not_called()
                self.assertEqual(result["status"], "REFUSED")
                self.assertEqual(result["tool_attempts"], 0)
                self.assertEqual(self.audit_record()["authorization"], "REFUSED")
                self.request[field] = original

    def test_05_missing_service_requires_clarification(self):
        del self.request["service"]
        result = self.query()
        self.backend.assert_not_called()
        self.assertEqual(result["status"], "CLARIFICATION_REQUIRED")
        self.assertEqual(result["error"], "Specify api-service or dependency-service.")
        self.assertEqual(result["tool_attempts"], 0)
        self.assertEqual(self.audit_record()["execution"], "skipped")

    def test_06_explicit_utc_is_used_as_given(self):
        self.request["start_time"] = "2026-11-22T19:00:00Z"
        self.request["end_time"] = "2026-11-22T19:15:00+00:00"
        result = self.query()
        self.backend.assert_called_once_with(
            "api-service", "http_error_rate",
            datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 22, 19, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(result["status"], "ALLOWED")
        self.assertEqual(result["observations"]["start_time"], "2026-11-22T19:00:00+00:00")
        self.assertEqual(result["observations"]["end_time"], "2026-11-22T19:15:00+00:00")


if __name__ == "__main__":
    unittest.main()
