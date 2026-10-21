"""The probe: the smallest service that follows the convention every service follows (command-center/D32).

It listens on $PORT and answers an unauthenticated GET /version with {"commit": "<sha>"}, the commit deploy.sh
put in COMMIT_SHA. It exists so that the deploy path can be proven before any real service does
(command-center/environments C2). Standard library only.
"""

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path != "/version":
            return self.answer(404, {"error": "not found"})
        commit = os.environ.get("COMMIT_SHA", "")
        if not commit:
            # Without a commit, say so rather than answer something that looks like one.
            return self.answer(503, {"error": "COMMIT_SHA is not set"})
        return self.answer(200, {"commit": commit})

    def answer(self, status, document):
        body = json.dumps(document).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    ThreadingHTTPServer(("", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
