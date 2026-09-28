"""Recruitment API handlers. Returns (status, payload_dict)."""

import base64
import json
import os
import re
import secrets
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from recruitment import db, documents

ALLOWED_TAGS = {"p", "br", "ul", "ol", "li", "strong", "em", "b", "i", "h3", "h4"}
RESUME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_RESUME = 10 * 1024 * 1024
_RATE = {}


def json_body(raw):
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def sanitize_text(value, limit=8000):
    if value is None:
        return ""
    text = str(value).replace("\x00", "").strip()
    return text[:limit]


def sanitize_html(value):
    text = sanitize_text(value, 20000)
    def replacer(match):
        tag = match.group(1).lower().split()[0].strip("/")
        if tag in ALLOWED_TAGS:
            if match.group(0).startswith("</"):
                return f"</{tag}>"
            if tag == "br":
                return "<br>"
            return f"<{tag}>"
        return ""
    return re.sub(r"</?([a-zA-Z0-9]+)(?:\s[^>]*)?>", replacer, text)


def requirement(value, allowed, default):
    text = sanitize_text(value, 40).lower().replace(" ", "_")
    return text if text in allowed else default


def boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ("1", "true", "yes", "on")


def optional_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rate_limited(ip):
    now = datetime.now()
    window = [stamp for stamp in _RATE.get(ip, []) if now - stamp < timedelta(hours=1)]
    if len(window) >= 8:
        _RATE[ip] = window
        return True
    window.append(now)
    _RATE[ip] = window
    return False


def session_user(conn, token):
    if not token:
        return None
    row = conn.execute(
        """SELECT admin_users.* FROM sessions
           JOIN admin_users ON admin_users.id = sessions.admin_user_id
           WHERE sessions.token = ? AND sessions.expires_at > ?""",
        (token, db.now_iso()),
    ).fetchone()
    return row


def login(username, password):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM admin_users WHERE username = ?", (sanitize_text(username, 80),)).fetchone()
        if not row or not db.verify_password(password or "", row["password_salt"], row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(hours=12)).replace(microsecond=0).isoformat()
        conn.execute(
            "INSERT INTO sessions (token, admin_user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, row["id"], db.now_iso(), expires),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def logout(token):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token or "",))
        conn.commit()
    finally:
        conn.close()


def job_fields(data, partial=False):
    errors = {}
    title = sanitize_text(data.get("title"), 160)
    if not partial or "title" in data:
        if not title:
            errors["title"] = "Job title is required."
    employment = sanitize_text(data.get("employment_type"), 40).lower()
    if (not partial or "employment_type" in data) and employment not in db.EMPLOYMENT_TYPES:
        errors["employment_type"] = "Choose an employment type."
    shift_type = sanitize_text(data.get("shift_type"), 40).lower()
    if shift_type and shift_type not in db.SHIFT_TYPES:
        errors["shift_type"] = "Choose a shift."
    pay_type = sanitize_text(data.get("pay_type"), 40).lower()
    if pay_type and pay_type not in db.PAY_TYPES:
        errors["pay_type"] = "Choose a pay type."
    fields = {
        "title": title,
        "location_id": optional_int(data.get("location_id")),
        "employment_type": employment,
        "shift_type": shift_type,
        "shift_description": sanitize_text(data.get("shift_description"), 120),
        "salary_min": optional_number(data.get("salary_min")),
        "salary_max": optional_number(data.get("salary_max")),
        "pay_type": pay_type,
        "show_pay": 0 if boolish(data.get("hide_pay")) or data.get("show_pay") is False else (1 if boolish(data.get("show_pay")) else 0),
        "description": sanitize_html(data.get("description")),
        "requirements": sanitize_html(data.get("requirements")),
        "positions_available": optional_int(data.get("positions_available")),
        "start_date": sanitize_text(data.get("start_date"), 20),
        "closing_date": sanitize_text(data.get("closing_date"), 20),
        "accepting_applications": 1 if boolish(data.get("accepting_applications", True)) else 0,
        "require_cover_letter": 1 if boolish(data.get("require_cover_letter")) or data.get("cover_letter_requirement") == "required" else 0,
        "resume_requirement": requirement(data.get("resume_requirement"), ("required", "optional", "not_required"), "optional"),
        "cover_letter_requirement": requirement(data.get("cover_letter_requirement"), ("required", "optional", "not_required"), "optional"),
        "work_permit_requirement": requirement(data.get("work_permit_requirement"), ("optional", "required", "later"), "optional"),
        "drivers_license_required": 1 if boolish(data.get("drivers_license_required")) else 0,
        "whmis_required": 1 if boolish(data.get("whmis_required")) else 0,
        "first_aid_required": 1 if boolish(data.get("first_aid_required")) else 0,
        "internal_notes": sanitize_text(data.get("internal_notes"), 4000),
    }
    if "show_pay" in data and not boolish(data.get("hide_pay")):
        fields["show_pay"] = 1 if boolish(data.get("show_pay")) else 0
    return fields, errors


def create_job(admin_id, data):
    fields, errors = job_fields(data)
    if errors:
        return 400, {"error": "Check the form and try again.", "fields": errors}
    conn = db.connect()
    try:
        if fields["location_id"] and not conn.execute("SELECT id FROM locations WHERE id = ? AND active = 1", (fields["location_id"],)).fetchone():
            return 400, {"error": "Choose an active location.", "fields": {"location_id": "Choose an active location."}}
        public_id = f"JOB-{db.next_counter(conn, 'job', 1001)}"
        stamp = db.now_iso()
        conn.execute(
            """INSERT INTO jobs (
                public_job_id, company_id, title, location_id, employment_type, shift_type, shift_description,
                salary_min, salary_max, pay_type, show_pay, description, requirements, positions_available,
                start_date, closing_date, status, accepting_applications, require_cover_letter, internal_notes,
                resume_requirement, cover_letter_requirement, work_permit_requirement, drivers_license_required,
                whmis_required, first_aid_required, published_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (
                public_id, db.company_id(conn), fields["title"], fields["location_id"], fields["employment_type"],
                fields["shift_type"], fields["shift_description"], fields["salary_min"], fields["salary_max"],
                fields["pay_type"], fields["show_pay"], fields["description"], fields["requirements"],
                fields["positions_available"], fields["start_date"], fields["closing_date"],
                fields["accepting_applications"], fields["require_cover_letter"], fields["internal_notes"],
                fields["resume_requirement"], fields["cover_letter_requirement"], fields["work_permit_requirement"],
                fields["drivers_license_required"], fields["whmis_required"], fields["first_aid_required"],
                stamp, stamp,
            ),
        )
        db.audit(conn, admin_id, "job_created", "job", public_id, fields["title"])
        conn.commit()
        return 201, {"job": db.admin_job(conn, db.job_row(conn, public_id))}
    finally:
        conn.close()


def update_job(admin_id, public_id, data):
    conn = db.connect()
    try:
        row = db.job_row(conn, public_id)
        if not row:
            return 404, {"error": "Job not found."}
        fields, errors = job_fields({**{k: row[k] for k in (
            "title", "location_id", "employment_type", "shift_type", "shift_description", "salary_min", "salary_max",
            "pay_type", "description", "requirements", "positions_available", "start_date", "closing_date",
            "accepting_applications", "require_cover_letter", "internal_notes", "resume_requirement",
            "cover_letter_requirement", "work_permit_requirement", "drivers_license_required", "whmis_required",
            "first_aid_required"
        )}, "show_pay": bool(row["show_pay"]), **data})
        if errors:
            return 400, {"error": "Check the form and try again.", "fields": errors}
        conn.execute(
            """UPDATE jobs SET title=?, location_id=?, employment_type=?, shift_type=?, shift_description=?,
               salary_min=?, salary_max=?, pay_type=?, show_pay=?, description=?, requirements=?,
               positions_available=?, start_date=?, closing_date=?, accepting_applications=?,
               require_cover_letter=?, internal_notes=?, resume_requirement=?, cover_letter_requirement=?,
               work_permit_requirement=?, drivers_license_required=?, whmis_required=?, first_aid_required=?,
               updated_at=? WHERE id=?""",
            (
                fields["title"], fields["location_id"], fields["employment_type"], fields["shift_type"],
                fields["shift_description"], fields["salary_min"], fields["salary_max"], fields["pay_type"],
                fields["show_pay"], fields["description"], fields["requirements"], fields["positions_available"],
                fields["start_date"], fields["closing_date"], fields["accepting_applications"],
                fields["require_cover_letter"], fields["internal_notes"], fields["resume_requirement"],
                fields["cover_letter_requirement"], fields["work_permit_requirement"], fields["drivers_license_required"],
                fields["whmis_required"], fields["first_aid_required"], db.now_iso(), row["id"],
            ),
        )
        db.audit(conn, admin_id, "job_edited", "job", public_id, fields["title"])
        conn.commit()
        return 200, {"job": db.admin_job(conn, db.job_row(conn, public_id))}
    finally:
        conn.close()


def set_job_status(admin_id, public_id, status):
    conn = db.connect()
    try:
        row = db.job_row(conn, public_id)
        if not row:
            return 404, {"error": "Job not found."}
        stamp = db.now_iso()
        if status == "open":
            conn.execute(
                """UPDATE jobs SET status='open', accepting_applications=1, published_at=COALESCE(published_at, ?),
                   archived_at=NULL, updated_at=? WHERE id=?""",
                (stamp, stamp, row["id"]),
            )
            action = "job_published"
        elif status == "closed":
            conn.execute(
                "UPDATE jobs SET status='closed', accepting_applications=0, updated_at=? WHERE id=?",
                (stamp, row["id"]),
            )
            action = "job_closed"
        elif status == "archived":
            conn.execute(
                "UPDATE jobs SET status='archived', accepting_applications=0, archived_at=?, updated_at=? WHERE id=?",
                (stamp, stamp, row["id"]),
            )
            action = "job_archived"
        else:
            return 400, {"error": "Unknown status."}
        db.audit(conn, admin_id, action, "job", public_id)
        conn.commit()
        return 200, {"job": db.admin_job(conn, db.job_row(conn, public_id))}
    finally:
        conn.close()


def duplicate_job(admin_id, public_id):
    conn = db.connect()
    try:
        row = db.job_row(conn, public_id)
        if not row:
            return 404, {"error": "Job not found."}
        new_id = f"JOB-{db.next_counter(conn, 'job', 1001)}"
        stamp = db.now_iso()
        conn.execute(
            """INSERT INTO jobs (
                public_job_id, company_id, title, location_id, employment_type, shift_type, shift_description,
                salary_min, salary_max, pay_type, show_pay, description, requirements, positions_available,
                start_date, closing_date, status, accepting_applications, require_cover_letter, internal_notes,
                resume_requirement, cover_letter_requirement, work_permit_requirement, drivers_license_required,
                whmis_required, first_aid_required, published_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
            (
                new_id, row["company_id"], row["title"], row["location_id"], row["employment_type"],
                row["shift_type"], row["shift_description"], row["salary_min"], row["salary_max"], row["pay_type"],
                row["show_pay"], row["description"], row["requirements"], row["positions_available"],
                row["start_date"], row["closing_date"], row["accepting_applications"], row["require_cover_letter"],
                row["internal_notes"], row["resume_requirement"], row["cover_letter_requirement"],
                row["work_permit_requirement"], row["drivers_license_required"], row["whmis_required"],
                row["first_aid_required"], stamp, stamp,
            ),
        )
        db.audit(conn, admin_id, "job_duplicated", "job", new_id, f"Copied from {public_id}")
        conn.commit()
        return 201, {"job": db.admin_job(conn, db.job_row(conn, new_id))}
    finally:
        conn.close()


def list_admin_jobs(conn):
    db.close_expired(conn)
    rows = conn.execute(
        """SELECT jobs.*, locations.name AS location_name, locations.city AS location_city,
                  locations.province AS location_province, locations.address AS location_address
           FROM jobs LEFT JOIN locations ON locations.id = jobs.location_id
           ORDER BY jobs.created_at DESC"""
    ).fetchall()
    return [db.admin_job(conn, row) for row in rows]


def save_resume(file_name, content_type, data_bytes):
    ext = os.path.splitext(file_name or "")[1].lower()
    if ext not in RESUME_TYPES:
        return None, "Upload a PDF, DOC, or DOCX resume."
    if len(data_bytes) > MAX_RESUME:
        return None, "Resume must be 10 MB or smaller."
    if not data_bytes:
        return None, "The resume file is empty."
    key = secrets.token_hex(16) + ext
    path = os.path.join(db.RESUME_DIR, key)
    with open(path, "wb") as handle:
        handle.write(data_bytes)
    return {
        "storage_key": key,
        "filename": os.path.basename(file_name)[:180],
        "content_type": RESUME_TYPES[ext],
        "size_bytes": len(data_bytes),
    }, None


def validate_application(data, job):
    errors = {}
    required = {
        "first_name": "First name is required.",
        "last_name": "Last name is required.",
        "email": "Email is required.",
        "phone": "Phone number is required.",
        "city": "City is required.",
        "province": "Province is required.",
    }
    for key, message in required.items():
        if not sanitize_text(data.get(key), 160):
            errors[key] = message
    email = sanitize_text(data.get("email"), 160)
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors["email"] = "Enter a valid email address."
    if not boolish(data.get("certified")):
        errors["certified"] = "Confirm the information is accurate."
    if not boolish(data.get("consent_contact")):
        errors["consent_contact"] = "Consent is required so we can contact you."
    if data.get("eligible_to_work") is None:
        errors["eligible_to_work"] = "Answer whether you are legally authorized to work in Canada."
    if not sanitize_text(data.get("work_authorization"), 80):
        errors["work_authorization"] = "Select your current authorization to work in Canada."
    if data.get("able_to_perform_duties") is None:
        errors["able_to_perform_duties"] = "Answer the essential duties question."
    cover_rule = (job["cover_letter_requirement"] if job else "") or ("required" if job and job["require_cover_letter"] else "optional")
    if job and cover_rule == "required" and not sanitize_text(data.get("cover_letter"), 8000) and not (data.get("_files") or {}).get("cover_letter"):
        errors["cover_letter"] = "Add a cover letter or upload one for this job."
    files = data.get("_files") or {}
    if job and (job["resume_requirement"] or "optional") == "required" and not files.get("resume"):
        errors["resume"] = "A resume is required for this job."
    if job and job["drivers_license_required"] and not boolish(data.get("drivers_license")):
        errors["drivers_license"] = "This job requires a valid driver's licence."
    if job and job["drivers_license_required"] and boolish(data.get("drivers_license")) and not files.get("drivers_license"):
        errors["drivers_license_file"] = "Upload your driver's licence for this job."
    if job and (job["work_permit_requirement"] or "") == "required" and sanitize_text(data.get("work_authorization"), 80) == "work_permit" and not files.get("work_permit"):
        errors["work_permit"] = "Upload your work permit for this job."
    certs = files.get("certificates") or []
    cert_types = {item.get("certificate_type") for item in certs}
    if job and job["whmis_required"] and "whmis" not in cert_types:
        errors["certificates"] = "Upload a WHMIS certificate for this job."
    if job and job["first_aid_required"] and "first_aid" not in cert_types:
        errors["certificates"] = "Upload a First Aid certificate for this job."
    if boolish(data.get("has_cleaning_experience")) and not sanitize_text(data.get("years_experience"), 40):
        errors["years_experience"] = "Select years of experience."
    if sanitize_text(data.get("company_website") or data.get("honeypot"), 200):
        errors["form"] = "Unable to submit this application."
    return errors


def encode_form(fields, files):
    boundary = "----mcc" + secrets.token_hex(12)
    chunks = []
    for name, value in fields:
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, name, value)).encode("utf-8"))
    for filename, mime, data in files:
        safe = (filename or "attachment").replace('"', "")
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"attachment\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n" % (boundary, safe, mime or "application/octet-stream")).encode("utf-8"))
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), boundary


def mailgun_send(conn, to_addr, subject, body, from_addr, attachments=None):
    api_key = (db.setting(conn, "mailgun_api_key", "") or "").strip()
    domain = (db.setting(conn, "mailgun_domain", "") or "").strip()
    if not api_key or not domain:
        return None
    region = (db.setting(conn, "mailgun_region", "us") or "us").lower()
    host = "https://api.eu.mailgun.net" if region == "eu" else "https://api.mailgun.net"
    payload, boundary = encode_form(
        [("from", from_addr), ("to", to_addr), ("subject", subject), ("text", body)],
        [((item.get("filename") or "attachment"), item.get("mime") or "application/octet-stream", item.get("data") or b"") for item in (attachments or [])],
    )
    request = Request(
        "%s/v3/%s/messages" % (host, domain),
        data=payload,
        headers={
            "Authorization": "Basic " + base64.b64encode(("api:" + api_key).encode("utf-8")).decode("ascii"),
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response.read()
        return True
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        detail = exc.read().decode("utf-8", "replace") if isinstance(exc, HTTPError) else str(exc)
        path = os.path.join(db.OUTBOX_DIR, secrets.token_hex(8) + ".mailgun-error")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(detail[:2000])
        return False


def send_email(conn, to_addr, subject, body, attachments=None):
    recipients = [part.strip() for part in str(to_addr or "").replace(";", ",").split(",") if part.strip()]
    from_addr = (os.environ.get("SMTP_FROM") or "").strip() or db.setting(conn, "smtp_from", "") or "noreply@mastercleaning.ca"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    for item in attachments or []:
        maintype, _, subtype = (item.get("mime") or "application/octet-stream").partition("/")
        message.add_attachment(item["data"], maintype=maintype or "application", subtype=subtype or "octet-stream", filename=item.get("filename") or "attachment")
    filename = os.path.join(db.OUTBOX_DIR, secrets.token_hex(8) + ".eml")
    with open(filename, "wb") as handle:
        handle.write(bytes(message))
    if not recipients:
        return False
    mailed = mailgun_send(conn, ", ".join(recipients), subject, body, from_addr, attachments)
    if mailed is not None:
        return mailed
    host = (os.environ.get("SMTP_HOST") or "").strip() or db.setting(conn, "smtp_host", "") or ""
    if not host:
        return False
    try:
        port = int((os.environ.get("SMTP_PORT") or "").strip() or db.setting(conn, "smtp_port", "587") or "587")
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            user = (os.environ.get("SMTP_USER") or "").strip() or db.setting(conn, "smtp_user", "") or ""
            password = (os.environ.get("SMTP_PASSWORD") or "").strip() or db.setting(conn, "smtp_password", "") or ""
            if user:
                smtp.login(user, password)
            smtp.send_message(message, to_addrs=recipients)
        return True
    except Exception as exc:
        with open(filename + ".error", "w", encoding="utf-8") as handle:
            handle.write(str(exc))
        return False


def send_test_email():
    conn = db.connect()
    try:
        to_addr = db.setting(conn, "quote_email", "") or db.setting(conn, "recruitment_email", "") or ""
        if not to_addr:
            return 400, {"error": "Add the inbox that should receive these emails, then save."}
        if not (db.setting(conn, "mailgun_api_key", "") or db.setting(conn, "smtp_host", "")):
            return 400, {"error": "Add the Mailgun domain and API key, then save."}
        ok = send_email(conn, to_addr, "Mailgun test — Master Commercial Cleaning", "This is a test from the website. If this arrived, quote requests will come to this inbox.\n")
        if ok:
            return 200, {"ok": True, "sent_to": to_addr}
        return 502, {"error": "Mailgun did not accept the message. Check the domain, region, API key, and From address."}
    finally:
        conn.close()


def save_application_files(conn, app_id, company_id, files):
    mapping = (
        ("resume", "resume", ""),
        ("cover_letter", "cover_letter", ""),
        ("work_permit", "work_permit", "work_permit_expiry"),
        ("study_permit", "study_permit", "study_permit_expiry"),
        ("drivers_license", "drivers_license", "drivers_license_expiry"),
    )
    for key, doc_type, expiry_key in mapping:
        saved = files.get(key)
        if not saved:
            continue
        documents.insert_document(conn, app_id, company_id, doc_type, saved, expiry=files.get(expiry_key) or "")
        if doc_type == "resume":
            conn.execute(
                "INSERT INTO resume_files (application_id, storage_key, filename, content_type, size_bytes) VALUES (?, ?, ?, ?, ?)",
                (app_id, saved["storage_key"], saved["filename"], saved["mime_type"], saved["file_size"]),
            )
    for cert in files.get("certificates") or []:
        if not cert.get("saved"):
            continue
        documents.insert_document(
            conn, app_id, company_id, "certification", cert["saved"],
            name=cert.get("name") or cert.get("certificate_type") or "Certificate",
            expiry=cert.get("expiry") or "",
        )
    for extra in files.get("additional") or []:
        if not extra.get("saved"):
            continue
        documents.insert_document(
            conn, app_id, company_id, extra.get("document_type") or "other", extra["saved"],
            name=extra.get("name") or "Supporting document",
        )
    return None


def submit_application(data, files, ip):
    data = dict(data or {})
    data["_files"] = files or {}
    if rate_limited(ip or "unknown"):
        return 429, {"error": "Too many applications from this network. Please try again later."}
    conn = db.connect()
    try:
        db.close_expired(conn)
        public_id = sanitize_text(data.get("job_id"), 40)
        row = db.job_row(conn, public_id)
        if not row or row["status"] != "open":
            return 400, {"error": "This position is no longer available."}
        today = date.today().isoformat()
        if row["closing_date"] and row["closing_date"] < today:
            return 400, {"error": "This position is no longer accepting applications."}
        if not row["accepting_applications"]:
            return 400, {"error": "This position is no longer accepting applications."}
        errors = validate_application(data, row)
        if errors:
            return 400, {"error": "Check the form and try again.", "fields": errors}
        number = f"APP-{date.today().year}-{db.next_counter(conn, 'application-' + str(date.today().year), 1):05d}"
        stamp = db.now_iso()
        availability = data.get("availability") if isinstance(data.get("availability"), dict) else {}
        cur = conn.execute(
            """INSERT INTO job_applications (
                application_number, job_id, company_id, first_name, last_name, email, phone, street_address,
                city, province, postal_code, availability_json, start_date, employment_preference, weekends,
                evenings, has_cleaning_experience, years_experience, experience_description, no_previous_employment,
                previous_employer, previous_position, previous_employment_length, drivers_license,
                reliable_transportation, willing_to_travel, eligible_to_work, able_to_perform_duties, certified,
                consent_contact, cover_letter, status, submitted_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?)""",
            (
                number, row["id"], row["company_id"],
                sanitize_text(data.get("first_name"), 80), sanitize_text(data.get("last_name"), 80),
                sanitize_text(data.get("email"), 160), sanitize_text(data.get("phone"), 40),
                sanitize_text(data.get("street_address"), 160), sanitize_text(data.get("city"), 80),
                sanitize_text(data.get("province"), 40), sanitize_text(data.get("postal_code"), 16),
                json.dumps(availability)[:8000], sanitize_text(data.get("start_date"), 20),
                sanitize_text(data.get("employment_preference"), 40),
                1 if boolish(data.get("weekends")) else 0,
                1 if boolish(data.get("evenings")) else 0,
                1 if boolish(data.get("has_cleaning_experience")) else 0,
                sanitize_text(data.get("years_experience"), 40),
                sanitize_text(data.get("experience_description"), 4000),
                1 if boolish(data.get("no_previous_employment")) else 0,
                sanitize_text(data.get("previous_employer"), 160),
                sanitize_text(data.get("previous_position"), 160),
                sanitize_text(data.get("previous_employment_length"), 80),
                1 if boolish(data.get("drivers_license")) else 0,
                1 if boolish(data.get("reliable_transportation")) else 0,
                1 if boolish(data.get("willing_to_travel")) else 0,
                1 if boolish(data.get("eligible_to_work")) else 0,
                1 if boolish(data.get("able_to_perform_duties")) else 0,
                1, 1, sanitize_text(data.get("cover_letter"), 8000), stamp, stamp,
            ),
        )
        app_id = cur.lastrowid
        conn.execute(
            """UPDATE job_applications SET work_authorization=?, work_permit_type=?, work_permit_expiry=?,
               study_permit_expiry=?, authorization_notes=?, drivers_license_expiry=? WHERE id=?""",
            (
                sanitize_text(data.get("work_authorization"), 80),
                sanitize_text(data.get("work_permit_type"), 80),
                sanitize_text(data.get("work_permit_expiry"), 20),
                sanitize_text(data.get("study_permit_expiry"), 20),
                sanitize_text(data.get("authorization_notes"), 2000),
                sanitize_text(data.get("drivers_license_expiry"), 20),
                app_id,
            ),
        )
        file_error = save_application_files(conn, app_id, row["company_id"], files or {})
        if file_error:
            conn.rollback()
            return 400, {"error": file_error}
        refs = data.get("references") if isinstance(data.get("references"), list) else []
        for ref in refs[:2]:
            if not isinstance(ref, dict):
                continue
            if not any(sanitize_text(ref.get(k), 160) for k in ("name", "phone", "email")):
                continue
            conn.execute(
                "INSERT INTO application_references (application_id, name, relationship, phone, email) VALUES (?, ?, ?, ?, ?)",
                (
                    app_id, sanitize_text(ref.get("name"), 120), sanitize_text(ref.get("relationship"), 80),
                    sanitize_text(ref.get("phone"), 40), sanitize_text(ref.get("email"), 160),
                ),
            )
        conn.execute(
            "INSERT INTO application_status_history (application_id, previous_status, new_status, changed_by, created_at) VALUES (?, NULL, 'new', NULL, ?)",
            (app_id, stamp),
        )
        location = row["location_name"] or ""
        admin_email = (os.environ.get("RECRUITMENT_EMAIL") or "").strip() or db.setting(conn, "recruitment_email", "gift.delvin@mastercleaning.ca, davd.maluti@mastercleaning.ca")
        link = f"/admin/recruitment/applications/{number}"
        send_email(
            conn,
            admin_email,
            f"New Application — {row['title']} — {location}",
            f"Applicant: {sanitize_text(data.get('first_name'), 80)} {sanitize_text(data.get('last_name'), 80)}\n"
            f"Position: {row['title']}\nLocation: {location}\nSubmitted: {stamp}\n\nView application: {link}\n",
        )
        send_email(
            conn,
            sanitize_text(data.get("email"), 160),
            "We Received Your Application",
            f"Hello {sanitize_text(data.get('first_name'), 80)},\n\n"
            f"Thank you for applying to Master Commercial Cleaning.\n\n"
            f"Position: {row['title']}\nLocation: {location}\nApplication reference: {number}\n\n"
            "Your application has been received. If your experience matches our current hiring needs, our team may contact you.\n",
        )
        conn.commit()
        return 201, {
            "application_number": number,
            "message": "Thank you for applying to Master Commercial Cleaning. Your application has been received. If your experience matches our current hiring needs, our team may contact you.",
        }
    finally:
        conn.close()


def application_admin(conn, row):
    refs = conn.execute(
        "SELECT name, relationship, phone, email FROM application_references WHERE application_id = ?",
        (row["id"],),
    ).fetchall()
    notes = conn.execute(
        "SELECT id, note, created_at FROM application_notes WHERE application_id = ? ORDER BY created_at DESC",
        (row["id"],),
    ).fetchall()
    history = conn.execute(
        "SELECT previous_status, new_status, created_at FROM application_status_history WHERE application_id = ? ORDER BY created_at",
        (row["id"],),
    ).fetchall()
    resume = conn.execute(
        "SELECT filename, content_type, size_bytes FROM resume_files WHERE application_id = ?",
        (row["id"],),
    ).fetchone()
    try:
        availability = json.loads(row["availability_json"] or "{}")
    except json.JSONDecodeError:
        availability = {}
    return {
        "application_number": row["application_number"],
        "status": row["status"],
        "status_label": db.APP_STATUS_LABELS.get(row["status"], row["status"]),
        "submitted_at": row["submitted_at"],
        "applicant": {
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "phone": row["phone"],
            "street_address": row["street_address"] or "",
            "city": row["city"],
            "province": row["province"],
            "postal_code": row["postal_code"] or "",
        },
        "job": {
            "job_id": row["public_job_id"],
            "title": row["title"],
            "location": row["location_name"] or "",
            "employment_type_label": db.EMPLOYMENT_LABELS.get(row["employment_type"], row["employment_type"]),
        },
        "availability": availability,
        "start_date": row["start_date"] or "",
        "employment_preference": row["employment_preference"] or "",
        "weekends": bool(row["weekends"]),
        "evenings": bool(row["evenings"]),
        "has_cleaning_experience": bool(row["has_cleaning_experience"]),
        "years_experience": row["years_experience"] or "",
        "experience_description": row["experience_description"] or "",
        "no_previous_employment": bool(row["no_previous_employment"]),
        "previous_employer": row["previous_employer"] or "",
        "previous_position": row["previous_position"] or "",
        "previous_employment_length": row["previous_employment_length"] or "",
        "drivers_license": bool(row["drivers_license"]),
        "reliable_transportation": bool(row["reliable_transportation"]),
        "willing_to_travel": bool(row["willing_to_travel"]),
        "eligible_to_work": bool(row["eligible_to_work"]),
        "work_authorization": row["work_authorization"] or "",
        "work_permit_type": row["work_permit_type"] or "",
        "work_permit_expiry": row["work_permit_expiry"] or "",
        "work_permit_expiry_label": documents.expiry_label(row["work_permit_expiry"]),
        "study_permit_expiry": row["study_permit_expiry"] or "",
        "study_permit_expiry_label": documents.expiry_label(row["study_permit_expiry"]),
        "authorization_notes": row["authorization_notes"] or "",
        "drivers_license_expiry": row["drivers_license_expiry"] or "",
        "drivers_license_expiry_label": documents.expiry_label(row["drivers_license_expiry"]),
        "documents": documents.list_documents(conn, row["id"]),
        "able_to_perform_duties": bool(row["able_to_perform_duties"]),
        "cover_letter": row["cover_letter"] or "",
        "references": [dict(item) for item in refs],
        "notes": [{"id": n["id"], "note": n["note"], "created_at": n["created_at"]} for n in notes],
        "status_history": [dict(item) for item in history],
        "resume": None if not resume else {
            "filename": resume["filename"],
            "content_type": resume["content_type"],
            "size_bytes": resume["size_bytes"],
        },
    }


def list_query():
    return """SELECT job_applications.*, jobs.public_job_id, jobs.title, jobs.employment_type,
                     locations.name AS location_name
              FROM job_applications
              JOIN jobs ON jobs.id = job_applications.job_id
              LEFT JOIN locations ON locations.id = jobs.location_id"""


def list_applications(filters):
    conn = db.connect()
    try:
        clauses = []
        params = []
        if filters.get("job"):
            clauses.append("jobs.public_job_id = ?")
            params.append(filters["job"])
        if filters.get("location"):
            clauses.append("lower(locations.name) = ?")
            params.append(filters["location"].lower())
        if filters.get("status"):
            clauses.append("job_applications.status = ?")
            params.append(filters["status"])
        if filters.get("type"):
            clauses.append("jobs.employment_type = ?")
            params.append(filters["type"])
        if filters.get("date"):
            clauses.append("substr(job_applications.submitted_at, 1, 10) = ?")
            params.append(filters["date"])
        search = (filters.get("q") or "").strip()
        if search:
            like = f"%{search.lower()}%"
            clauses.append(
                """(lower(job_applications.first_name || ' ' || job_applications.last_name) LIKE ?
                    OR lower(job_applications.email) LIKE ? OR job_applications.phone LIKE ?
                    OR lower(job_applications.application_number) LIKE ?)"""
            )
            params.extend([like, like, f"%{search}%", like])
        sql = list_query()
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY job_applications.submitted_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return 200, {
            "applications": [
                {
                    "application_number": row["application_number"],
                    "applicant": f"{row['first_name']} {row['last_name']}",
                    "job_id": row["public_job_id"],
                    "job_title": row["title"],
                    "location": row["location_name"] or "",
                    "phone": row["phone"],
                    "email": row["email"],
                    "employment_type": row["employment_type"],
                    "applied_at": row["submitted_at"],
                    "status": row["status"],
                    "status_label": db.APP_STATUS_LABELS.get(row["status"], row["status"]),
                }
                for row in rows
            ]
        }
    finally:
        conn.close()


def get_application(number):
    conn = db.connect()
    try:
        row = conn.execute(list_query() + " WHERE job_applications.application_number = ?", (number,)).fetchone()
        if not row:
            return 404, {"error": "Application not found."}
        return 200, {"application": application_admin(conn, row)}
    finally:
        conn.close()


def change_application_status(admin_id, number, status):
    if status not in db.APP_STATUSES:
        return 400, {"error": "Unknown application status."}
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM job_applications WHERE application_number = ?", (number,)).fetchone()
        if not row:
            return 404, {"error": "Application not found."}
        previous = row["status"]
        stamp = db.now_iso()
        conn.execute(
            "UPDATE job_applications SET status = ?, updated_at = ? WHERE id = ?",
            (status, stamp, row["id"]),
        )
        conn.execute(
            """INSERT INTO application_status_history (application_id, previous_status, new_status, changed_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (row["id"], previous, status, admin_id, stamp),
        )
        db.audit(conn, admin_id, "application_status_changed", "application", number, f"{previous} -> {status}")
        conn.commit()
        return get_application(number)
    finally:
        conn.close()


def add_note(admin_id, number, note):
    text = sanitize_text(note, 4000)
    if not text:
        return 400, {"error": "Write a note before saving."}
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM job_applications WHERE application_number = ?", (number,)).fetchone()
        if not row:
            return 404, {"error": "Application not found."}
        conn.execute(
            "INSERT INTO application_notes (application_id, admin_user_id, note, created_at) VALUES (?, ?, ?, ?)",
            (row["id"], admin_id, text, db.now_iso()),
        )
        db.audit(conn, admin_id, "application_note_added", "application", number)
        conn.commit()
        return get_application(number)
    finally:
        conn.close()


def resume_path(number):
    conn = db.connect()
    try:
        row = conn.execute(
            """SELECT resume_files.* FROM resume_files
               JOIN job_applications ON job_applications.id = resume_files.application_id
               WHERE job_applications.application_number = ?""",
            (number,),
        ).fetchone()
        if not row:
            return None
        path = os.path.join(db.RESUME_DIR, row["storage_key"])
        if not os.path.isfile(path):
            return None
        return path, row["filename"], row["content_type"]
    finally:
        conn.close()


def list_locations(active_only=False):
    conn = db.connect()
    try:
        sql = "SELECT * FROM locations WHERE company_id = ?"
        params = [db.company_id(conn)]
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY name"
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "address": row["address"] or "",
                "city": row["city"],
                "province": row["province"],
                "postal_code": row["postal_code"] or "",
                "active": bool(row["active"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def save_location(admin_id, data, location_id=None):
    name = sanitize_text(data.get("name"), 80)
    city = sanitize_text(data.get("city"), 80)
    province = sanitize_text(data.get("province"), 40) or "Manitoba"
    if not name or not city:
        return 400, {"error": "Location name and city are required."}
    conn = db.connect()
    try:
        if location_id:
            row = conn.execute("SELECT id FROM locations WHERE id = ?", (location_id,)).fetchone()
            if not row:
                return 404, {"error": "Location not found."}
            conn.execute(
                """UPDATE locations SET name=?, address=?, city=?, province=?, postal_code=?, active=? WHERE id=?""",
                (
                    name, sanitize_text(data.get("address"), 160), city, province,
                    sanitize_text(data.get("postal_code"), 16), 1 if boolish(data.get("active", True)) else 0, location_id,
                ),
            )
            db.audit(conn, admin_id, "location_updated", "location", str(location_id), name)
        else:
            conn.execute(
                """INSERT INTO locations (company_id, name, address, city, province, postal_code, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    db.company_id(conn), name, sanitize_text(data.get("address"), 160), city, province,
                    sanitize_text(data.get("postal_code"), 16), 1 if boolish(data.get("active", True)) else 0, db.now_iso(),
                ),
            )
            db.audit(conn, admin_id, "location_created", "location", name, name)
        conn.commit()
        return 200, {"locations": list_locations()}
    finally:
        conn.close()


def get_settings():
    conn = db.connect()
    try:
        return {
            "recruitment_email": db.setting(conn, "recruitment_email", ""),
            "quote_email": db.setting(conn, "quote_email", "") or "",
            "smtp_host": db.setting(conn, "smtp_host", "") or "",
            "smtp_port": db.setting(conn, "smtp_port", "587") or "587",
            "smtp_user": db.setting(conn, "smtp_user", "") or "",
            "smtp_from": db.setting(conn, "smtp_from", "") or "",
            "smtp_password_set": bool(db.setting(conn, "smtp_password", "")),
            "mailgun_domain": db.setting(conn, "mailgun_domain", "") or "",
            "mailgun_region": db.setting(conn, "mailgun_region", "us") or "us",
            "mailgun_api_key_set": bool(db.setting(conn, "mailgun_api_key", "")),
        }
    finally:
        conn.close()


def save_settings(admin_id, data):
    conn = db.connect()
    try:
        db.set_setting(conn, "recruitment_email", sanitize_text(data.get("recruitment_email"), 400))
        db.set_setting(conn, "quote_email", sanitize_text(data.get("quote_email"), 160))
        db.set_setting(conn, "smtp_host", sanitize_text(data.get("smtp_host"), 160))
        db.set_setting(conn, "smtp_port", sanitize_text(data.get("smtp_port"), 8) or "587")
        db.set_setting(conn, "smtp_user", sanitize_text(data.get("smtp_user"), 160))
        db.set_setting(conn, "smtp_from", sanitize_text(data.get("smtp_from"), 160))
        db.set_setting(conn, "mailgun_domain", sanitize_text(data.get("mailgun_domain"), 160).lower())
        db.set_setting(conn, "mailgun_region", "eu" if sanitize_text(data.get("mailgun_region"), 8).lower() == "eu" else "us")
        if data.get("mailgun_api_key"):
            db.set_setting(conn, "mailgun_api_key", str(data.get("mailgun_api_key")).strip()[:200])
        if data.get("smtp_password"):
            db.set_setting(conn, "smtp_password", str(data.get("smtp_password"))[:200])
        if data.get("new_password"):
            salt, digest = db.hash_password(str(data.get("new_password")))
            conn.execute(
                "UPDATE admin_users SET password_salt = ?, password_hash = ? WHERE id = ?",
                (salt, digest, admin_id),
            )
        db.audit(conn, admin_id, "settings_updated", "settings", "recruitment")
        conn.commit()
        return 200, {"settings": get_settings()}
    finally:
        conn.close()


def store_quote_file(filename, data, kind):
    ext = os.path.splitext(filename or "")[1].lower()
    photos = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    videos = {".mp4", ".mov", ".webm"}
    allowed = photos if kind == "photo" else videos
    if ext not in allowed:
        return None, "Use a JPG, PNG, or WEBP photo, or an MP4, MOV, or WEBM video."
    limit = 8 * 1024 * 1024 if kind == "photo" else 25 * 1024 * 1024
    if not data or len(data) > limit:
        return None, "Each photo must be 8 MB or smaller, and the video must be 25 MB or smaller."
    ok = False
    if ext in (".jpg", ".jpeg"):
        ok = data.startswith(b"\xff\xd8\xff")
    elif ext == ".png":
        ok = data.startswith(b"\x89PNG")
    elif ext == ".webp":
        ok = data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    elif ext in (".heic", ".heif"):
        ok = b"ftyp" in data[:32]
    elif ext in (".mp4", ".mov"):
        ok = b"ftyp" in data[:32]
    elif ext == ".webm":
        ok = data.startswith(b"\x1a\x45\xdf\xa3")
    if not ok:
        return None, "That file doesn't look like a valid photo or video."
    key = secrets.token_hex(16) + ext
    with open(os.path.join(db.QUOTE_DIR, key), "wb") as handle:
        handle.write(data)
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".heic": "image/heic", ".heif": "image/heif",
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    }[ext]
    return {"storage_key": key, "filename": os.path.basename(filename)[:180], "mime_type": mime, "kind": kind, "file_size": len(data)}, None


def measure_note(raw):
    if not isinstance(raw, dict):
        return ""
    label = sanitize_text(raw.get("label"), 80)
    length = sanitize_text(str(raw.get("length") or ""), 12)
    width = sanitize_text(str(raw.get("width") or ""), 12)
    square_feet = sanitize_text(str(raw.get("square_feet") or ""), 12)
    size = ""
    if length and width:
        size = length + " ft × " + width + " ft"
    if square_feet:
        size = (size + " · " if size else "") + square_feet + " sq ft"
    return " · ".join(part for part in (label, size) if part)


def create_quote(data, files, ip):
    if rate_limited(ip or "unknown"):
        return 429, {"error": "Too many requests from this network. Please call us or try again later."}
    if sanitize_text(data.get("company_website"), 200):
        return 400, {"error": "Unable to send this request."}
    name = sanitize_text(data.get("name"), 120)
    email = sanitize_text(data.get("email"), 160)
    message = sanitize_text(data.get("message"), 4000)
    if not name or not email or not message:
        return 400, {"error": "Name, email, and a short description are required."}
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return 400, {"error": "Enter a valid email address."}
    photos = [item for item in files if item.get("kind") == "photo"]
    videos = [item for item in files if item.get("kind") == "video"]
    if len(photos) > 6 or len(videos) > 1:
        return 400, {"error": "You can send up to 6 photos and 1 short video."}
    conn = db.connect()
    try:
        stamp = db.now_iso()
        fields = (
            name, sanitize_text(data.get("business"), 160), email, sanitize_text(data.get("phone"), 40),
            sanitize_text(data.get("facility_type"), 80), sanitize_text(data.get("city"), 80),
            sanitize_text(data.get("square_feet"), 40), sanitize_text(data.get("rooms"), 40),
            sanitize_text(data.get("service"), 120), sanitize_text(data.get("frequency"), 80),
            message, stamp,
        )
        cur = conn.execute(
            """INSERT INTO quote_requests
               (name, business_name, email, phone, facility_type, city, square_feet, rooms, service, frequency, message, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
            fields,
        )
        quote_id = cur.lastrowid
        photo_notes = []
        video_note = {}
        try:
            parsed = json.loads(data.get("photo_notes") or "[]")
            if isinstance(parsed, list):
                photo_notes = parsed
        except (TypeError, ValueError):
            photo_notes = []
        try:
            parsed = json.loads(data.get("video_note") or "{}")
            if isinstance(parsed, dict):
                video_note = parsed
        except (TypeError, ValueError):
            video_note = {}
        photo_index = 0
        for saved in files:
            if saved.get("kind") == "photo":
                note = measure_note(photo_notes[photo_index]) if photo_index < len(photo_notes) else ""
                photo_index += 1
            else:
                note = measure_note(video_note)
            saved["note"] = note
            conn.execute(
                "INSERT INTO quote_files (quote_id, storage_key, filename, mime_type, kind, note) VALUES (?, ?, ?, ?, ?, ?)",
                (quote_id, saved["storage_key"], saved["filename"], saved["mime_type"], saved["kind"], note),
            )
        to_addr = db.setting(conn, "quote_email", "") or db.setting(conn, "recruitment_email", "") or "clean@mastercleaning.ca"
        lines = [
            "New quote request from the website",
            "",
            "Name: %s" % name,
            "Business: %s" % (fields[1] or "—"),
            "Email: %s" % email,
            "Phone: %s" % (fields[3] or "—"),
            "Facility: %s" % (fields[4] or "—"),
            "City: %s" % (fields[5] or "—"),
            "Approximate size: %s sq ft" % (fields[6] or "not given"),
            "Rooms: %s" % (fields[7] or "not given"),
            "Service: %s" % (fields[8] or "—"),
            "Frequency: %s" % (fields[9] or "—"),
            "",
            message,
            "",
            "Photos: %s" % (len(photos) or "none"),
        ]
        for saved in photos:
            if saved.get("note"):
                lines.append("  " + saved["note"])
        lines.append("Video: %s" % ((videos[0]["filename"] + (" (" + videos[0]["note"] + ")" if videos[0].get("note") else "")) if videos else "none"))
        attachments = []
        for saved in photos:
            path = os.path.join(db.QUOTE_DIR, saved["storage_key"])
            if os.path.isfile(path) and saved.get("file_size", 0) <= 3 * 1024 * 1024:
                with open(path, "rb") as handle:
                    attachments.append({"filename": saved["filename"], "mime": saved["mime_type"], "data": handle.read()})
        if videos:
            lines.append("The video is saved with this request. Open Recruitment, then Quotes, to watch it.")
        send_email(conn, to_addr, "New quote request — " + name, "\n".join(lines) + "\n", attachments)
        conn.commit()
        return 201, {"ok": True}
    finally:
        conn.close()


def list_quotes():
    conn = db.connect()
    try:
        rows = conn.execute("SELECT * FROM quote_requests ORDER BY created_at DESC").fetchall()
        files = conn.execute("SELECT id, quote_id, filename, kind, note FROM quote_files ORDER BY id").fetchall()
        grouped = {}
        for item in files:
            grouped.setdefault(item["quote_id"], []).append({"id": item["id"], "filename": item["filename"], "kind": item["kind"], "note": item["note"] or ""})
        result = []
        for row in rows:
            item = dict(row)
            item["files"] = grouped.get(row["id"], [])
            result.append(item)
        return result
    finally:
        conn.close()


def quote_file(quote_id, file_id):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT storage_key, filename, mime_type FROM quote_files WHERE id = ? AND quote_id = ?",
            (file_id, quote_id),
        ).fetchone()
        if not row:
            return None
        path = os.path.join(db.QUOTE_DIR, row["storage_key"])
        if not os.path.isfile(path):
            return None
        return path, row["filename"], row["mime_type"] or "application/octet-stream"
    finally:
        conn.close()


def set_quote_status(quote_id, status):
    if status not in ("new", "read", "closed"):
        return False
    conn = db.connect()
    try:
        cur = conn.execute("UPDATE quote_requests SET status = ? WHERE id = ?", (status, quote_id))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def create_inquiry(data, ip, attachment=None):
    if rate_limited(ip or "unknown"):
        return 429, {"error": "Too many messages from this network. Please try again later."}
    if sanitize_text(data.get("company_website"), 200):
        return 400, {"error": "Unable to send this message."}
    name = sanitize_text(data.get("name"), 120)
    email = sanitize_text(data.get("email"), 160)
    message = sanitize_text(data.get("message"), 4000)
    if not name or not email or not message:
        return 400, {"error": "Name, email, and a question are required."}
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return 400, {"error": "Enter a valid email address."}
    conn = db.connect()
    try:
        stamp = db.now_iso()
        conn.execute(
            """INSERT INTO inquiries (company_id, name, email, phone, message, job_public_id, status, created_at, attachment_key, attachment_name, attachment_type)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)""",
            (
                db.company_id(conn), name, email, sanitize_text(data.get("phone"), 40), message, sanitize_text(data.get("job_id"), 40), stamp,
                attachment.get("storage_key") if attachment else None,
                attachment.get("filename") if attachment else None,
                attachment.get("mime_type") if attachment else None,
            ),
        )
        send_email(conn, db.setting(conn, "recruitment_email", "clean@mastercleaning.ca"), "New careers question — " + name, "From: %s\nEmail: %s\nPhone: %s\nPosition: %s\n\n%s\n" % (name, email, data.get("phone") or "", data.get("job_id") or "General", message))
        conn.commit()
        return 201, {"ok": True}
    finally:
        conn.close()


def admin_summary():
    conn = db.connect()
    try:
        new_apps = conn.execute("SELECT COUNT(*) AS n FROM job_applications WHERE status = 'new'").fetchone()["n"]
        new_inquiries = conn.execute("SELECT COUNT(*) AS n FROM inquiries WHERE status = 'new'").fetchone()["n"]
        new_quotes = conn.execute("SELECT COUNT(*) AS n FROM quote_requests WHERE status = 'new'").fetchone()["n"]
        open_jobs = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE status = 'open'").fetchone()["n"]
        apps = conn.execute(
            """SELECT job_applications.application_number, job_applications.first_name, job_applications.last_name,
                      job_applications.status, job_applications.submitted_at, jobs.title
               FROM job_applications JOIN jobs ON jobs.id = job_applications.job_id
               ORDER BY job_applications.submitted_at DESC LIMIT 5"""
        ).fetchall()
        inquiries = conn.execute("SELECT id, name, email, phone, message, job_public_id, status, created_at, attachment_name FROM inquiries ORDER BY created_at DESC LIMIT 5").fetchall()
        quotes = conn.execute("SELECT id, name, business_name, city, service, status, created_at FROM quote_requests ORDER BY created_at DESC LIMIT 5").fetchall()
        return {
            "new_applications": new_apps,
            "new_inquiries": new_inquiries,
            "new_quotes": new_quotes,
            "open_jobs": open_jobs,
            "applications": [{"application_number": row["application_number"], "applicant": row["first_name"] + " " + row["last_name"], "title": row["title"], "status": row["status"], "submitted_at": row["submitted_at"]} for row in apps],
            "inquiries": [dict(row) for row in inquiries],
            "quotes": [dict(row) for row in quotes],
        }
    finally:
        conn.close()


def inquiry_file(inquiry_id):
    conn = db.connect()
    try:
        row = conn.execute("SELECT attachment_key, attachment_name, attachment_type FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
        if not row or not row["attachment_key"]:
            return None
        path = os.path.join(db.DOC_DIR, row["attachment_key"])
        if not os.path.isfile(path):
            return None
        return path, row["attachment_name"], row["attachment_type"] or "application/octet-stream"
    finally:
        conn.close()


def list_inquiries():
    conn = db.connect()
    try:
        rows = conn.execute("SELECT * FROM inquiries ORDER BY created_at DESC").fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item.pop("attachment_key", None)
            items.append(item)
        return items
    finally:
        conn.close()


def set_inquiry_status(admin_id, inquiry_id, status):
    if status not in ("new", "read", "closed"):
        return False
    conn = db.connect()
    try:
        cur = conn.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))
        if cur.rowcount:
            db.audit(conn, admin_id, "inquiry_status_changed", "inquiry", str(inquiry_id), status)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
