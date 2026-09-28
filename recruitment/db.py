"""SQLite store for the Master Commercial Cleaning recruitment module."""

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "recruitment.sqlite")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
DOC_DIR = os.path.join(DATA_DIR, "documents")
QUOTE_DIR = os.path.join(DATA_DIR, "quotes")
OUTBOX_DIR = os.path.join(DATA_DIR, "outbox")

EMPLOYMENT_TYPES = ("full-time", "part-time", "casual", "temporary", "contract")
EMPLOYMENT_LABELS = {
    "full-time": "Full-Time",
    "part-time": "Part-Time",
    "casual": "Casual",
    "temporary": "Temporary",
    "contract": "Contract",
}
PAY_TYPES = ("hourly", "salary", "contract", "negotiable")
PAY_LABELS = {
    "hourly": "Per hour",
    "salary": "Salary",
    "contract": "Contract",
    "negotiable": "Negotiable",
}
SHIFT_TYPES = ("morning", "day", "evening", "overnight", "flexible")
JOB_STATUSES = ("draft", "open", "closed", "archived")
APP_STATUSES = (
    "new",
    "under_review",
    "shortlisted",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
)
APP_STATUS_LABELS = {
    "new": "New",
    "under_review": "Under Review",
    "shortlisted": "Shortlisted",
    "interview": "Interview",
    "offer": "Offer",
    "hired": "Hired",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_PARTS = ("morning", "afternoon", "evening", "overnight")


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESUME_DIR, exist_ok=True)
    os.makedirs(DOC_DIR, exist_ok=True)
    os.makedirs(QUOTE_DIR, exist_ok=True)
    os.makedirs(OUTBOX_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return salt, digest.hex()


def verify_password(password, salt, digest):
    _, check = hash_password(password, salt)
    return secrets.compare_digest(check, digest)


def init_db():
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id),
            name TEXT NOT NULL,
            address TEXT,
            city TEXT NOT NULL,
            province TEXT NOT NULL,
            postal_code TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            public_job_id TEXT NOT NULL UNIQUE,
            company_id INTEGER NOT NULL REFERENCES companies(id),
            title TEXT NOT NULL,
            location_id INTEGER REFERENCES locations(id),
            employment_type TEXT NOT NULL,
            shift_type TEXT,
            shift_description TEXT,
            salary_min REAL,
            salary_max REAL,
            pay_type TEXT,
            show_pay INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            requirements TEXT,
            positions_available INTEGER,
            start_date TEXT,
            closing_date TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            accepting_applications INTEGER NOT NULL DEFAULT 1,
            require_cover_letter INTEGER NOT NULL DEFAULT 0,
            internal_notes TEXT,
            views INTEGER NOT NULL DEFAULT 0,
            published_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY,
            application_number TEXT NOT NULL UNIQUE,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            company_id INTEGER NOT NULL REFERENCES companies(id),
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            street_address TEXT,
            city TEXT NOT NULL,
            province TEXT NOT NULL,
            postal_code TEXT,
            availability_json TEXT,
            start_date TEXT,
            employment_preference TEXT,
            weekends INTEGER,
            evenings INTEGER,
            has_cleaning_experience INTEGER,
            years_experience TEXT,
            experience_description TEXT,
            no_previous_employment INTEGER NOT NULL DEFAULT 0,
            previous_employer TEXT,
            previous_position TEXT,
            previous_employment_length TEXT,
            drivers_license INTEGER,
            reliable_transportation INTEGER,
            willing_to_travel INTEGER,
            eligible_to_work INTEGER,
            able_to_perform_duties INTEGER,
            certified INTEGER NOT NULL DEFAULT 0,
            consent_contact INTEGER NOT NULL DEFAULT 0,
            cover_letter TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            submitted_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resume_files (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL UNIQUE REFERENCES job_applications(id),
            storage_key TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS application_references (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES job_applications(id),
            name TEXT,
            relationship TEXT,
            phone TEXT,
            email TEXT
        );
        CREATE TABLE IF NOT EXISTS application_notes (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES job_applications(id),
            admin_user_id INTEGER,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS application_status_history (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES job_applications(id),
            previous_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            admin_user_id INTEGER NOT NULL REFERENCES admin_users(id),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            admin_user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );
        """
    )
    company = conn.execute("SELECT id FROM companies WHERE slug = ?", ("master-commercial-cleaning",)).fetchone()
    if not company:
        conn.execute(
            "INSERT INTO companies (company_name, slug, active) VALUES (?, ?, 1)",
            ("Master Commercial Cleaning", "master-commercial-cleaning"),
        )
        company_id = conn.execute("SELECT id FROM companies WHERE slug = ?", ("master-commercial-cleaning",)).fetchone()["id"]
        created = now_iso()
        for name, city in (("Winnipeg", "Winnipeg"), ("Oakbank", "Oakbank"), ("Beausejour", "Beausejour")):
            conn.execute(
                """INSERT INTO locations (company_id, name, city, province, active, created_at)
                   VALUES (?, ?, ?, 'Manitoba', 1, ?)""",
                (company_id, name, city, created),
            )
    if not conn.execute("SELECT id FROM admin_users WHERE username = 'admin'").fetchone():
        password = os.environ.get("MCC_ADMIN_PASSWORD") or "mcc-admin"
        salt, digest = hash_password(password)
        conn.execute(
            "INSERT INTO admin_users (username, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("admin", salt, digest, now_iso()),
        )
        flag = os.path.join(DATA_DIR, "admin_password_initialized")
        if not os.path.exists(flag):
            with open(flag, "w", encoding="utf-8") as handle:
                handle.write("admin\n")
            print("Recruitment admin login: username admin / password " + password)
    if conn.execute("SELECT value FROM settings WHERE key = 'recruitment_email'").fetchone() is None:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('recruitment_email', ?)",
            ("clean@mastercleaning.ca",),
        )
    migrate(conn)
    conn.commit()
    conn.close()


def migrate(conn):
    def add(table, column, ddl):
        cols = [row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)]
        if column not in cols:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))

    add("jobs", "resume_requirement", "TEXT NOT NULL DEFAULT 'optional'")
    add("jobs", "cover_letter_requirement", "TEXT NOT NULL DEFAULT 'optional'")
    add("jobs", "work_permit_requirement", "TEXT NOT NULL DEFAULT 'optional'")
    add("jobs", "drivers_license_required", "INTEGER NOT NULL DEFAULT 0")
    add("jobs", "whmis_required", "INTEGER NOT NULL DEFAULT 0")
    add("jobs", "first_aid_required", "INTEGER NOT NULL DEFAULT 0")
    add("job_applications", "work_authorization", "TEXT")
    add("job_applications", "work_permit_type", "TEXT")
    add("job_applications", "work_permit_expiry", "TEXT")
    add("job_applications", "study_permit_expiry", "TEXT")
    add("job_applications", "authorization_notes", "TEXT")
    add("job_applications", "drivers_license_expiry", "TEXT")
    add("inquiries", "attachment_key", "TEXT")
    add("inquiries", "attachment_name", "TEXT")
    add("inquiries", "attachment_type", "TEXT")
    add("quote_files", "note", "TEXT")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quote_requests (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            business_name TEXT,
            email TEXT NOT NULL,
            phone TEXT,
            facility_type TEXT,
            city TEXT,
            square_feet TEXT,
            rooms TEXT,
            service TEXT,
            frequency TEXT,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quote_files (
            id INTEGER PRIMARY KEY,
            quote_id INTEGER NOT NULL REFERENCES quote_requests(id),
            storage_key TEXT NOT NULL,
            filename TEXT,
            mime_type TEXT,
            kind TEXT
        )"""
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS applicant_documents (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES job_applications(id),
            company_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            document_name TEXT,
            original_filename TEXT,
            storage_key TEXT,
            mime_type TEXT,
            file_size INTEGER,
            expiry_date TEXT,
            verification_status TEXT NOT NULL DEFAULT 'uploaded',
            requested_by INTEGER,
            requested_at TEXT,
            uploaded_at TEXT,
            verified_by INTEGER,
            verified_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS document_requests (
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            application_id INTEGER NOT NULL REFERENCES job_applications(id),
            document_type TEXT NOT NULL,
            message TEXT,
            due_date TEXT,
            expires_at TEXT NOT NULL,
            fulfilled_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            message TEXT NOT NULL,
            job_public_id TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS document_links (
            token TEXT PRIMARY KEY,
            document_id INTEGER NOT NULL,
            admin_user_id INTEGER,
            expires_at TEXT NOT NULL
        );
        """
    )


def company_id(conn):
    row = conn.execute("SELECT id FROM companies WHERE slug = ?", ("master-commercial-cleaning",)).fetchone()
    return row["id"]


def next_counter(conn, name, start):
    row = conn.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()
    if row is None:
        value = start
        conn.execute("INSERT INTO counters (name, value) VALUES (?, ?)", (name, value))
    else:
        value = row["value"] + 1
        conn.execute("UPDATE counters SET value = ? WHERE name = ?", (value, name))
    return value


def audit(conn, admin_id, action, entity_type=None, entity_id=None, detail=None):
    conn.execute(
        """INSERT INTO audit_log (admin_user_id, action, entity_type, entity_id, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (admin_id, action, entity_type, entity_id, detail, now_iso()),
    )


def setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def location_public(row):
    if row is None:
        return None
    return {
        "name": row["name"],
        "city": row["city"],
        "province": row["province"],
        "address": row["address"] or "",
    }


def pay_label(job):
    if not job["show_pay"]:
        return None
    if (job["pay_type"] or "") == "negotiable" and job["salary_min"] is None:
        return "Negotiable"
    amount = job["salary_min"]
    if amount is None:
        return None
    text = f"${amount:g}"
    if job["salary_max"]:
        text = f"${job['salary_min']:g}–${job['salary_max']:g}"
    kind = job["pay_type"] or ""
    if kind == "hourly":
        return text + "/hour"
    if kind == "salary":
        return text + " salary"
    if kind == "contract":
        return text + " contract"
    if kind == "negotiable":
        return text + " (negotiable)"
    return text


def shift_label(job):
    custom = (job["shift_description"] or "").strip()
    if custom:
        return custom
    kind = job["shift_type"] or ""
    return kind[:1].upper() + kind[1:] if kind else ""


def summary_text(description):
    text = " ".join((description or "").replace("<", " <").split())
    # strip tags roughly
    out = []
    skip = False
    for ch in text:
        if ch == "<":
            skip = True
            continue
        if ch == ">":
            skip = False
            continue
        if not skip:
            out.append(ch)
    clean = " ".join("".join(out).split())
    if len(clean) > 180:
        return clean[:177].rstrip() + "..."
    return clean


def close_expired(conn):
    today = date.today().isoformat()
    rows = conn.execute(
        """SELECT id, public_job_id FROM jobs
           WHERE status = 'open' AND closing_date IS NOT NULL AND closing_date != '' AND closing_date < ?""",
        (today,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE jobs SET status = 'closed', accepting_applications = 0, updated_at = ? WHERE id = ?",
            (now_iso(), row["id"]),
        )
        audit(conn, None, "job_auto_closed", "job", row["public_job_id"], "Closing date passed")
    if rows:
        conn.commit()


def job_row(conn, public_job_id):
    return conn.execute(
        """SELECT jobs.*, locations.name AS location_name, locations.city AS location_city,
                  locations.province AS location_province, locations.address AS location_address
           FROM jobs LEFT JOIN locations ON locations.id = jobs.location_id
           WHERE jobs.public_job_id = ?""",
        (public_job_id,),
    ).fetchone()


def application_count(conn, job_pk):
    return conn.execute("SELECT COUNT(*) AS n FROM job_applications WHERE job_id = ?", (job_pk,)).fetchone()["n"]


def public_job(conn, row, detail=False):
    payload = {
        "job_id": row["public_job_id"],
        "title": row["title"],
        "location": row["location_name"] or "",
        "city": row["location_city"] or "",
        "province": row["location_province"] or "",
        "address": row["location_address"] or "",
        "employment_type": row["employment_type"],
        "employment_type_label": EMPLOYMENT_LABELS.get(row["employment_type"], row["employment_type"]),
        "shift": shift_label(row),
        "pay": pay_label(row),
        "summary": summary_text(row["description"]),
        "posted_at": (row["published_at"] or row["created_at"] or "")[:10],
        "closing_date": row["closing_date"] or None,
        "positions_available": row["positions_available"],
        "start_date": row["start_date"] or None,
    }
    if detail:
        payload.update(
            {
                "description": row["description"] or "",
                "requirements": row["requirements"] or "",
                "accepting_applications": bool(row["accepting_applications"]) and row["status"] == "open",
                "require_cover_letter": (row["cover_letter_requirement"] or "") == "required" or bool(row["require_cover_letter"]),
                "resume_requirement": row["resume_requirement"] or "optional",
                "cover_letter_requirement": row["cover_letter_requirement"] or "optional",
                "work_permit_requirement": row["work_permit_requirement"] or "optional",
                "drivers_license_required": bool(row["drivers_license_required"]),
                "whmis_required": bool(row["whmis_required"]),
                "first_aid_required": bool(row["first_aid_required"]),
            }
        )
    return payload


def admin_job(conn, row):
    views = row["views"] or 0
    apps = application_count(conn, row["id"])
    rate = round((apps / views) * 100, 1) if views else 0
    return {
        "job_id": row["public_job_id"],
        "title": row["title"],
        "location_id": row["location_id"],
        "location": row["location_name"] or "",
        "city": row["location_city"] or "",
        "province": row["location_province"] or "",
        "employment_type": row["employment_type"],
        "employment_type_label": EMPLOYMENT_LABELS.get(row["employment_type"], row["employment_type"]),
        "shift_type": row["shift_type"] or "",
        "shift_description": row["shift_description"] or "",
        "shift": shift_label(row),
        "salary_min": row["salary_min"],
        "salary_max": row["salary_max"],
        "pay_type": row["pay_type"] or "",
        "show_pay": bool(row["show_pay"]),
        "pay": pay_label(row),
        "description": row["description"] or "",
        "requirements": row["requirements"] or "",
        "positions_available": row["positions_available"],
        "start_date": row["start_date"] or "",
        "closing_date": row["closing_date"] or "",
        "status": row["status"],
        "accepting_applications": bool(row["accepting_applications"]),
        "require_cover_letter": (row["cover_letter_requirement"] or "") == "required" or bool(row["require_cover_letter"]),
        "resume_requirement": row["resume_requirement"] or "optional",
        "cover_letter_requirement": row["cover_letter_requirement"] or "optional",
        "work_permit_requirement": row["work_permit_requirement"] or "optional",
        "drivers_license_required": bool(row["drivers_license_required"]),
        "whmis_required": bool(row["whmis_required"]),
        "first_aid_required": bool(row["first_aid_required"]),
        "internal_notes": row["internal_notes"] or "",
        "applications": apps,
        "views": views,
        "conversion_rate": rate,
        "published_at": row["published_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived_at": row["archived_at"],
    }


def list_public_jobs(conn, location=None, employment_type=None):
    close_expired(conn)
    query = """SELECT jobs.*, locations.name AS location_name, locations.city AS location_city,
                      locations.province AS location_province, locations.address AS location_address
               FROM jobs LEFT JOIN locations ON locations.id = jobs.location_id
               WHERE jobs.status = 'open'"""
    params = []
    if location:
        query += " AND lower(locations.name) = ?"
        params.append(location.strip().lower())
    if employment_type:
        query += " AND jobs.employment_type = ?"
        params.append(employment_type.strip().lower())
    query += " ORDER BY COALESCE(jobs.published_at, jobs.created_at) DESC"
    return [public_job(conn, row) for row in conn.execute(query, params).fetchall()]


def get_public_job(conn, public_job_id):
    close_expired(conn)
    row = job_row(conn, public_job_id)
    if not row or row["status"] != "open":
        return None
    return public_job(conn, row, detail=True)


def record_view(conn, public_job_id):
    row = job_row(conn, public_job_id)
    if not row or row["status"] != "open":
        return False
    conn.execute("UPDATE jobs SET views = views + 1 WHERE id = ?", (row["id"],))
    conn.commit()
    return True
