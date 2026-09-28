"""Persist hiring records for the live site. The database stays in a private repository."""

import base64
import io
import json
import os
import zipfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = os.environ.get("MCC_DATA_REPO", "davidmackasy/mcc-hiring-data")
FILE = "data.zip"


def _token():
    return (os.environ.get("MCC_DATA_TOKEN") or "").strip()


def _call(method, url, payload=None):
    headers = {
        "Authorization": "Bearer " + _token(),
        "Accept": "application/vnd.github+json",
        "User-Agent": "mcc-hiring",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def _contents_url():
    return "https://api.github.com/repos/%s/contents/%s" % (REPO, FILE)


def load(data_dir):
    if not _token():
        return
    os.makedirs(data_dir, exist_ok=True)
    status, body = _call("GET", _contents_url())
    if status != 200:
        return
    meta = json.loads(body.decode("utf-8"))
    raw = b""
    if meta.get("content"):
        raw = base64.b64decode("".join(meta["content"].split()))
    elif meta.get("download_url"):
        status, raw = _call("GET", meta["download_url"])
        if status != 200:
            return
    if not raw:
        return
    root = os.path.abspath(data_dir)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            target = os.path.abspath(os.path.join(root, name))
            if target != root and not target.startswith(root + os.sep):
                continue
            archive.extract(name, root)


def save(data_dir):
    token = _token()
    if not token or not os.path.isdir(data_dir):
        return False
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for folder, _dirs, files in os.walk(data_dir):
            if os.path.basename(folder) == "outbox":
                continue
            for name in files:
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, data_dir)
                if rel == "outbox" or rel.startswith("outbox" + os.sep):
                    continue
                archive.write(full, rel)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    status, body = _call("GET", _contents_url())
    payload = {"message": "Save hiring records", "content": encoded}
    if status == 200:
        payload["sha"] = json.loads(body.decode("utf-8")).get("sha")
    status, _body = _call("PUT", _contents_url(), payload)
    if status in (200, 201):
        return True
    if status == 409:
        status, body = _call("GET", _contents_url())
        if status == 200:
            payload["sha"] = json.loads(body.decode("utf-8")).get("sha")
            status, _body = _call("PUT", _contents_url(), payload)
            return status in (200, 201)
    return False
