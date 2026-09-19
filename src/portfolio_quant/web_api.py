"""Loopback-only, read-only HTTP API for the Portfolio Quant dashboard."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from portfolio_quant.web_cycles import read_cycles
from portfolio_quant.web_rates import read_rates
from portfolio_quant.web_overview import read_overview
from portfolio_quant.web_static import read_static
from portfolio_quant.web_weather import read_weather
from portfolio_quant.web_changes import read_changes


HOST = "127.0.0.1"
PORT = 8765


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Do not write request details to logs."""
        pass

    def do_GET(self):
        if self.headers.get("Host") not in {
            f"{HOST}:{PORT}",
            f"localhost:{PORT}",
        }:
            self._respond(403, {"error": "Forbidden"})
            return

        route = urlsplit(self.path).path
        if route == "/api/overview":
            reader = read_overview
        elif route == "/api/cycles":
            reader = read_cycles
        elif route == "/api/rates":
            reader = read_rates
        elif route == "/api/weather":
            reader = read_weather
        elif route == "/api/changes":
            reader = read_changes
        else:
            try:
                content_type, body = read_static(route)
            except FileNotFoundError:
                self._respond(404, {"error": "Not found"})
                return
            except (RuntimeError, OSError):
                self._respond(503, {"error": "Dashboard unavailable"})
                return

            self._respond_static(content_type, body)
            return

        try:
            data = reader()
        except Exception:
            self._respond(503, {"error": "Overview unavailable"})
            return

        self._respond(200, data)

    def _respond_static(self, content_type: str, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _respond(self, status: int, data: dict):
        body = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Portfolio Quant API: http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
