"""
Regression tests for the encoding-resilient CSV reader in ownership-graph/run.py.

Tests cover:
- utf-8-sig BOM files succeed on first attempt
- utf-8 files succeed on second attempt
- cp1252 files (byte 0x97 em dash) succeed after failing utf-8-sig and utf-8
- Files undecodable in all four encodings are skipped with a reason
- ingest_csv_dir() never raises on bad files
- JSON report includes skipped_files and encoding_used sections
- Non-CSV files in the directory are recorded as skipped
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

# Add the agent directory to sys.path so we can import run.py
AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from run import (
    ENCODINGS,
    FileResult,
    ingest_csv_dir,
    read_csv_rows,
    write_reports,
    build_graph,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _write_csv(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _csv_bytes(rows: list[dict], encoding: str, bom: bool = False) -> bytes:
    """Serialise a list of dicts to CSV bytes in the given encoding."""
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    raw = buf.getvalue().encode(encoding)
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    return raw


# ─── ENCODINGS constant ───────────────────────────────────────────────────────

def test_encoding_order():
    assert ENCODINGS == ("utf-8-sig", "utf-8", "cp1252", "latin-1")


# ─── read_csv_rows: success paths ─────────────────────────────────────────────

def test_utf8_sig_bom_succeeds_first(tmp_path):
    """BOM file should be read on the first (utf-8-sig) attempt."""
    rows = [{"owner": "Alice Smith", "address": "123 Main St"}]
    path = _write_csv(tmp_path, "bom.csv", _csv_bytes(rows, "utf-8", bom=True))

    result = read_csv_rows(path)

    assert result.skipped is False
    assert result.encoding_used == "utf-8-sig"
    assert len(result.rows) == 1
    assert result.rows[0]["owner"] == "Alice Smith"


def test_plain_utf8_succeeds(tmp_path):
    """Plain UTF-8 file (no BOM) is read with the utf-8 encoding."""
    rows = [{"owner": "Bob Jones", "address": "456 Oak Ave"}]
    path = _write_csv(tmp_path, "plain.csv", _csv_bytes(rows, "utf-8"))

    result = read_csv_rows(path)

    assert result.skipped is False
    # utf-8-sig also decodes plain utf-8 correctly (transparent to BOM), so
    # the encoding reported is whichever comes first that succeeds.
    assert result.encoding_used in ("utf-8-sig", "utf-8")
    assert result.rows[0]["owner"] == "Bob Jones"


def test_cp1252_em_dash_regression(tmp_path):
    """
    Regression: byte 0x97 (cp1252 em dash) is invalid UTF-8.
    utf-8-sig and utf-8 must fail; cp1252 must succeed.
    """
    # Build CSV header + one data row with an em dash in the owner name.
    # 0x97 is the cp1252 encoding of em dash (U+2014); it is not valid UTF-8.
    header = b"owner,address\r\n"
    value  = b"Smith\x97Jones,789 Elm St\r\n"
    path   = _write_csv(tmp_path, "cp1252.csv", header + value)

    # Verify the byte is genuinely not valid UTF-8
    with pytest.raises(UnicodeDecodeError):
        (header + value).decode("utf-8")

    result = read_csv_rows(path)

    assert result.skipped is False, f"Expected success, got skip: {result.skip_reason}"
    assert result.encoding_used == "cp1252"
    assert len(result.rows) == 1
    assert "Smith" in result.rows[0]["owner"]


def test_latin1_fallback(tmp_path):
    """
    Byte 0x96 (cp1252 en dash) is also invalid UTF-8.
    latin-1 (which maps every byte) should be the final fallback if cp1252
    rejects it — though in practice cp1252 and latin-1 agree on 0x96.
    The key contract: result is NOT skipped.
    """
    header = b"owner,address\r\n"
    # 0x96 = cp1252 en dash; valid in both cp1252 and latin-1
    value  = b"Test\x96Owner,100 Pine Rd\r\n"
    path   = _write_csv(tmp_path, "latin1.csv", header + value)

    result = read_csv_rows(path)

    assert result.skipped is False
    assert result.encoding_used in ("cp1252", "latin-1")


# ─── read_csv_rows: failure paths ─────────────────────────────────────────────

def test_all_encodings_fail_returns_skipped(tmp_path):
    """
    A file with bytes that are invalid in all four encodings must be skipped
    with a descriptive reason — not raise.
    """
    # latin-1 is an 8-bit encoding that accepts every byte value, so it is
    # impossible to produce a byte sequence it rejects.  Instead, we use a
    # surrogate escape sequence that Python's strict mode rejects.
    # We patch the ENCODINGS tuple by monkeypatching the module so we can
    # test the "all fail" branch without finding a genuinely undecodable byte.
    import run as run_module

    original = run_module.ENCODINGS
    try:
        # Use two encodings that will both reject the cp1252 em dash
        run_module.ENCODINGS = ("utf-8-sig", "utf-8")  # type: ignore[attr-defined]

        header = b"owner,address\r\n"
        value  = b"Smith\x97Jones,789 Elm St\r\n"
        path   = _write_csv(tmp_path, "bad.csv", header + value)

        result = run_module.read_csv_rows(path)

        assert result.skipped is True
        assert result.skip_reason is not None
        assert "could not decode" in result.skip_reason
        assert result.rows == []
    finally:
        run_module.ENCODINGS = original  # type: ignore[attr-defined]


def test_nonexistent_file_returns_skipped():
    """Missing file must not raise — return a skipped FileResult."""
    path = Path("/tmp/does_not_exist_ownership_graph.csv")
    result = read_csv_rows(path)
    assert result.skipped is True
    assert result.skip_reason is not None


# ─── ingest_csv_dir ───────────────────────────────────────────────────────────

def test_ingest_dir_does_not_crash_on_bad_file(tmp_path):
    """ingest_csv_dir must not raise when a file cannot be decoded."""
    # Good file
    good = [{"owner": "Alice LLC", "property address": "1 Main St"}]
    _write_csv(tmp_path, "good.csv", _csv_bytes(good, "utf-8"))

    # Bad file — patch encodings to force all-fail
    import run as run_module
    original = run_module.ENCODINGS
    try:
        run_module.ENCODINGS = ("utf-8-sig", "utf-8")  # type: ignore[attr-defined]
        _write_csv(tmp_path, "bad.csv", b"owner,address\r\nSmith\x97Jones,789 Elm\r\n")

        edges, skipped = run_module.ingest_csv_dir(tmp_path)
    finally:
        run_module.ENCODINGS = original  # type: ignore[attr-defined]

    # Should not raise; bad file ends up in skipped
    bad_names = [Path(r.path).name for r in skipped if r.skipped]
    assert "bad.csv" in bad_names


def test_ingest_dir_skips_non_csv(tmp_path):
    """Non-CSV files in the raw directory are recorded as skipped."""
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "data.xlsx").write_bytes(b"\x50\x4b\x03\x04")  # zip magic

    edges, skipped = ingest_csv_dir(tmp_path)

    skipped_names = {Path(r.path).name for r in skipped}
    assert "readme.txt" in skipped_names
    assert "data.xlsx" in skipped_names
    assert edges == []


def test_ingest_dir_missing_dir_returns_empty():
    """ingest_csv_dir on a non-existent directory returns empty lists."""
    edges, skipped = ingest_csv_dir(Path("/tmp/no_such_dir_ownership"))
    assert edges == []
    assert skipped == []


def test_ingest_dir_cp1252_file_produces_edges(tmp_path):
    """A cp1252-encoded CSV with ownership headers is ingested without error."""
    header = b"owner,property address,sale price\r\n"
    value  = b"Smith\x97LLC,123 Oak St,250000\r\n"
    _write_csv(tmp_path, "cp1252_owners.csv", header + value)

    edges, skipped = ingest_csv_dir(tmp_path)

    assert any("Smith" in (e.owner_name or "") or "Smith" in (e.owner_entity or "")
               for e in edges), "Expected at least one edge from cp1252 file"


# ─── JSON report: skipped_files and encoding_used ─────────────────────────────

def test_json_report_contains_skipped_files_section(tmp_path):
    """OWNERSHIP_GRAPH.json must contain a 'skipped_files' key."""
    reports_dir = tmp_path / "reports"
    workspace   = tmp_path

    skipped = [
        FileResult(path=str(tmp_path / "bad.csv"), skipped=True,
                   skip_reason="could not decode with any of: utf-8-sig, utf-8, cp1252, latin-1")
    ]
    file_results: list[FileResult] = []
    graph: dict = {}

    write_reports(graph, skipped, file_results, reports_dir, workspace)

    payload = json.loads((reports_dir / "OWNERSHIP_GRAPH.json").read_text())
    assert "skipped_files" in payload
    assert isinstance(payload["skipped_files"], list)
    assert payload["skipped_files"][0]["file"] == "bad.csv"
    assert "could not decode" in payload["skipped_files"][0]["reason"]


def test_json_report_contains_encoding_used_section(tmp_path):
    """OWNERSHIP_GRAPH.json must contain an 'encoding_used' key."""
    reports_dir = tmp_path / "reports"
    workspace   = tmp_path

    file_results = [
        FileResult(path=str(tmp_path / "good.csv"), encoding_used="cp1252",
                   rows=[{"owner": "Test LLC"}])
    ]
    skipped: list[FileResult] = []
    graph: dict = {}

    write_reports(graph, skipped, file_results, reports_dir, workspace)

    payload = json.loads((reports_dir / "OWNERSHIP_GRAPH.json").read_text())
    assert "encoding_used" in payload
    assert isinstance(payload["encoding_used"], list)
    assert payload["encoding_used"][0]["file"] == "good.csv"
    assert payload["encoding_used"][0]["encoding"] == "cp1252"


def test_md_report_contains_skipped_files_section(tmp_path):
    """OWNERSHIP_GRAPH.md must include a '## Skipped Files' section."""
    reports_dir = tmp_path / "reports"
    workspace   = tmp_path

    skipped = [
        FileResult(path=str(tmp_path / "corrupt.csv"), skipped=True,
                   skip_reason="could not decode with any of: utf-8-sig, utf-8, cp1252, latin-1")
    ]
    write_reports({}, skipped, [], reports_dir, workspace)

    md = (reports_dir / "OWNERSHIP_GRAPH.md").read_text()
    assert "## Skipped Files" in md
    assert "corrupt.csv" in md


def test_md_report_contains_encoding_section(tmp_path):
    """OWNERSHIP_GRAPH.md must include a '## Encoding Used Per File' section."""
    reports_dir = tmp_path / "reports"
    workspace   = tmp_path

    file_results = [
        FileResult(path=str(tmp_path / "ok.csv"), encoding_used="utf-8", rows=[])
    ]
    write_reports({}, [], file_results, reports_dir, workspace)

    md = (reports_dir / "OWNERSHIP_GRAPH.md").read_text()
    assert "## Encoding Used Per File" in md
    assert "ok.csv" in md


# ─── end-to-end: cp1252 file survives the full pipeline ──────────────────────

def test_full_pipeline_with_cp1252_file(tmp_path):
    """
    End-to-end: a directory containing only a cp1252 CSV with byte 0x97
    produces a graph with at least one owner and an OWNERSHIP_GRAPH.json
    that lists the file under encoding_used with encoding='cp1252'.
    """
    raw_dir     = tmp_path / "raw"
    reports_dir = tmp_path / "reports"
    raw_dir.mkdir()

    header = b"owner,property address,sale price\r\n"
    value  = b"Smith\x97Brothers LLC,42 Willow Way,175000\r\n"
    _write_csv(raw_dir, "deeds.csv", header + value)

    edges, skipped = ingest_csv_dir(raw_dir)
    assert edges, "Expected edges from cp1252 CSV"
    assert not any(r.path.endswith("deeds.csv") for r in skipped)

    # Collect file_results the same way main() does
    from run import read_csv_rows
    file_results = []
    for entry in sorted(raw_dir.iterdir()):
        if entry.suffix.lower() == ".csv" and not entry.name.startswith((".", "_")):
            r = read_csv_rows(entry)
            if not r.skipped:
                file_results.append(r)

    graph = build_graph(edges)
    write_reports(graph, skipped, file_results, reports_dir, tmp_path)

    payload = json.loads((reports_dir / "OWNERSHIP_GRAPH.json").read_text())
    enc_files = {e["file"]: e["encoding"] for e in payload["encoding_used"]}
    assert "deeds.csv" in enc_files
    assert enc_files["deeds.csv"] == "cp1252"
    assert payload["owner_count"] >= 1
