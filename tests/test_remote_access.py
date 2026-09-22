"""The private gateway must preserve backend origin and CSRF protections."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from deepanalyze.remote import PrivateProxyServer, validate_public_origin, validate_tailnet_address
from deepanalyze.server import Application, LocalServer
from tests.test_server import OfflineProvider, NoLiterature


class RemoteAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(Path(self.temp.name), OfflineProvider(), NoLiterature())
        self.backend = LocalServer(0, self.app)
        self.gateway = PrivateProxyServer(0, "https://research.example.ts.net", self.backend.server_port)
        self.threads = []
        for server in (self.backend, self.gateway):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.gateway, self.backend):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=2)
        self.app.close()
        self.temp.cleanup()

    def request(self, method="GET", headers=None, path="/api/state", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=10)
        fields = {"Host": "research.example.ts.net", **(headers or {})}
        connection.request(method, path, body, fields)
        response = connection.getresponse()
        status, payload = response.status, response.read()
        connection.close()
        return status, payload

    def test_remote_get_and_validated_origin_reach_fixed_backend(self):
        status, body = self.request(headers={"Origin": "https://research.example.ts.net"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["csrf_token"], self.app.token)
        self.assertEqual(self.request(headers={"Host": f"127.0.0.1:{self.gateway.server_port}"})[0], 200)
        self.assertEqual(self.gateway.server_address[0], "127.0.0.1")
        self.assertEqual(self.request(path="/.deepanalyze/runs")[0], 404)

    def test_unknown_hosts_cross_origin_and_spoofed_forwarding_are_rejected(self):
        for headers in (
            {"Host": "evil.example", "X-Forwarded-Host": "research.example.ts.net"},
            {"Host": "research.example.ts.net.evil.example"},
            {"Origin": "https://evil.example"},
            {"Origin": "http://research.example.ts.net"},
            {"Origin": "null"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 403)

    def test_post_still_requires_backend_csrf_token(self):
        # An unknown route gives 404 only after successful backend CSRF validation.
        headers = {"Origin": "https://research.example.ts.net", "Content-Type": "application/json"}
        self.assertEqual(self.request("POST", headers, "/api/unknown", b"{}")[0], 403)
        headers["X-DeepAnalyze-Token"] = self.app.token
        self.assertEqual(self.request("POST", headers, "/api/unknown", b"{}")[0], 404)

    def test_unsafe_framing_and_oversized_body_rejected(self):
        self.assertEqual(self.request("POST", {"Content-Length": "1000001"})[0], 413)
        self.assertEqual(self.request("POST", {"Transfer-Encoding": "chunked"})[0], 400)
        self.assertEqual(self.request(path="http://evil.example/")[0], 400)

    def test_valid_origins_are_canonicalized_and_invalid_inputs_rejected(self):
        self.assertEqual(validate_public_origin("https://Research.Example.ts.net:443/"), "https://research.example.ts.net")
        self.assertEqual(validate_public_origin("https://research.ts.net:8443"), "https://research.ts.net:8443")
        for value in (None, "", " https://research.ts.net", "http://research.ts.net",
                      "https://research.ts.net.evil.example", "https://*.ts.net",
                      "https://127.0.0.1", "https://user@research.ts.net", "https://research.ts.net/path",
                      "https://research.ts.net?q", "https://research.ts.net#x",
                      "https://-bad.ts.net", "https://bad_.ts.net", "https://research.ts.net:65536",
                      "https://research.ts.net:0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_public_origin(value)

    def test_tailnet_addresses_are_canonical_ipv4_addresses_in_tailnet_range(self):
        for value in ("100.64.0.1", "100.127.255.254"):
            with self.subTest(value=value):
                self.assertEqual(validate_tailnet_address(value), value)

        for value in (
            "0.0.0.0",
            "127.0.0.1",
            "192.168.1.10",
            "8.8.8.8",
            "2001:db8::1",
            "not-an-ip",
            "100.63.255.255",
            "100.128.0.1",
            None,
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_tailnet_address(value)

    def test_direct_tailnet_gateway_binds_validated_ip_and_derives_http_origin(self):
        assigned_port = 48765
        bind_calls = []

        def fake_init(server, address, handler, bind_and_activate=True):
            bind_calls.append((address, handler, bind_and_activate))
            server.server_address = address
            server.server_port = assigned_port

        with patch("deepanalyze.remote.ThreadingHTTPServer.__init__", new=fake_init):
            gateway = PrivateProxyServer(0, None, 8765, tailscale_ip="100.64.12.34")

        self.assertEqual(bind_calls[0][0], ("100.64.12.34", 0))
        self.assertEqual(gateway.server_address, ("100.64.12.34", 0))
        self.assertEqual(gateway.server_port, assigned_port)
        self.assertEqual(gateway.public_origin, "http://100.64.12.34:48765")

    def test_direct_tailnet_gateway_rejects_conflicting_public_origin(self):
        with self.assertRaises(ValueError):
            PrivateProxyServer(0, "https://research.example.ts.net", 8765, tailscale_ip="100.64.12.34")

if __name__ == "__main__":
    unittest.main()
