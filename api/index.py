"""Live-site entry for applications, jobs, and admin."""

import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recruitment import db
from server import Handler


class handler(Handler):
    def _path(self):
        candidates = []
        for name in ("x-vercel-original-path", "x-invoke-path", "x-forwarded-uri", "x-original-uri", "x-forwarded-url"):
            value = self.headers.get(name)
            if value:
                candidates.append(value)
        if self.path:
            candidates.append(self.path)

        def useful(path):
            trimmed = path.rstrip("/") or "/"
            if trimmed in ("/api/index", "/api"):
                return False
            return (
                trimmed.startswith("/api/")
                or trimmed.startswith("/admin")
                or trimmed == "/blog"
                or path.startswith("/blog/")
                or trimmed == "/sitemap.xml"
            )

        chosen = self.path or "/"
        for item in candidates:
            parsed = urlparse(item)
            path = parsed.path or "/"
            if not path.startswith("/") or not useful(path):
                continue
            chosen = path + (("?" + parsed.query) if parsed.query else "")
            break
        self.path = chosen

    def _run(self, method_name):
        db.prepare_request()
        self._path()
        getattr(super(), method_name)()
        db.finish_request(method_name.replace("do_", ""))

    def do_HEAD(self):
        self._run("do_HEAD")

    def do_GET(self):
        self._run("do_GET")

    def do_POST(self):
        self._run("do_POST")

    def do_PATCH(self):
        self._run("do_PATCH")

    def do_DELETE(self):
        self._run("do_DELETE")
