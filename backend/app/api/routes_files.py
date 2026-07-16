"""File upload — saves to the local work dir (no cloud storage).

Once saved, the file becomes available to scan_work_dir / read_local_file /
auto_import_contacts / _parse_ics_local. Zero external API.
"""
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File as FastapiFile, status

from app.api.deps import CurrentUser, CurrentWorkspace, SessionDep
from app.jarvis import device_tools as _dt


router = APIRouter(prefix="/files", tags=["files"])


ALLOWED_EXT = {".ics", ".csv", ".vcf", ".txt", ".md", ".json", ".log",
               ".html", ".htm", ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/upload")
async def upload_file(
    session: SessionDep,
    user: CurrentUser,
    ws: CurrentWorkspace,
    file: Annotated[UploadFile, FastapiFile()],
) -> dict:
    root = _dt._get_work_dir()
    if root is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "work directory unavailable")
    name = Path(file.filename or "upload").name  # strip any path
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"extension '{ext}' not allowed")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 20 MB)")
    # Prevent overwrite: append (1), (2), ...
    target = root / name
    i = 1
    while target.exists():
        stem = Path(name).stem
        target = root / f"{stem} ({i}){ext}"
        i += 1
    target.write_bytes(content)
    return {
        "status": "ok",
        "name": target.name,
        "path": str(target.relative_to(root)),
        "size": len(content),
        "ext": ext,
        "importable": ext in {".csv", ".vcf"},
    }
