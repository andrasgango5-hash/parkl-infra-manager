import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app, db
from models import M2MMonthlyUsage, M2MSubscription, User
from werkzeug.security import generate_password_hash
from services.teltonika_rms import (
    TeltonikaRMSConfigurationError,
    TeltonikaRMSRequestError,
    build_rms_url,
    get_device_usage,
    get_rms_headers,
    list_rms_devices,
    normalize_rms_device,
    rms_get,
    sync_rms_devices_to_m2m,
    sync_rms_usage_to_m2m,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "rms-test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = None
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15


class TeltonikaRMSTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.subscription = M2MSubscription(
            subscriber_name="Parkl",
            sim_number="8944 1000-0001",
            phone_number="+36301234567",
            current_package="1 GB",
            status="active",
        )
        self.manager = User(
            username="manager",
            password_hash=generate_password_hash("ManagerTest123!"),
            role="manager",
            is_active=True,
            force_password_change=False,
        )
        db.session.add_all([self.subscription, self.manager])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def mobile_device(self, sent_mb=100, received_mb=50):
        return {
            "id": 321,
            "name": "Arena RUT241",
            "serial": "SER-001",
            "imei": "352000000000001",
            "iccid": "894410000001",
            "operator": "Telekom",
            "model": "RUT241",
            "online": True,
            "sent_mb": sent_mb,
            "received_mb": received_mb,
            "remaining_data": 874,
        }

    def manager_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = self.manager.id
        return client

    def test_missing_token_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                TeltonikaRMSConfigurationError,
                "TELTONIKA_RMS_API_TOKEN",
            ):
                get_rms_headers()

    def test_devices_url_uses_root_devices_endpoint(self):
        with patch.dict(
            os.environ,
            {
                "TELTONIKA_RMS_API_BASE_URL": (
                    "https://api.rms.teltonika-networks.com"
                )
            },
            clear=False,
        ):
            self.assertEqual(
                build_rms_url("/devices"),
                "https://api.rms.teltonika-networks.com/devices",
            )

    def test_rms_get_logs_url_status_and_response_without_token(self):
        class FakeResponse:
            status_code = 200
            ok = True
            text = '{"success": true, "data": [{"id": 321}]}'

            def json(self):
                return {"success": True, "data": [{"id": 321}]}

        with (
            patch.dict(
                os.environ,
                {
                    "TELTONIKA_RMS_API_TOKEN": "never-log-this-token",
                    "TELTONIKA_RMS_API_BASE_URL": (
                        "https://api.rms.teltonika-networks.com"
                    ),
                },
                clear=False,
            ),
            patch(
                "services.teltonika_rms.requests.get",
                return_value=FakeResponse(),
            ) as mocked_get,
            self.assertLogs(self.app.logger.name, level="INFO") as captured,
        ):
            payload = rms_get("/devices")

        requested_url = mocked_get.call_args.args[0]
        logs = "\n".join(captured.output)
        self.assertEqual(
            requested_url,
            "https://api.rms.teltonika-networks.com/devices",
        )
        self.assertEqual(payload["data"][0]["id"], 321)
        self.assertIn("status_code=200", logs)
        self.assertIn('"success": true', logs)
        self.assertIn("JSON keys=['data', 'success']", logs)
        self.assertNotIn("never-log-this-token", logs)

    def test_list_devices_accepts_success_data_envelope_and_logs_counts(self):
        rms_payload = {
            "success": True,
            "data": [
                self.mobile_device(),
                {
                    "id": 654,
                    "name": "Vezetékes router",
                    "serial": "WIRED-001",
                    "model": "RUTX",
                    "wan_state": "online",
                    "connection_type": "wired",
                },
            ],
        }
        with (
            patch(
                "services.teltonika_rms.rms_get",
                return_value=rms_payload,
            ),
            self.assertLogs(self.app.logger.name, level="INFO") as captured,
        ):
            devices = list_rms_devices()

        logs = "\n".join(captured.output)
        self.assertEqual(len(devices), 2)
        self.assertIn("received=2", logs)
        self.assertIn("with_iccid=1", logs)
        self.assertIn("mobile=1", logs)
        self.assertIn("wired=1", logs)

    def test_normalize_supports_real_rms_fields(self):
        normalized = normalize_rms_device(
            {
                "id": 99,
                "name": "RUT241",
                "serial": "SER-99",
                "model": "RUT241",
                "imei": "352099",
                "iccid": "8944-1000",
                "operator": "Telekom",
                "wan_state": "online",
                "sent": 12,
                "received": 34,
                "remaining_data": 56,
                "connection_type": "mobile",
            }
        )

        self.assertEqual(normalized["rms_device_id"], "99")
        self.assertEqual(normalized["online_status"], "online")
        self.assertEqual(normalized["connection_type"], "mobile")
        self.assertEqual(normalized["sent"], 12)
        self.assertEqual(normalized["received"], 34)
        self.assertEqual(normalized["remaining_data"], 56)

    def test_get_device_usage_returns_daily_sent_received_total(self):
        response = {
            "success": True,
            "data": [
                {
                    "date": "2026-06-10",
                    "modems": [
                        {
                            "modem_id": "3-1",
                            "sims": [
                                {"sim_id": 1, "data": {"rx": 100, "tx": 40}},
                                {"sim_id": 2, "data": {"rx": 20, "tx": 10}},
                            ],
                        }
                    ],
                }
            ],
        }
        with patch(
            "services.teltonika_rms.rms_get",
            return_value=response,
        ) as mocked_get:
            result = get_device_usage(321, "2026-06-10", "2026-06-11")

        mocked_get.assert_called_once_with(
            "/devices/321/data-usage",
            params={
                "start_date": "2026-06-10 00:00:00",
                "end_date": "2026-06-11 23:59:59",
                "version": "new",
            },
        )
        self.assertEqual(
            result,
            [
                {
                    "date": "2026-06-10",
                    "sent": 50,
                    "received": 120,
                    "total": 170,
                }
            ],
        )

    def test_get_device_usage_supports_legacy_daily_response(self):
        with patch(
            "services.teltonika_rms.rms_get",
            return_value={
                "success": True,
                "data": [
                    {
                        "date": "2026-06-10",
                        "sim1_rx": 100,
                        "sim2_rx": 20,
                        "sim1_tx": 40,
                        "sim2_tx": 10,
                    }
                ],
            },
        ):
            result = get_device_usage(321, "2026-06-10", "2026-06-10")

        self.assertEqual(result[0]["sent"], 50)
        self.assertEqual(result[0]["received"], 120)
        self.assertEqual(result[0]["total"], 170)

    def test_get_device_usage_splits_month_into_non_overlapping_chunks(self):
        with patch(
            "services.teltonika_rms.rms_get",
            return_value={"success": True, "data": []},
        ) as mocked_get:
            summary = get_device_usage(
                321,
                "2026-06-01",
                "2026-06-30",
                return_summary=True,
            )

        ranges = [
            (
                call.kwargs["params"]["start_date"],
                call.kwargs["params"]["end_date"],
            )
            for call in mocked_get.call_args_list
        ]
        self.assertEqual(
            ranges,
            [
                ("2026-06-01 00:00:00", "2026-06-07 23:59:59"),
                ("2026-06-08 00:00:00", "2026-06-14 23:59:59"),
                ("2026-06-15 00:00:00", "2026-06-21 23:59:59"),
                ("2026-06-22 00:00:00", "2026-06-28 23:59:59"),
                ("2026-06-29 00:00:00", "2026-06-30 23:59:59"),
            ],
        )
        self.assertEqual(summary["chunk_requests"], 5)
        self.assertEqual(summary["chunk_errors"], 0)

    def test_get_device_usage_keeps_successful_chunks_after_one_failure(self):
        responses = [
            {"success": True, "data": [{"date": "2026-06-01", "tx": 1, "rx": 2}]},
            TeltonikaRMSRequestError("Chunk hiba"),
            {"success": True, "data": [{"date": "2026-06-15", "tx": 3, "rx": 4}]},
        ]
        with patch(
            "services.teltonika_rms.rms_get",
            side_effect=responses,
        ):
            summary = get_device_usage(
                321,
                "2026-06-01",
                "2026-06-21",
                return_summary=True,
            )

        self.assertEqual(summary["chunk_requests"], 3)
        self.assertEqual(summary["chunk_errors"], 1)
        self.assertEqual(
            [item["date"] for item in summary["records"]],
            ["2026-06-01", "2026-06-15"],
        )

    def test_iccid_match_updates_subscription(self):
        result = sync_rms_devices_to_m2m([self.mobile_device()])
        db.session.commit()
        db.session.refresh(self.subscription)

        self.assertEqual(result["linked_by_iccid"], 1)
        self.assertEqual(result["mobile_updated"], 1)
        self.assertEqual(self.subscription.teltonika_rms_device_id, "321")
        self.assertEqual(self.subscription.teltonika_rms_name, "Arena RUT241")
        self.assertEqual(self.subscription.teltonika_imei, "352000000000001")
        self.assertEqual(self.subscription.teltonika_operator, "Telekom")
        self.assertEqual(self.subscription.connection_type, "mobile")

    def test_wired_device_is_skipped_for_usage(self):
        wired = {
            "id": 654,
            "name": "Vezetékes RMS eszköz",
            "serial": "WIRED-001",
            "sent_mb": 500,
            "received_mb": 500,
        }
        normalized = normalize_rms_device(wired)
        self.assertEqual(normalized["connection_type"], "wired")

        result = sync_rms_usage_to_m2m([wired])
        db.session.commit()
        self.assertEqual(result["skipped_wired_unknown"], 1)
        self.assertEqual(M2MMonthlyUsage.query.count(), 0)

    def test_invalid_device_is_reported_as_error(self):
        result = sync_rms_devices_to_m2m([{}])

        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["skipped_wired_unknown"], 0)

    def test_daily_usage_records_are_summed_for_current_month(self):
        period = datetime(2026, 6, 12, tzinfo=timezone.utc)
        with patch(
            "services.teltonika_rms.get_device_usage",
            return_value={
                "records": [
                    {
                        "date": "2026-06-01",
                        "sent": 50 * 1024 * 1024,
                        "received": 25 * 1024 * 1024,
                        "total": 75 * 1024 * 1024,
                    },
                    {
                        "date": "2026-06-02",
                        "sent": 75 * 1024 * 1024,
                        "received": 50 * 1024 * 1024,
                        "total": 125 * 1024 * 1024,
                    },
                ],
                "chunk_requests": 2,
                "chunk_errors": 0,
                "scope_errors": 0,
                "error_message": None,
            },
        ) as mocked_usage:
            result = sync_rms_usage_to_m2m(
                [self.mobile_device(sent_mb=9999, received_mb=9999)],
                sync_period=period,
            )
        db.session.commit()

        usage = M2MMonthlyUsage.query.one()
        self.assertEqual(float(usage.usage_mb), 200)
        self.assertEqual(usage.source, "teltonika_api")
        self.assertEqual(result["usage_requested"], 1)
        self.assertEqual(result["usage_created"], 1)
        mocked_usage.assert_called_once_with(
            "321",
            datetime(2026, 6, 1).date(),
            datetime(2026, 6, 12).date(),
            return_summary=True,
        )

    def test_monthly_usage_is_updated_instead_of_duplicated(self):
        period = datetime(2026, 6, 12, tzinfo=timezone.utc)
        with patch(
            "services.teltonika_rms.get_device_usage",
            return_value={
                "records": [
                    {
                        "date": "2026-06-01",
                        "sent": 100 * 1024 * 1024,
                        "received": 50 * 1024 * 1024,
                        "total": 150 * 1024 * 1024,
                    }
                ],
                "chunk_requests": 2,
                "chunk_errors": 0,
                "scope_errors": 0,
                "error_message": None,
            },
        ):
            sync_rms_usage_to_m2m(
                [self.mobile_device()],
                sync_period=period,
            )
        db.session.commit()
        with patch(
            "services.teltonika_rms.get_device_usage",
            return_value={
                "records": [
                    {
                        "date": "2026-06-01",
                        "sent": 160 * 1024 * 1024,
                        "received": 90 * 1024 * 1024,
                        "total": 250 * 1024 * 1024,
                    }
                ],
                "chunk_requests": 2,
                "chunk_errors": 0,
                "scope_errors": 0,
                "error_message": None,
            },
        ):
            result = sync_rms_usage_to_m2m(
                [self.mobile_device()],
                sync_period=period,
            )
        db.session.commit()

        self.assertEqual(M2MMonthlyUsage.query.count(), 1)
        self.assertEqual(float(M2MMonthlyUsage.query.one().usage_mb), 250)
        self.assertEqual(result["usage_updated"], 1)

    def test_device_without_data_usage_is_skipped(self):
        with patch(
            "services.teltonika_rms.get_device_usage",
            return_value={
                "records": [],
                "chunk_requests": 2,
                "chunk_errors": 0,
                "scope_errors": 0,
                "error_message": None,
            },
        ):
            result = sync_rms_usage_to_m2m([self.mobile_device()])
        db.session.commit()

        self.assertEqual(result["usage_requested"], 1)
        self.assertEqual(result["usage_no_data"], 1)
        self.assertEqual(M2MMonthlyUsage.query.count(), 0)

    def test_data_usage_403_has_scope_error_message(self):
        class ForbiddenResponse:
            status_code = 403
            ok = False
            text = '{"success": false}'

        with (
            patch.dict(
                os.environ,
                {"TELTONIKA_RMS_API_TOKEN": "test-token"},
                clear=False,
            ),
            patch(
                "services.teltonika_rms.requests.get",
                return_value=ForbiddenResponse(),
            ),
        ):
            with self.assertRaisesRegex(
                TeltonikaRMSRequestError,
                "company_device_statistics:read",
            ):
                get_device_usage(321, "2026-06-01", "2026-06-12")

    def test_usage_sync_counts_scope_error_without_stopping(self):
        with patch(
            "services.teltonika_rms.get_device_usage",
            side_effect=TeltonikaRMSRequestError(
                "Valószínűleg hiányzik a "
                "company_device_statistics:read RMS scope."
            ),
        ):
            result = sync_rms_usage_to_m2m([self.mobile_device()])
        db.session.commit()
        db.session.refresh(self.subscription)

        self.assertEqual(result["usage_requested"], 1)
        self.assertEqual(result["scope_errors"], 1)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(M2MMonthlyUsage.query.count(), 0)
        self.assertIn(
            "company_device_statistics:read",
            self.subscription.last_rms_error,
        )

    def test_usage_sync_reports_failed_chunk_counts(self):
        with patch(
            "services.teltonika_rms.get_device_usage",
            return_value={
                "records": [],
                "chunk_requests": 2,
                "chunk_errors": 2,
                "scope_errors": 2,
                "error_message": (
                    "Valószínűleg hiányzik a "
                    "company_device_statistics:read RMS scope."
                ),
            },
        ):
            result = sync_rms_usage_to_m2m([self.mobile_device()])
        db.session.commit()

        self.assertEqual(result["usage_chunk_requests"], 2)
        self.assertEqual(result["usage_chunk_errors"], 2)
        self.assertEqual(result["scope_errors"], 2)
        self.assertEqual(result["errors"], 2)
        self.assertEqual(M2MMonthlyUsage.query.count(), 0)

    def test_admin_sync_route_reports_summary(self):
        device_result = {
            "rms_devices": 5,
            "linked_by_iccid": 3,
            "mobile_updated": 3,
            "skipped_wired_unknown": 2,
            "unmatched_mobile": 0,
            "usage_created": 0,
            "usage_updated": 0,
            "usage_requested": 0,
            "usage_chunk_requests": 0,
            "usage_chunk_errors": 0,
            "usage_daily_records": 0,
            "usage_total_mb": 0,
            "usage_no_data": 0,
            "scope_errors": 0,
            "errors": 0,
        }
        usage_result = {
            **device_result,
            "usage_requested": 3,
            "usage_created": 2,
            "usage_updated": 1,
        }
        with (
            patch(
                "services.teltonika_rms.list_rms_devices",
                return_value=[self.mobile_device()],
            ),
            patch(
                "services.teltonika_rms.sync_rms_devices_to_m2m",
                return_value=device_result,
            ),
            patch(
                "services.teltonika_rms.sync_rms_usage_to_m2m",
                return_value=usage_result,
            ),
        ):
            response = self.manager_client().post(
                "/m2m/rms-sync", follow_redirects=True
            )
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("5 RMS eszköz", page)
        self.assertIn("3 ICCID kapcsolat", page)
        self.assertIn("2 wired/unknown kihagyva", page)
        self.assertIn("Havi data usage lekérés: 3 SIM", page)

    def test_sync_route_logs_rms_exception(self):
        with (
            patch(
                "services.teltonika_rms.list_rms_devices",
                side_effect=TeltonikaRMSRequestError("Teszt RMS hiba."),
            ),
            self.assertLogs(self.app.logger.name, level="ERROR") as captured,
        ):
            response = self.manager_client().post(
                "/m2m/rms-sync", follow_redirects=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Az RMS szinkron nem sikerült: Teszt RMS hiba.",
            response.get_data(as_text=True),
        )
        self.assertTrue(
            any("ismert RMS hibával leállt" in line for line in captured.output)
        )


if __name__ == "__main__":
    unittest.main()
