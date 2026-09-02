import os
import json
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any
from app.core.config import settings


def _auth_headers(token: Optional[str] = None) -> dict:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _ext_from_content_type(content_type: str) -> str:
    ct = content_type.lower()
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "gif" in ct:
        return ".gif"
    if "webp" in ct:
        return ".webp"
    if "svg" in ct:
        return ".svg"
    if "pdf" in ct:
        return ".pdf"
    return ".bin"


def _download_to(url: str, dest_path: str, token: Optional[str] = None, timeout: int = 60) -> bool:
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        req = urllib.request.Request(url, headers=_auth_headers(token))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"[file_sync] Failed {url}: {e}")
        return False


def _file_exists_in_dir(directory: str, pattern: str) -> bool:
    p = Path(directory)
    if not p.exists():
        return False
    return any(p.glob(pattern))


def sync_geometry_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"images_downloaded": 0, "images_skipped": 0, "pdfs_downloaded": 0, "pdfs_skipped": 0}

    remote_cursor.execute("SELECT id FROM geometries WHERE image_url IS NOT NULL")
    for row in remote_cursor.fetchall():
        geometry_id = str(row[0])
        if _file_exists_in_dir(settings.geometry_images_dir, f"{geometry_id}.*"):
            stats["images_skipped"] += 1
            continue
        url = f"{base_url}/api/v1/geometries/{geometry_id}/image"
        try:
            req = urllib.request.Request(url, headers=_auth_headers(token))
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    ext = _ext_from_content_type(resp.headers.get("Content-Type", ""))
                    dest = os.path.join(settings.geometry_images_dir, f"{geometry_id}{ext}")
                    with open(dest, "wb") as f:
                        f.write(resp.read())
                    stats["images_downloaded"] += 1
        except Exception as e:
            print(f"[file_sync] Image failed for {geometry_id}: {e}")

    if token:
        remote_cursor.execute("SELECT id, pdf_document FROM geometries WHERE pdf_document IS NOT NULL")
        for row in remote_cursor.fetchall():
            geometry_id = str(row[0])
            raw = row[1]
            if isinstance(raw, str):
                try:
                    pdf_doc = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(raw, dict):
                pdf_doc = raw
            else:
                continue
            if not pdf_doc or not pdf_doc.get("path"):
                continue
            dest = os.path.join(settings.geometry_docs_dir, pdf_doc["path"])
            if os.path.exists(dest):
                stats["pdfs_skipped"] += 1
                continue
            url = f"{base_url}/api/v1/geometries/{geometry_id}/download-pdf"
            if _download_to(url, dest, token):
                stats["pdfs_downloaded"] += 1
    else:
        print("[file_sync] No PRODUCTION_API_TOKEN — skipping geometry PDFs")

    return stats


def sync_material_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"mss_downloaded": 0, "sds_downloaded": 0, "skipped": 0}

    if not token:
        print("[file_sync] No PRODUCTION_API_TOKEN — skipping material files")
        return stats

    remote_cursor.execute("SELECT id, mss_file_path, sds_file_path FROM materials")
    for row in remote_cursor.fetchall():
        material_id = str(row[0])
        mss_path = row[1]
        sds_path = row[2]

        if mss_path:
            dest = os.path.join(settings.material_docs_dir, mss_path)
            if os.path.exists(dest):
                stats["skipped"] += 1
            else:
                url = f"{base_url}/api/v1/materials/{material_id}/download/mss"
                if _download_to(url, dest, token):
                    stats["mss_downloaded"] += 1

        if sds_path:
            dest = os.path.join(settings.material_docs_dir, sds_path)
            if os.path.exists(dest):
                stats["skipped"] += 1
            else:
                url = f"{base_url}/api/v1/materials/{material_id}/download/sds"
                if _download_to(url, dest, token):
                    stats["sds_downloaded"] += 1

    return stats


def sync_vest_documents(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"documents_downloaded": 0, "skipped": 0}

    if not token:
        print("[file_sync] No PRODUCTION_API_TOKEN — skipping vest documents")
        return stats

    try:
        remote_cursor.execute("SELECT id, vest_id, file_path FROM model_documents")
    except Exception:
        print("[file_sync] model_documents table not found on remote — skipping")
        return stats

    for row in remote_cursor.fetchall():
        doc_id = str(row[0])
        vest_id = str(row[1])
        file_path = row[2]
        if not file_path:
            continue
        dest = os.path.join(settings.model_docs_dir, file_path)
        if os.path.exists(dest):
            stats["skipped"] += 1
            continue
        url = f"{base_url}/api/v1/vests/{vest_id}/documents/{doc_id}/download"
        if _download_to(url, dest, token):
            stats["documents_downloaded"] += 1

    return stats


def sync_all_files(remote_cursor, base_url: Optional[str] = None, token: Optional[str] = None) -> dict:
    base_url = base_url or settings.PRODUCTION_BACKEND_URL
    token = token or (settings.PRODUCTION_API_TOKEN or None)

    print(f"[file_sync] Starting file sync from {base_url}")
    results = {}
    results["geometry"] = sync_geometry_files(remote_cursor, base_url, token)
    results["materials"] = sync_material_files(remote_cursor, base_url, token)
    results["vest_documents"] = sync_vest_documents(remote_cursor, base_url, token)
    print(f"[file_sync] Done: {results}")
    return results
