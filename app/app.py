"""Sample application packaged by TrustDeploy: a tiny HTTP service."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = os.environ.get("APP_VERSION", "1.0.0")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"service": "trustdeploy-sample-app", "version": VERSION, "status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
