"""Live-site entry for applications, jobs, and admin."""

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recruitment import db
from server import Handler


class handler(Handler):
    def _path(self):
        candidates = [self.path or ""]
        for name in ("x-forwarded-uri", "x-invoke-path", "x-vercel-original-path", "x-original-uri", "x-forwarded-url"):
            value = self.headers.get(name)
            if value:
                candidates.append(value)
        chosen = self.path or "/"
        for item in candidates:
            parsed = urlparse(item)
            path = parsed.path or item
            query = parsed.query
            if not path.startswith("/"):
                continue
            if path.startswith("/api/") or path.startswith("/admin"):
                chosen = path + (("?" + query) if query else "")
                if path.startswith("/api/v1"):
                    break
        self.path = chosen

    def _run(self, method_name):
        db.prepare_request()
        self._path()
        getattr(super(), method_name)()
        db.finish_request(method_name.replace("do_", ""))

    def do_GET(self):
        self._run("do_GET")

    def do_POST(self):
        self._run("do_POST")

    def do_PATCH(self):
        self._run("do_PATCH")

    def do_DELETE(self):
        self._run("do_DELETE")
