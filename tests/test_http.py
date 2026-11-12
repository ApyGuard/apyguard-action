from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from apyguard_action.http import HttpError, request_json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        received = json.loads(self.rfile.read(length) or b"null")
        if self.path == "/broken":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"database is down")
            return
        payload = json.dumps({"echo": received, "token": self.headers.get("X-Token")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


class RequestJsonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_sends_json_and_parses_the_reply(self) -> None:
        reply = request_json("POST", f"{self.base}/ok", {"X-Token": "secret"}, {"a": 1})

        self.assertEqual(reply, {"echo": {"a": 1}, "token": "secret"})

    def test_error_status_names_the_status_and_body_but_not_the_token(self) -> None:
        with self.assertRaises(HttpError) as raised:
            request_json("POST", f"{self.base}/broken", {"X-Token": "secret"}, {})

        self.assertEqual(raised.exception.status, 500)
        self.assertIn("database is down", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
