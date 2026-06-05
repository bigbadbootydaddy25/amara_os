"""
SMB search — scans mounted Texhoma share for parcel 11-409-19 documents.
Searches: DOC LIBRARY, DEED BOOK, Doddridge Library, Old Farm Maps, Landmen
Copies matches to deed/output/server_docs/

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

from deed.config import PARCEL_ID, DISTRICT, COUNTY, OUTPUT_DIR

DEST_DIR = OUTPUT_DIR / "server_docs"

# Search terms — any file whose name contains one of these (case-insensitive) is a hit
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
]

# Folder names to search inside the share root
TARGET_FOLDERS = [
    "DOC LIBRARY",
    "DEED BOOK",
    "Doddridge Library",
    "Old Farm Maps",
    "Landmen",
]

# File extensions to collect (skip executables, system files)
COLLECT_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".txt", ".csv", ".xml", ".shp", ".kml",
    ".msg", ".eml",
}


def _find_mount() -> Path | None:
    """Locate the WVDA / TEXHOMA_DATA volume under /Volumes/."""
    volumes = Path("/Volumes")
    if not volumes.exists():
        return None

    candidates = []
    for vol in volumes.iterdir():
        name = vol.name.upper()
        if any(kw in name for kw in ["WVDA", "TEXHOMA", "DATA", "WVDATA"]):
            candidates.append(vol)

    if not candidates:
        log.warning("No WVDA/TEXHOMA volume found under /Volumes/")
        log.warning("Volumes present: %s", [v.name for v in volumes.iterdir()])
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Prefer most-specific match
    for pref in ["WVDATA", "TEXHOMA_DATA", "WVDA"]:
        for c in candidates:
            if pref in c.name.upper():
                return c
    return candidates[0]


def _is_hit(path: Path) -> bool:
    """Return True if the file name or any parent folder name matches search terms."""
    check = (path.name + " " + " ".join(p.name for p in path.parents)).lower()
    return any(term.lower() in check for term in SEARCH_TERMS)


def _collect_ext(path: Path) -> bool:
    return path.suffix.lower() in COLLECT_EXTS or path.suffix == ""


def search_folder(folder: Path, dest: Path) -> list[Path]:
    """Recursively search folder for matching files, copy to dest."""
    if not folder.exists():
        log.warning("  Folder not found: %s", folder)
        return []

    found = []
    log.info("  Scanning %s ...", folder)

    try:
        all_files = list(folder.rglob("*"))
    except PermissionError as e:
        log.warning("  Permission denied: %s", e)
        return []

    log.info("  %d total items in %s", len(all_files), folder.name)

    for f in all_files:
        if not f.is_file():
            continue
        if not _collect_ext(f):
            continue
        if _is_hit(f):
            # Preserve subfolder structure under dest
            try:
                rel = f.relative_to(folder)
            except ValueError:
                rel = Path(f.name)

            dst = dest / folder.name / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            if dst.exists() and dst.stat().st_size == f.stat().st_size:
                log.info("    SKIP (exists): %s", rel)
                found.append(dst)
                continue

            try:
                shutil.copy2(str(f), str(dst))
                log.info("    COPIED: %s", rel)
                found.append(dst)
            except Exception as e:
                log.warning("    Copy failed %s: %s", f.name, e)

    return found


def main():
    log.info("══════════════════════════════════════════════════")
    log.info("  SMB Search — Parcel %s | %s District | %s County", PARCEL_ID, DISTRICT, COUNTY)
    log.info("══════════════════════════════════════════════════")

    # 1. Find mount
    mount = _find_mount()
    if not mount:
        log.error("Share not mounted. In Finder: Go → Connect to Server → smb://WVDATA.TEXHOMALP.COM/DATA")
        sys.exit(1)

    log.info("Share mounted at: %s", mount)

    # Show top-level contents so we can confirm folder names
    log.info("Top-level folders:")
    try:
        tops = sorted(p.name for p in mount.iterdir() if p.is_dir())
        for t in tops:
            log.info("  %s", t)
    except Exception as e:
        log.warning("  Could not list root: %s", e)
        tops = []

    # 2. Search target folders
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    all_found: list[Path] = []

    for folder_name in TARGET_FOLDERS:
        # Try exact name first, then case-insensitive match
        folder = mount / folder_name
        if not folder.exists():
            match = next((mount / t for t in tops if t.lower() == folder_name.lower()), None)
            if match:
                folder = match
                log.info("Matched '%s' → '%s'", folder_name, folder.name)
            else:
                log.warning("Folder not found on share: '%s'", folder_name)
                continue

        hits = search_folder(folder, DEST_DIR)
        all_found.extend(hits)
        log.info("  → %d files from '%s'", len(hits), folder_name)

    # 3. Summary
    log.info("")
    log.info("══════════════════════════════════════════════════")
    log.info("  TOTAL FOUND: %d files", len(all_found))
    log.info("  Destination: %s", DEST_DIR)
    log.info("══════════════════════════════════════════════════")

    if all_found:
        log.info("Files copied:")
        for f in all_found:
            try:
                rel = f.relative_to(DEST_DIR)
            except ValueError:
                rel = f
            log.info("  %s", rel)
    else:
        log.info("No matching documents found.")
        log.info("Search terms used: %s", SEARCH_TERMS)
        log.info("Tip: if share folders have different names, check the list above and")
        log.info("     edit TARGET_FOLDERS in %s", __file__)

    return all_found


if __name__ == "__main__":
    main()
