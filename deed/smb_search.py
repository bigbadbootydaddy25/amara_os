"""
SMB search — scans /Volumes/DATA/ for parcel 11-409-19 documents.

Searches:
  DOC LIBRARY, DEED BOOK*, Old Farm Maps, Landmen, Doddridge Library,
  WV Curative Libraries, WV Tax Maps, Scans, WV Middle Team, DATA/

Also reads DEED BOOK (208-324)324-325.pdf directly and logs its presence.

Copies all hits to deed/output/server_docs/

Usage: cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/smb_search.py
"""
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("SMB_SEARCH")

from deed.config import PARCEL_ID, DISTRICT, COUNTY, OUTPUT_DIR, SMB_MOUNT

DEST_DIR = OUTPUT_DIR / "server_docs"

SEARCH_TERMS = [
    "11-409-19",
    "11409-19",
    "1140919",
    "11_409_19",
    "409-19",
    "40919",
    "harrison",
    "elk",
    "strunk",
    "118 acres",
    "118acres",
]

# All target folders — searched recursively
TARGET_FOLDERS = [
    "DOC LIBRARY",
    "Old Farm Maps",
    "Landmen",
    "Doddridge Library",
    "WV Curative Libraries",
    "WV Tax Maps",
    "Scans",
    "WV Middle Team",
    "DATA",          # /Volumes/DATA/DATA/ subfolder
]

# DEED BOOK folder — may contain spaces/parens; handle separately
DEED_BOOK_PREFIX = "DEED BOOK"

# Known specific file to inspect
SPECIFIC_FILE = "DEED BOOK (208-324)324-325.pdf"

COLLECT_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".txt", ".csv", ".xml", ".shp", ".kml", ".kmz",
    ".msg", ".eml", ".ppt", ".pptx",
}


def _is_hit(path: Path, mount: Path) -> bool:
    """True if file name or any relative path component matches a search term."""
    try:
        rel = str(path.relative_to(mount)).lower()
    except ValueError:
        rel = path.name.lower()
    return any(t.lower() in rel for t in SEARCH_TERMS)


def _copy(src: Path, dest_root: Path, label: str) -> Path | None:
    if not src.is_file():
        return None
    try:
        rel = src.relative_to(SMB_MOUNT)
    except ValueError:
        rel = Path(label) / src.name

    dst = dest_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        log.info("    SKIP (exists): %s", rel)
        return dst

    try:
        shutil.copy2(str(src), str(dst))
        log.info("    COPIED: %s", rel)
        return dst
    except Exception as e:
        log.warning("    Copy failed %s: %s", src.name, e)
        return None


def search_folder(folder: Path, dest: Path) -> list[Path]:
    if not folder.exists():
        log.warning("  Not found: %s", folder)
        return []

    log.info("  Scanning: %s", folder)
    found = []
    try:
        all_files = [f for f in folder.rglob("*") if f.is_file()]
    except PermissionError as e:
        log.warning("  Permission denied: %s", e)
        return []

    log.info("  %d files in '%s'", len(all_files), folder.name)
    for f in all_files:
        if f.suffix.lower() not in COLLECT_EXTS and f.suffix != "":
            continue
        if _is_hit(f, SMB_MOUNT):
            hit = _copy(f, dest, folder.name)
            if hit:
                found.append(hit)

    return found


def find_deed_book_folders(mount: Path) -> list[Path]:
    """Find all folders starting with 'DEED BOOK' (case-insensitive)."""
    folders = []
    try:
        for p in mount.iterdir():
            if p.is_dir() and p.name.upper().startswith(DEED_BOOK_PREFIX.upper()):
                folders.append(p)
    except Exception as e:
        log.warning("Cannot list root: %s", e)
    return folders


def inspect_specific_file(mount: Path, dest: Path) -> Path | None:
    """Check for DEED BOOK (208-324)324-325.pdf and copy it regardless of search-term match."""
    for folder in find_deed_book_folders(mount):
        candidate = folder / SPECIFIC_FILE
        if candidate.exists():
            log.info("  SPECIFIC FILE FOUND: %s", candidate)
            return _copy(candidate, dest, "DEED BOOK")
        # Also try direct root
    direct = mount / SPECIFIC_FILE
    if direct.exists():
        log.info("  SPECIFIC FILE FOUND (root): %s", direct)
        return _copy(direct, dest, "DEED BOOK")
    log.info("  Specific file not found at direct path — will catch via folder scan")
    return None


def main():
    mount = SMB_MOUNT
    log.info("══════════════════════════════════════════════════════")
    log.info("  SMB Search  |  Parcel %s  |  %s District  |  %s Co", PARCEL_ID, DISTRICT, COUNTY)
    log.info("  Mount:  %s", mount)
    log.info("══════════════════════════════════════════════════════")

    if not mount.exists():
        log.error("Share not mounted at %s", mount)
        log.error("Mount first: open 'smb://SSchufford@WVDATA.TEXHOMALP.COM/DATA'")
        sys.exit(1)

    # Show root contents
    log.info("Root contents of %s:", mount)
    try:
        tops = sorted(p.name for p in mount.iterdir())
        for t in tops:
            log.info("  %s", t)
    except Exception as e:
        log.warning("Cannot list root: %s", e)
        tops = []

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    all_found: list[Path] = []

    # 1. Check specific deed book file first
    log.info("")
    log.info("── Specific file check ──")
    sf = inspect_specific_file(mount, DEST_DIR)
    if sf:
        all_found.append(sf)

    # 2. Search all DEED BOOK folders
    log.info("")
    log.info("── DEED BOOK folders ──")
    for db_folder in find_deed_book_folders(mount):
        hits = search_folder(db_folder, DEST_DIR)
        all_found.extend(hits)
        log.info("  → %d hits from '%s'", len(hits), db_folder.name)

    # 3. Search remaining target folders
    log.info("")
    log.info("── Target folders ──")
    for folder_name in TARGET_FOLDERS:
        folder = mount / folder_name
        if not folder.exists():
            # Case-insensitive match
            match = next(
                (mount / t for t in tops if t.lower() == folder_name.lower()),
                None,
            )
            if match:
                folder = match
                log.info("Matched '%s' → '%s'", folder_name, folder.name)
            else:
                log.warning("Not found on share: '%s'", folder_name)
                continue

        hits = search_folder(folder, DEST_DIR)
        all_found.extend(hits)
        log.info("  → %d hits from '%s'", len(hits), folder_name)

    # Deduplicate by resolved path
    seen = set()
    unique = []
    for f in all_found:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(f)
    all_found = unique

    # Summary
    log.info("")
    log.info("══════════════════════════════════════════════════════")
    log.info("  TOTAL: %d files copied → %s", len(all_found), DEST_DIR)
    log.info("══════════════════════════════════════════════════════")
    if all_found:
        for f in all_found:
            try:
                rel = f.relative_to(DEST_DIR)
            except ValueError:
                rel = f
            log.info("  %s", rel)
    else:
        log.info("  No matching documents found.")
        log.info("  Search terms: %s", SEARCH_TERMS)

    return all_found


if __name__ == "__main__":
    main()
