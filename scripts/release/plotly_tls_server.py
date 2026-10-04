#!/usr/bin/env python3
"""Private HTTPS status endpoint for the Plotly dependency compatibility gate."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/status":
            self.send_error(404)
            return
        body = b'{"value":{"ready":true}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    cert, key = (Path(argument) for argument in sys.argv[1:3])
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert, keyfile=key)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(server.server_address[1], flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
