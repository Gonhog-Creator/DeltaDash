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


def sync_cover_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"pdfs_downloaded": 0, "pdfs_skipped": 0, "images_downloaded": 0, "images_skipped": 0}

    remote_cursor.execute("SELECT id, pdf_document, front_image, back_image FROM covers")
    for row in remote_cursor.fetchall():
        cover_id = str(row[0])

        # Sync PDF
        raw_pdf = row[1]
        if isinstance(raw_pdf, str):
            try:
                pdf_doc = json.loads(raw_pdf)
            except (json.JSONDecodeError, TypeError):
                pdf_doc = None
        elif isinstance(raw_pdf, dict):
            pdf_doc = raw_pdf
        else:
            pdf_doc = None

        if pdf_doc and pdf_doc.get("path"):
            dest = os.path.join(settings.cover_docs_dir, pdf_doc["path"])
            if os.path.exists(dest):
                stats["pdfs_skipped"] += 1
            else:
                url = f"{base_url}/api/v1/covers/{cover_id}/download-pdf"
                if _download_to(url, dest, token):
                    stats["pdfs_downloaded"] += 1

        # Sync front and back images
        for idx, field_name in enumerate(["front_image", "back_image"]):
            raw_img = row[2 + idx]
            if isinstance(raw_img, str):
                try:
                    img_doc = json.loads(raw_img)
                except (json.JSONDecodeError, TypeError):
                    img_doc = None
            elif isinstance(raw_img, dict):
                img_doc = raw_img
            else:
                img_doc = None

            if img_doc and img_doc.get("path"):
                dest = os.path.join(settings.cover_images_dir, img_doc["path"])
                if os.path.exists(dest):
                    stats["images_skipped"] += 1
                else:
                    side = field_name.replace("_image", "")
                    url = f"{base_url}/api/v1/covers/{cover_id}/download-image/{side}"
                    if _download_to(url, dest, token):
                        stats["images_downloaded"] += 1

    return stats


def sync_material_document_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"downloaded": 0, "skipped": 0}

    if not token:
        print("[file_sync] No PRODUCTION_API_TOKEN — skipping material document files")
        return stats

    try:
        remote_cursor.execute("SELECT id, stored_path FROM material_documents WHERE stored_path IS NOT NULL")
    except Exception:
        print("[file_sync] material_documents table not found on remote — skipping")
        return stats

    for row in remote_cursor.fetchall():
        doc_id = str(row[0])
        stored_path = row[1]
        if not stored_path:
            continue
        dest = os.path.join(settings.material_docs_dir, stored_path)
        if os.path.exists(dest):
            stats["skipped"] += 1
            continue
        url = f"{base_url}/api/v1/materials/documents/{doc_id}/download"
        if _download_to(url, dest, token):
            stats["downloaded"] += 1

    return stats


def sync_pliego_document_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"downloaded": 0, "skipped": 0}

    if not token:
        print("[file_sync] No PRODUCTION_API_TOKEN — skipping pliego document files")
        return stats

    try:
        remote_cursor.execute("SELECT id, file_path FROM pliego_documents WHERE file_path IS NOT NULL")
    except Exception:
        print("[file_sync] pliego_documents table not found on remote — skipping")
        return stats

    for row in remote_cursor.fetchall():
        doc_id = str(row[0])
        file_path = row[1]
        if not file_path:
            continue
        dest = os.path.join(settings.pliego_docs_dir, file_path)
        if os.path.exists(dest):
            stats["skipped"] += 1
            continue
        url = f"{base_url}/api/v1/pliego/documents/{doc_id}/download"
        if _download_to(url, dest, token):
            stats["downloaded"] += 1

    return stats


def sync_test_session_files(remote_cursor, base_url: str, token: Optional[str] = None) -> dict:
    stats = {"pdfs_downloaded": 0, "pdfs_skipped": 0, "images_downloaded": 0, "images_skipped": 0}

    try:
        remote_cursor.execute("SELECT id, pdf_documents, front_image, back_image FROM test_sessions")
    except Exception:
        print("[file_sync] test_sessions table not found on remote — skipping")
        return stats

    for row in remote_cursor.fetchall():
        session_id = str(row[0])

        # Sync PDFs (array)
        raw_pdfs = row[1]
        if isinstance(raw_pdfs, str):
            try:
                pdf_list = json.loads(raw_pdfs)
            except (json.JSONDecodeError, TypeError):
                pdf_list = None
        elif isinstance(raw_pdfs, list):
            pdf_list = raw_pdfs
        else:
            pdf_list = None

        if pdf_list:
            for pdf_doc in pdf_list:
                if pdf_doc and pdf_doc.get("path"):
                    dest = os.path.join(settings.test_session_docs_dir, pdf_doc["path"])
                    if os.path.exists(dest):
                        stats["pdfs_skipped"] += 1
                    else:
                        url = f"{base_url}/api/v1/test-sessions/{session_id}/download-pdf/0"
                        if _download_to(url, dest, token):
                            stats["pdfs_downloaded"] += 1

        # Sync front and back images
        for idx, field_name in enumerate(["front_image", "back_image"]):
            raw_img = row[2 + idx]
            if isinstance(raw_img, str):
                try:
                    img_doc = json.loads(raw_img)
                except (json.JSONDecodeError, TypeError):
                    img_doc = None
            elif isinstance(raw_img, dict):
                img_doc = raw_img
            else:
                img_doc = None

            if img_doc and img_doc.get("path"):
                dest = os.path.join(settings.test_session_images_dir, img_doc["path"])
                if os.path.exists(dest):
                    stats["images_skipped"] += 1
                else:
                    side = field_name.replace("_image", "")
                    url = f"{base_url}/api/v1/test-sessions/{session_id}/download-image/{side}"
                    if _download_to(url, dest, token):
                        stats["images_downloaded"] += 1

    return stats


def sync_all_files(remote_cursor, base_url: Optional[str] = None, token: Optional[str] = None) -> dict:
    base_url = base_url or settings.PRODUCTION_BACKEND_URL
    token = token or (settings.PRODUCTION_API_TOKEN or None)

    print(f"[file_sync] Starting file sync from {base_url}")
    results = {}
    results["geometry"] = sync_geometry_files(remote_cursor, base_url, token)
    results["materials"] = sync_material_files(remote_cursor, base_url, token)
    results["material_documents"] = sync_material_document_files(remote_cursor, base_url, token)
    results["vest_documents"] = sync_vest_documents(remote_cursor, base_url, token)
    results["covers"] = sync_cover_files(remote_cursor, base_url, token)
    results["pliego_documents"] = sync_pliego_document_files(remote_cursor, base_url, token)
    results["test_sessions"] = sync_test_session_files(remote_cursor, base_url, token)
    print(f"[file_sync] Done: {results}")
    return results
