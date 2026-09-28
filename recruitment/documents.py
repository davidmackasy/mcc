"""Private applicant document storage. Files stay under data/documents."""

import os
import secrets
from datetime import date, datetime, timedelta

from recruitment import db

DOC_TYPES = (
    "resume", "cover_letter", "work_permit", "study_permit", "drivers_license",
    "permanent_resident_document", "certification", "reference_letter", "other",
)
OFFICE = {".pdf", ".doc", ".docx"}
IMAGES = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED = {
    "resume": OFFICE,
    "cover_letter": OFFICE,
    "work_permit": IMAGES,
    "study_permit": IMAGES,
    "drivers_license": IMAGES,
    "permanent_resident_document": IMAGES,
    "certification": OFFICE | IMAGES,
    "reference_letter": OFFICE | IMAGES,
    "other": OFFICE | IMAGES,
}
MAGIC = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".docx": b"PK\x03\x04",
    ".doc": b"\xd0\xcf\x11\xe0",
}
LABELS = {
    "resume": "Resume",
    "cover_letter": "Cover Letter",
    "work_permit": "Work Permit",
    "study_permit": "Study Permit",
    "drivers_license": "Driver's Licence",
    "permanent_resident_document": "Permanent Resident Document",
    "certification": "Certification",
    "reference_letter": "Reference Letter",
    "other": "Other",
}
VERIFY = ("not_provided", "uploaded", "requested", "verified", "needs_review", "expired")


def expiry_label(value):
    if not value:
        return None
    try:
        day = date.fromisoformat(value[:10])
    except ValueError:
        return None
    today = date.today()
    if day < today:
        return "Expired"
    if day <= today + timedelta(days=60):
        return "Expiring Soon"
    return "Valid"


def store_file(filename, data, document_type):
    ext = os.path.splitext(filename or "")[1].lower()
    allowed = ALLOWED.get(document_type)
    if not allowed or ext not in allowed:
        return None, "That file type is not allowed for this document."
    if not data or len(data) > 10 * 1024 * 1024:
        return None, "Each file must be 10 MB or smaller."
    magic = MAGIC.get(ext)
    if magic and not data.startswith(magic):
        return None, "The file contents do not match its extension."
    key = secrets.token_hex(16) + ext
    with open(os.path.join(db.DOC_DIR, key), "wb") as handle:
        handle.write(data)
    mime = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[ext]
    return {"storage_key": key, "filename": os.path.basename(filename)[:180], "mime_type": mime, "file_size": len(data)}, None


def insert_document(conn, application_id, company_id, document_type, saved, name="", expiry="", status="uploaded"):
    stamp = db.now_iso()
    conn.execute(
        """INSERT INTO applicant_documents (
            application_id, company_id, document_type, document_name, original_filename, storage_key,
            mime_type, file_size, expiry_date, verification_status, uploaded_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            application_id, company_id, document_type, name or LABELS.get(document_type, document_type),
            saved["filename"] if saved else None, saved["storage_key"] if saved else None,
            saved["mime_type"] if saved else None, saved["file_size"] if saved else None,
            expiry or None, status, stamp if saved else None, stamp, stamp,
        ),
    )


def serialize(row):
    return {
        "id": row["id"],
        "document_type": row["document_type"],
        "label": LABELS.get(row["document_type"], row["document_type"]),
        "document_name": row["document_name"] or "",
        "filename": row["original_filename"] or "",
        "file_size": row["file_size"],
        "expiry_date": row["expiry_date"] or "",
        "expiry_label": expiry_label(row["expiry_date"]),
        "verification_status": row["verification_status"],
        "uploaded_at": row["uploaded_at"],
        "has_file": bool(row["storage_key"]),
    }


def list_documents(conn, application_id):
    rows = conn.execute(
        "SELECT * FROM applicant_documents WHERE application_id = ? ORDER BY id",
        (application_id,),
    ).fetchall()
    return [serialize(row) for row in rows]


def open_document(conn, document_id, admin_id=None):
    row = conn.execute("SELECT * FROM applicant_documents WHERE id = ?", (document_id,)).fetchone()
    if not row or not row["storage_key"]:
        return None
    path = os.path.join(db.DOC_DIR, row["storage_key"])
    if not os.path.isfile(path):
        return None
    if admin_id:
        db.audit(conn, admin_id, "document_viewed", "document", str(document_id), row["original_filename"])
        conn.commit()
    return path, row["original_filename"], row["mime_type"]


def signed_link(conn, document_id, admin_id):
    if not open_document(conn, document_id):
        return None
    token = secrets.token_urlsafe(24)
    expires = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    conn.execute(
        "INSERT INTO document_links (token, document_id, admin_user_id, expires_at) VALUES (?, ?, ?, ?)",
        (token, document_id, admin_id, expires),
    )
    conn.commit()
    return "/api/v1/documents/access/" + token


def open_signed(token):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM document_links WHERE token = ? AND expires_at > ?",
            (token, db.now_iso()),
        ).fetchone()
        if not row:
            return None
        found = open_document(conn, row["document_id"], row["admin_user_id"])
        return found
    finally:
        conn.close()


def create_request(conn, admin_id, application_id, document_type, message, due_date, days=14):
    token = secrets.token_urlsafe(24)
    stamp = db.now_iso()
    expires = (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()
    conn.execute(
        """INSERT INTO document_requests (token, application_id, document_type, message, due_date, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (token, application_id, document_type, message, due_date or None, expires, stamp),
    )
    conn.execute(
        """INSERT INTO applicant_documents (
            application_id, company_id, document_type, document_name, verification_status,
            requested_by, requested_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'requested', ?, ?, ?, ?)""",
        (application_id, db.company_id(conn), document_type, LABELS.get(document_type, document_type), admin_id, stamp, stamp, stamp),
    )
    return token, expires


def request_info(token):
    conn = db.connect()
    try:
        row = conn.execute(
            """SELECT document_requests.*, job_applications.application_number, job_applications.first_name
               FROM document_requests
               JOIN job_applications ON job_applications.id = document_requests.application_id
               WHERE document_requests.token = ?""",
            (token,),
        ).fetchone()
        if not row:
            return None
        expired = row["expires_at"] < db.now_iso() or row["fulfilled_at"]
        return {
            "document_type": row["document_type"],
            "label": LABELS.get(row["document_type"], row["document_type"]),
            "message": row["message"] or "",
            "due_date": row["due_date"] or "",
            "expired": bool(expired),
            "applicant": row["first_name"],
        }
    finally:
        conn.close()


def fulfill_request(token, saved, expiry):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM document_requests WHERE token = ?", (token,)).fetchone()
        if not row or row["fulfilled_at"] or row["expires_at"] < db.now_iso():
            return False, "This upload link is no longer available."
        app = conn.execute("SELECT company_id FROM job_applications WHERE id = ?", (row["application_id"],)).fetchone()
        insert_document(conn, row["application_id"], app["company_id"], row["document_type"], saved, expiry=expiry or "")
        conn.execute("UPDATE document_requests SET fulfilled_at = ? WHERE id = ?", (db.now_iso(), row["id"]))
        conn.commit()
        return True, None
    finally:
        conn.close()


def set_verification(conn, admin_id, document_id, status):
    if status not in VERIFY:
        return False
    stamp = db.now_iso()
    verified_at = stamp if status == "verified" else None
    cur = conn.execute(
        """UPDATE applicant_documents SET verification_status = ?, verified_by = ?, verified_at = ?, updated_at = ?
           WHERE id = ?""",
        (status, admin_id if status == "verified" else None, verified_at, stamp, document_id),
    )
    if cur.rowcount:
        db.audit(conn, admin_id, "document_status_changed", "document", str(document_id), status)
    return cur.rowcount > 0
