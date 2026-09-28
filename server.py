#!/usr/bin/env python3
"""Serve the static site and the recruitment API on port 8080."""

import json
import mimetypes
import os
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from recruitment import api, db, documents

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "recruitment", "web")
PORT = int(os.environ.get("PORT", "8080"))

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

PAGES = {
    "/careers": "careers.html",
    "/jobs": "careers.html",
    "/apply": "apply.html",
}


def cookie_token(header):
    if not header:
        return ""
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "mcc_admin":
            return value
    return ""


class Handler(BaseHTTPRequestHandler):
    server_version = "MCCRecruitment/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status, body, content_type, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, text):
        self.send_bytes(200, text.encode("utf-8"), "text/html; charset=utf-8")

    def careers_page(self):
        conn = db.connect()
        try:
            jobs = db.list_public_jobs(conn)
        finally:
            conn.close()
        if not jobs:
            cards = '<div class="empty"><h2>No Open Positions Right Now</h2><p>We don\'t currently have any positions available. Please check back again soon.</p></div>'
        else:
            cards = "".join(self.job_card(job) for job in jobs)
        with open(os.path.join(WEB, "careers.html"), encoding="utf-8") as handle:
            return handle.read().replace("<!--JOBS-->", cards)

    def job_card(self, job):
        chips = "".join(
            '<span class="chip">%s</span>' % self.esc(part)
            for part in (job.get("location"), job.get("employment_type_label"), job.get("shift"), job.get("pay"))
            if part
        )
        return (
            '<article class="job-card"><div class="card-top"><h2>%s</h2></div><div class="meta">%s</div><p>%s</p>'
            '<p class="help">Posted %s</p><a class="btn" href="/jobs/%s">View Job</a></article>'
        ) % (
            self.esc(job.get("title")),
            chips,
            self.esc(job.get("summary")),
            self.esc(job.get("posted_at")),
            self.esc(job.get("job_id")),
        )

    def job_page(self, job_id):
        conn = db.connect()
        try:
            job = db.get_public_job(conn, job_id)
        finally:
            conn.close()
        with open(os.path.join(WEB, "job.html"), encoding="utf-8") as handle:
            html = handle.read()
        if not job:
            block = '<div class="empty"><h1>This position is no longer available.</h1><p>It may have been filled or closed.</p><a class="btn" href="/careers">View Current Opportunities</a></div>'
            return html.replace("<title>Job | Master Commercial Cleaning</title>", "<title>Position unavailable | Master Commercial Cleaning</title>").replace('<div class="wrap" id="job"></div>', '<div class="wrap" id="job">%s</div>' % block)
        chips = "".join(
            '<span class="chip">%s</span>' % self.esc(part)
            for part in (
                ("%s, %s" % (job["city"], job["province"])) if job.get("city") else job.get("location"),
                job.get("employment_type_label"),
                job.get("shift"),
                job.get("pay"),
            )
            if part
        )
        apply_btn = '<a class="btn" href="/apply?job=%s">Apply Now</a>' % self.esc(job["job_id"]) if job.get("accepting_applications") else "<p>Applications are closed for this position.</p>"
        block = (
            '<div class="detail-grid"><article><span class="eyebrow">%s</span><h1>%s</h1><div class="meta">%s</div>'
            '<h2>Job description</h2><div class="prose">%s</div><h2>Requirements</h2><div class="prose">%s</div></article>'
            '<aside class="panel"><h2>This role</h2><p><strong>Location</strong><br>%s</p>'
            '<p><strong>Employment type</strong><br>%s</p><p><strong>Schedule</strong><br>%s</p>%s%s</aside></div>'
        ) % (
            self.esc(job["job_id"]),
            self.esc(job["title"]),
            chips,
            self.esc(job.get("description")),
            self.esc(job.get("requirements")),
            self.esc(job.get("location")),
            self.esc(job.get("employment_type_label")),
            self.esc(job.get("shift") or "See description"),
            ("<p><strong>Start date</strong><br>%s</p>" % self.esc(job["start_date"])) if job.get("start_date") else "",
            apply_btn,
        )
        html = html.replace("<title>Job | Master Commercial Cleaning</title>", "<title>%s | Master Commercial Cleaning</title>" % self.esc(job["title"]))
        return html.replace('<div class="wrap" id="job"></div>', '<div class="wrap" id="job">%s</div>' % block)

    def esc(self, value):
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def send_file(self, path, content_type=None, download_name=None, inline=False):
        if not os.path.isfile(path):
            self.send_json(404, {"error": "Not found"})
            return
        with open(path, "rb") as handle:
            body = handle.read()
        ext = os.path.splitext(path)[1].lower()
        ctype = content_type or STATIC_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        headers = []
        if download_name:
            headers.append(("Content-Disposition", f'inline; filename="{download_name}"' if inline else f'attachment; filename="{download_name}"'))
        self.send_bytes(200, body, ctype, headers)

    def read_body(self, limit=12 * 1024 * 1024):
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > limit:
            return None
        return self.rfile.read(length) if length else b""

    def require_admin(self):
        conn = db.connect()
        try:
            user = api.session_user(conn, cookie_token(self.headers.get("Cookie")))
            if not user:
                return None
            return user["id"], user["username"]
        finally:
            conn.close()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            self.route_api("GET", path, query, None)
            return
        self.route_page(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/api/"):
            limit = 40 * 1024 * 1024 if path.rstrip("/") == "/api/v1/quotes" else 12 * 1024 * 1024
            raw = self.read_body(limit)
            if raw is None:
                self.send_json(413, {"error": "Upload is too large."})
                return
            self.route_api("POST", path, parse_qs(parsed.query), raw)
            return
        self.send_json(404, {"error": "Not found"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        raw = self.read_body(1024 * 1024)
        if raw is None:
            self.send_json(413, {"error": "Request is too large."})
            return
        self.route_api("PATCH", path, parse_qs(parsed.query), raw)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        self.route_api("DELETE", parsed.path.rstrip("/") or "/", {}, None)

    def route_page(self, path):
        if path in ("/careers", "/careers.html", "/jobs"):
            self.send_html(self.careers_page())
            return
        if path in PAGES:
            self.send_file(os.path.join(WEB, PAGES[path]))
            return
        if path.startswith("/application/documents/request/"):
            self.send_file(os.path.join(WEB, "document-request.html"))
            return
        job_page = re.fullmatch(r"/jobs/(JOB-\d+)", path)
        if job_page:
            self.send_html(self.job_page(job_page.group(1)))
            return
        if path == "/admin" or path.startswith("/admin/"):
            self.send_file(os.path.join(WEB, "admin.html"))
            return
        if path.startswith("/recruitment-assets/"):
            rel = path[len("/recruitment-assets/"):]
            target = os.path.normpath(os.path.join(WEB, rel))
            if not target.startswith(WEB):
                self.send_json(403, {"error": "Forbidden"})
                return
            self.send_file(target)
            return
        if path == "/":
            self.send_file(os.path.join(ROOT, "index.html"))
            return
        rel = path.lstrip("/")
        target = os.path.normpath(os.path.join(ROOT, rel))
        blocked = ("data", "recruitment", ".git")
        if not target.startswith(ROOT) or rel.split("/")[0] in blocked:
            self.send_json(403, {"error": "Forbidden"})
            return
        if os.path.isdir(target):
            self.send_json(404, {"error": "Not found"})
            return
        if not os.path.isfile(target):
            self.send_json(404, {"error": "Not found"})
            return
        self.send_file(target)

    def route_api(self, method, path, query, raw):
        prefix = "/api/v1"
        if not path.startswith(prefix):
            self.send_json(404, {"error": "Not found"})
            return
        route = path[len(prefix):] or "/"
        one = query.get
        if method == "GET" and route == "/jobs":
            conn = db.connect()
            try:
                jobs = db.list_public_jobs(conn, one("location", [None])[0], one("type", [None])[0])
            finally:
                conn.close()
            self.send_json(200, {"jobs": jobs})
            return
        match = re.fullmatch(r"/jobs/(JOB-\d+)", route)
        if method == "GET" and match:
            conn = db.connect()
            try:
                job = db.get_public_job(conn, match.group(1))
            finally:
                conn.close()
            if not job:
                self.send_json(404, {"error": "This position is no longer available."})
                return
            self.send_json(200, {"job": job})
            return
        if method == "POST" and match and route.endswith("/view") is False:
            pass
        view = re.fullmatch(r"/jobs/(JOB-\d+)/view", route)
        if method == "POST" and view:
            conn = db.connect()
            try:
                ok = db.record_view(conn, view.group(1))
            finally:
                conn.close()
            self.send_json(200 if ok else 404, {"ok": ok})
            return
        if method == "GET" and route == "/locations":
            self.send_json(200, {"locations": api.list_locations(active_only=True)})
            return
        if method == "POST" and route == "/applications":
            data, files, error = self.parse_application(raw)
            if error:
                self.send_json(400, {"error": error})
                return
            status, payload = api.submit_application(data, files, self.client_address[0])
            self.send_json(status, payload)
            return
        if method == "POST" and route == "/quotes":
            data, files, error = self.parse_quote(raw)
            if error:
                self.send_json(400, {"error": error})
                return
            status, payload = api.create_quote(data, files, self.client_address[0])
            self.send_json(status, payload)
            return
        if method == "POST" and route == "/inquiries":
            data, attachment, error = self.parse_inquiry(raw)
            if error:
                self.send_json(400, {"error": error})
                return
            status, payload = api.create_inquiry(data, self.client_address[0], attachment)
            self.send_json(status, payload)
            return
        if method == "POST" and route == "/admin/login":
            data = api.json_body(raw)
            if data is None:
                self.send_json(400, {"error": "Invalid request."})
                return
            token = api.login(data.get("username"), data.get("password"))
            if not token:
                self.send_json(401, {"error": "Those credentials were not recognized."})
                return
            secure = "; Secure" if os.environ.get("VERCEL") else ""
            self.send_json(200, {"ok": True}, [("Set-Cookie", f"mcc_admin={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=43200{secure}")])
            return
        if method == "POST" and route == "/admin/logout":
            api.logout(cookie_token(self.headers.get("Cookie")))
            self.send_json(200, {"ok": True}, [("Set-Cookie", "mcc_admin=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")])
            return
        admin = self.require_admin()
        if route.startswith("/admin") and not admin:
            self.send_json(401, {"error": "Sign in required."})
            return
        if not admin and route.startswith("/admin"):
            return
        admin_id = admin[0] if admin else None
        if method == "GET" and route == "/admin/session":
            self.send_json(200, {"username": admin[1]})
            return
        if method == "GET" and route == "/admin/summary":
            self.send_json(200, {"summary": api.admin_summary()})
            return
        if method == "GET" and route == "/admin/quotes":
            self.send_json(200, {"quotes": api.list_quotes()})
            return
        quote_file = re.fullmatch(r"/admin/quotes/(\d+)/files/(\d+)", route)
        if method == "GET" and quote_file:
            found = api.quote_file(int(quote_file.group(1)), int(quote_file.group(2)))
            if not found:
                self.send_json(404, {"error": "File not found."})
                return
            path, name, ctype = found
            self.send_file(path, ctype, name, inline=True)
            return
        quote_match = re.fullmatch(r"/admin/quotes/(\d+)", route)
        if method == "PATCH" and quote_match:
            data = api.json_body(raw) or {}
            ok = api.set_quote_status(int(quote_match.group(1)), data.get("status"))
            self.send_json(200 if ok else 400, {"ok": ok})
            return
        if method == "GET" and route == "/admin/inquiries":
            self.send_json(200, {"inquiries": api.list_inquiries()})
            return
        inquiry_file = re.fullmatch(r"/admin/inquiries/(\d+)/attachment", route)
        if method == "GET" and inquiry_file:
            found = api.inquiry_file(int(inquiry_file.group(1)))
            if not found:
                self.send_json(404, {"error": "No attachment on this question."})
                return
            path, name, ctype = found
            self.send_file(path, ctype, name, inline=True)
            return
        inquiry_match = re.fullmatch(r"/admin/inquiries/(\d+)", route)
        if method == "PATCH" and inquiry_match:
            data = api.json_body(raw) or {}
            ok = api.set_inquiry_status(admin_id, int(inquiry_match.group(1)), data.get("status"))
            self.send_json(200 if ok else 400, {"ok": ok})
            return
        if method == "GET" and route == "/admin/jobs":
            conn = db.connect()
            try:
                jobs = api.list_admin_jobs(conn)
            finally:
                conn.close()
            self.send_json(200, {"jobs": jobs})
            return
        if method == "POST" and route == "/admin/jobs":
            data = api.json_body(raw)
            if data is None:
                self.send_json(400, {"error": "Invalid request."})
                return
            status, payload = api.create_job(admin_id, data)
            self.send_json(status, payload)
            return
        job_action = re.fullmatch(r"/admin/jobs/(JOB-\d+)(?:/(publish|close|archive|duplicate))?", route)
        if job_action:
            public_id, action = job_action.group(1), job_action.group(2)
            if method == "GET" and not action:
                conn = db.connect()
                try:
                    row = db.job_row(conn, public_id)
                    payload = None if not row else db.admin_job(conn, row)
                finally:
                    conn.close()
                if not payload:
                    self.send_json(404, {"error": "Job not found."})
                    return
                self.send_json(200, {"job": payload})
                return
            if method == "PATCH" and not action:
                data = api.json_body(raw)
                if data is None:
                    self.send_json(400, {"error": "Invalid request."})
                    return
                status, payload = api.update_job(admin_id, public_id, data)
                self.send_json(status, payload)
                return
            if method == "POST" and action == "publish":
                status, payload = api.set_job_status(admin_id, public_id, "open")
                self.send_json(status, payload)
                return
            if method == "POST" and action == "close":
                status, payload = api.set_job_status(admin_id, public_id, "closed")
                self.send_json(status, payload)
                return
            if method == "POST" and action == "archive":
                status, payload = api.set_job_status(admin_id, public_id, "archived")
                self.send_json(status, payload)
                return
            if method == "POST" and action == "duplicate":
                status, payload = api.duplicate_job(admin_id, public_id)
                self.send_json(status, payload)
                return
            if method == "DELETE" and not action:
                status, payload = api.set_job_status(admin_id, public_id, "archived")
                self.send_json(status, payload)
                return
        if method == "GET" and route == "/admin/applications":
            filters = {key: one(key, [None])[0] for key in ("job", "location", "status", "type", "date", "q")}
            status, payload = api.list_applications(filters)
            self.send_json(status, payload)
            return
        app_match = re.fullmatch(r"/admin/applications/(APP-\d{4}-\d+)", route)
        if method == "GET" and app_match:
            status, payload = api.get_application(app_match.group(1))
            self.send_json(status, payload)
            return
        if method == "PATCH" and app_match:
            data = api.json_body(raw) or {}
            status, payload = api.change_application_status(admin_id, app_match.group(1), data.get("status"))
            self.send_json(status, payload)
            return
        note_match = re.fullmatch(r"/admin/applications/(APP-\d{4}-\d+)/notes", route)
        if method == "POST" and note_match:
            data = api.json_body(raw) or {}
            status, payload = api.add_note(admin_id, note_match.group(1), data.get("note"))
            self.send_json(status, payload)
            return
        access_match = re.fullmatch(r"/documents/access/([A-Za-z0-9_\-]+)", route)
        if method == "GET" and access_match:
            found = documents.open_signed(access_match.group(1))
            if not found:
                self.send_json(404, {"error": "This document link has expired."})
                return
            path, name, ctype = found
            self.send_file(path, ctype, name)
            return
        request_match = re.fullmatch(r"/document-requests/([A-Za-z0-9_\-]+)", route)
        if request_match and method == "GET":
            info = documents.request_info(request_match.group(1))
            if not info:
                self.send_json(404, {"error": "This upload link is no longer available."})
                return
            self.send_json(200, {"request": info})
            return
        if request_match and method == "POST":
            saved, expiry, error = self.parse_requested_file(raw)
            if error:
                self.send_json(400, {"error": error})
                return
            ok, message = documents.fulfill_request(request_match.group(1), saved, expiry)
            self.send_json(200 if ok else 400, {"ok": ok, "error": message})
            return
        resume_match = re.fullmatch(r"/admin/applications/(APP-\d{4}-\d+)/resume", route)
        if method == "GET" and resume_match:
            found = api.resume_path(resume_match.group(1))
            if not found:
                self.send_json(404, {"error": "No resume on this application."})
                return
            path, name, ctype = found
            self.send_file(path, ctype, name)
            return
        doc_link = re.fullmatch(r"/admin/documents/(\d+)/link", route)
        if method == "POST" and doc_link:
            conn = db.connect()
            try:
                url = documents.signed_link(conn, int(doc_link.group(1)), admin_id)
            finally:
                conn.close()
            if not url:
                self.send_json(404, {"error": "Document not found."})
                return
            self.send_json(200, {"url": url})
            return
        doc_status = re.fullmatch(r"/admin/documents/(\d+)", route)
        if method == "PATCH" and doc_status:
            data = api.json_body(raw) or {}
            conn = db.connect()
            try:
                ok = documents.set_verification(conn, admin_id, int(doc_status.group(1)), data.get("verification_status"))
                conn.commit()
            finally:
                conn.close()
            self.send_json(200 if ok else 400, {"ok": ok})
            return
        ask_match = re.fullmatch(r"/admin/applications/(APP-\d{4}-\d+)/document-requests", route)
        if method == "POST" and ask_match:
            data = api.json_body(raw) or {}
            kind = data.get("document_type")
            if kind not in documents.DOC_TYPES:
                self.send_json(400, {"error": "Choose a document type."})
                return
            conn = db.connect()
            try:
                app_row = conn.execute("SELECT id, email, first_name FROM job_applications WHERE application_number = ?", (ask_match.group(1),)).fetchone()
                if not app_row:
                    self.send_json(404, {"error": "Application not found."})
                    return
                token, expires = documents.create_request(conn, admin_id, app_row["id"], kind, api.sanitize_text(data.get("message"), 1000), api.sanitize_text(data.get("due_date"), 20))
                link = "/application/documents/request/" + token
                api.send_email(conn, app_row["email"], "Document requested — Master Commercial Cleaning", "Hello %s,\n\nPlease upload the requested document using this secure link:\n%s\n\nThis link expires %s.\n" % (app_row["first_name"], link, expires[:10]))
                db.audit(conn, admin_id, "document_requested", "application", ask_match.group(1), kind)
                conn.commit()
            finally:
                conn.close()
            self.send_json(201, {"link": link})
            return
        if method == "GET" and route == "/admin/locations":
            self.send_json(200, {"locations": api.list_locations()})
            return
        if method == "POST" and route == "/admin/locations":
            data = api.json_body(raw) or {}
            status, payload = api.save_location(admin_id, data)
            self.send_json(status, payload)
            return
        loc_match = re.fullmatch(r"/admin/locations/(\d+)", route)
        if method == "PATCH" and loc_match:
            data = api.json_body(raw) or {}
            status, payload = api.save_location(admin_id, data, int(loc_match.group(1)))
            self.send_json(status, payload)
            return
        if method == "GET" and route == "/admin/settings":
            self.send_json(200, {"settings": api.get_settings()})
            return
        if method == "PATCH" and route == "/admin/settings":
            data = api.json_body(raw) or {}
            status, payload = api.save_settings(admin_id, data)
            self.send_json(status, payload)
            return
        if method == "POST" and route == "/admin/email-test":
            status, payload = api.send_test_email()
            self.send_json(status, payload)
            return
        self.send_json(404, {"error": "Not found"})

    def parse_quote(self, raw):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return None, None, "Invalid request."
        boundary = ""
        for piece in ctype.split(";"):
            if piece.strip().startswith("boundary="):
                boundary = piece.strip().split("=", 1)[1].strip('"')
        data = {}
        files = []
        for chunk in raw.split(("--" + boundary).encode()):
            if b"Content-Disposition" not in chunk:
                continue
            header, _, body = chunk.partition(b"\r\n\r\n")
            body = body[:-2] if body.endswith(b"\r\n") else body
            header_text = header.decode("utf-8", "replace")
            name = re.search(r'name="([^"]+)"', header_text)
            filename = re.search(r'filename="([^"]*)"', header_text)
            if not name:
                continue
            if filename:
                if not body:
                    continue
                kind = "video" if name.group(1) == "video" else "photo"
                saved, err = api.store_quote_file(filename.group(1), body, kind)
                if err:
                    return None, None, err
                files.append(saved)
            else:
                data[name.group(1)] = body.decode("utf-8", "replace")
        return data, files, None

    def parse_inquiry(self, raw):
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = api.json_body(raw)
            if data is None:
                return None, None, "Invalid question."
            return data, None, None
        if "multipart/form-data" not in ctype:
            return None, None, "Invalid question."
        boundary = ""
        for piece in ctype.split(";"):
            if piece.strip().startswith("boundary="):
                boundary = piece.strip().split("=", 1)[1].strip('"')
        data = {}
        attachment = None
        for chunk in raw.split(("--" + boundary).encode()):
            if b"Content-Disposition" not in chunk:
                continue
            header, _, body = chunk.partition(b"\r\n\r\n")
            body = body[:-2] if body.endswith(b"\r\n") else body
            header_text = header.decode("utf-8", "replace")
            name = re.search(r'name="([^"]+)"', header_text)
            filename = re.search(r'filename="([^"]*)"', header_text)
            if not name:
                continue
            if filename:
                if not body:
                    continue
                saved, err = documents.store_file(filename.group(1), body, "other")
                if err:
                    return None, None, err
                attachment = saved
            else:
                data[name.group(1)] = body.decode("utf-8", "replace")
        return data, attachment, None

    def parse_application(self, raw):
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = api.json_body(raw)
            if data is None:
                return None, None, "Invalid application."
            return data, None, None
        if "multipart/form-data" not in ctype:
            return None, None, "Invalid application."
        boundary = ""
        for piece in ctype.split(";"):
            piece = piece.strip()
            if piece.startswith("boundary="):
                boundary = piece.split("=", 1)[1].strip('"')
        if not boundary:
            return None, None, "Invalid application."
        marker = ("--" + boundary).encode()
        data = {}
        files = {"certificates": [], "additional": []}
        pending = {}
        for chunk in raw.split(marker):
            if b"Content-Disposition" not in chunk:
                continue
            header, _, body = chunk.partition(b"\r\n\r\n")
            body = body[:-2] if body.endswith(b"\r\n") else body
            if body.endswith(b"--"):
                body = body[:-2]
            header_text = header.decode("utf-8", "replace")
            name_match = re.search(r'name="([^"]+)"', header_text)
            if not name_match:
                continue
            name = name_match.group(1)
            file_match = re.search(r'filename="([^"]*)"', header_text)
            if file_match:
                if not body:
                    continue
                pending[name] = (file_match.group(1), body)
            elif name == "application":
                data = api.json_body(body)
                if data is None:
                    return None, None, "Invalid application."
        kind_for = {
            "resume": "resume",
            "cover_letter_file": "cover_letter",
            "work_permit": "work_permit",
            "study_permit": "study_permit",
            "drivers_license_file": "drivers_license",
        }
        for name, (filename, body) in pending.items():
            if name in kind_for:
                saved, err = documents.store_file(filename, body, kind_for[name])
                if err:
                    return None, None, err
                files[kind_for[name]] = saved
            elif name.startswith("certificate_file_"):
                saved, err = documents.store_file(filename, body, "certification")
                if err:
                    return None, None, err
                files["certificates"].append({"saved": saved, "slot": name.rsplit("_", 1)[-1]})
            elif name.startswith("additional_file_"):
                saved, err = documents.store_file(filename, body, "other")
                if err:
                    return None, None, err
                files["additional"].append({"saved": saved, "slot": name.rsplit("_", 1)[-1], "document_type": "other"})
        meta = data.get("documents") if isinstance(data.get("documents"), dict) else {}
        for cert in files["certificates"]:
            info = (meta.get("certificates") or {}).get(cert["slot"], {})
            cert["certificate_type"] = info.get("certificate_type") or "other"
            cert["name"] = info.get("name") or ""
            cert["expiry"] = info.get("expiry") or ""
        for extra in files["additional"]:
            info = (meta.get("additional") or {}).get(extra["slot"], {})
            extra["document_type"] = info.get("document_type") or "other"
            extra["name"] = info.get("name") or ""
        files["work_permit_expiry"] = data.get("work_permit_expiry") or ""
        files["study_permit_expiry"] = data.get("study_permit_expiry") or ""
        files["drivers_license_expiry"] = data.get("drivers_license_expiry") or ""
        return data, files, None

    def parse_requested_file(self, raw):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return None, "", "Upload a file."
        boundary = ""
        for piece in ctype.split(";"):
            if piece.strip().startswith("boundary="):
                boundary = piece.strip().split("=", 1)[1].strip('"')
        expiry = ""
        saved = None
        for chunk in raw.split(("--" + boundary).encode()):
            if b"Content-Disposition" not in chunk:
                continue
            header, _, body = chunk.partition(b"\r\n\r\n")
            body = body[:-2] if body.endswith(b"\r\n") else body
            header_text = header.decode("utf-8", "replace")
            name = re.search(r'name="([^"]+)"', header_text)
            filename = re.search(r'filename="([^"]*)"', header_text)
            if not name:
                continue
            if filename and body:
                info = documents.request_info(urlparse(self.path).path.rstrip("/").split("/")[-1])
                kind = info["document_type"] if info else "other"
                saved, err = documents.store_file(filename.group(1), body, kind)
                if err:
                    return None, "", err
            elif name.group(1) == "expiry_date":
                expiry = body.decode("utf-8", "replace").strip()[:20]
        if not saved:
            return None, "", "Choose a file to upload."
        return saved, expiry, None


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def main():
    db.init_db()
    server = DualStackServer(("::", PORT), Handler)
    print(f"Serving MCC at http://localhost:{PORT}")
    print(f"Careers: http://localhost:{PORT}/careers")
    print(f"Recruitment admin: http://localhost:{PORT}/admin")
    server.serve_forever()


if __name__ == "__main__":
    main()
