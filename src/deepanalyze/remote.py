"""Private Tailscale Serve gateway for an already running loopback application."""
from __future__ import annotations

import argparse
import http.client
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 1_000_000


def validate_public_origin(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("Use a complete HTTPS Tailscale origin.")
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    labels = hostname.split(".")
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
            or not hostname.endswith(".ts.net") or len(labels) < 3 or len(hostname) > 253
            or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label) for label in labels)
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or "?" in value or "#" in value or "\\" in value):
        raise ValueError("Use only an HTTPS *.ts.net origin, without a path or credentials.")
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid HTTPS port.")
    return "https://" + hostname.lower() + (f":{port}" if port and port != 443 else "")


class PrivateProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, public_origin, backend_port):
        self.public_origin = validate_public_origin(public_origin)
        if not isinstance(backend_port, int) or not 1 <= backend_port <= 65535:
            raise ValueError("Invalid local backend port.")
        self.backend_port = backend_port
        super().__init__(("127.0.0.1", port), PrivateProxyHandler)


class PrivateProxyHandler(BaseHTTPRequestHandler):
    server_version = "DeepAnalyze"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _error(self, status, message):
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _forward(self):
        origin = self.server.public_origin
        port = self.server.server_port
        local_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        allowed_hosts = local_hosts | {urlsplit(origin).netloc}
        allowed_origins = {origin} | {"http://" + host for host in local_hosts}
        if (len(self.headers.get_all("Host", [])) != 1
                or self.headers.get("Host", "").lower() not in allowed_hosts):
            return self._error(403, "This gateway only accepts its configured host.")
        if len(self.headers.get_all("Origin", [])) > 1:
            return self._error(403, "Multiple origins are not allowed.")
        supplied_origin = self.headers.get("Origin")
        if supplied_origin and supplied_origin.lower() not in allowed_origins:
            return self._error(403, "Cross-origin requests are not allowed.")
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return self._error(403, "Cross-site requests are not allowed.")
        if not self.path.startswith("/") or self.path.startswith("//"):
            return self._error(400, "Only application-relative paths are allowed.")
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) > 1:
            return self._error(400, "Unsupported request framing.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._error(400, "Invalid request length.")
        if not 0 <= length <= MAX_BODY:
            return self._error(413, "Request body is too large.")
        self.connection.settimeout(15)
        try:
            body = self.rfile.read(length) if length else None
            if body is not None and len(body) != length:
                return self._error(400, "Incomplete request body.")
        except TimeoutError:
            return self._error(408, "Request body timed out.")
        # Rewrite only after validating the browser's actual Host and Origin.
        # The backend still validates its own CSRF token for every mutation.
        backend_host = f"127.0.0.1:{self.server.backend_port}"
        headers = {"Host": backend_host}
        for name in ("Content-Type", "X-DeepAnalyze-Token", "Sec-Fetch-Site", "Accept"):
            if self.headers.get(name):
                headers[name] = self.headers[name]
        if supplied_origin:
            headers["Origin"] = "http://" + backend_host
        backend = http.client.HTTPConnection("127.0.0.1", self.server.backend_port, timeout=60)
        try:
            backend.request(self.command, self.path, body=body, headers=headers)
            response = backend.getresponse()
            payload = response.read()
            self.send_response(response.status)
            excluded = {"connection", "keep-alive", "transfer-encoding", "content-length", "server", "date"}
            for name, value in response.getheaders():
                if name.lower() not in excluded:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, http.client.HTTPException):
            # No backend details, credentials or request bodies enter the logs.
            self._error(502, "The local research service is unavailable.")
        finally:
            backend.close()

    do_GET = _forward
    do_POST = _forward


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--backend-port", type=int, default=8765)
    parser.add_argument("--public-origin", required=True)
    args = parser.parse_args(argv)
    try:
        server = PrivateProxyServer(args.port, args.public_origin, args.backend_port)
    except (ValueError, OSError):
        parser.exit(1, "Cannot start private gateway. Check the HTTPS Tailscale origin and local ports.\n")
    print(f"Private gateway listening on 127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
