"""Client unit tests that need no GUI or server (requests is mocked)."""
import unittest
from unittest import mock
import requests
from client.app.api import ApiClient, ApiError


def resp(status, body):
    r = mock.Mock(); r.status_code = status; r.json.return_value = body; r.headers = {}; return r


class ApiClientTests(unittest.TestCase):
    def test_error_translation_session_expired(self):
        c = ApiClient("http://x")
        c.http.request = mock.Mock(return_value=resp(401, {"success": False, "error_code": "SESSION_EXPIRED", "message": "Session expired. Please log in again."}))
        with self.assertRaises(ApiError) as cm:
            c.get("/auth/me")
        self.assertEqual(cm.exception.code, "SESSION_EXPIRED"); self.assertNotIn("401", cm.exception.message)

    def test_server_unreachable_message(self):
        c = ApiClient("http://x")
        c.http.request = mock.Mock(side_effect=requests.exceptions.ConnectionError())
        with self.assertRaises(ApiError) as cm:
            c.get("/health")
        self.assertEqual(cm.exception.code, "SERVER_UNREACHABLE")

    def test_login_stores_token_and_sends_bearer(self):
        c = ApiClient("http://x")
        c.http.request = mock.Mock(return_value=resp(200, {"token": "abc", "user": {"role": "STUDENT"}}))
        c.login("u", "p"); self.assertEqual(c.token, "abc"); self.assertEqual(c.role, "STUDENT")
        c.http.request = mock.Mock(return_value=resp(200, {}))
        c.get("/x"); self.assertEqual(c.http.request.call_args.kwargs["headers"]["Authorization"], "Bearer abc")

    def test_field_errors_preserved(self):
        c = ApiClient("http://x")
        c.http.request = mock.Mock(return_value=resp(422, {"error_code": "VALIDATION_ERROR", "message": "m", "fields": {"abstract": "Abstract is required."}}))
        with self.assertRaises(ApiError) as cm:
            c.post("/submissions/1/submit")
        self.assertEqual(cm.exception.fields["abstract"], "Abstract is required.")


if __name__ == "__main__":
    unittest.main()
