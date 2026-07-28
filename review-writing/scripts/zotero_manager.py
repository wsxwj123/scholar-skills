#!/usr/bin/env python3
from __future__ import annotations  # lazy annotation evaluation — allows zotero.Zotero hints without top-level import
import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
"""
zotero_manager.py — PyZotero Web API wrapper for general-review-writing skill.

Credentials: saved once, reused automatically.
  python3 zotero_manager.py save-credentials --lib-id X --api-key Y
  -> stored in ~/.config/academic-skills/zotero.json (chmod 600, never in git).
  After that, --lib-id/--api-key are optional on every command.
  Priority: CLI flags > saved config > prompt to save once.

Usage:
  python3 zotero_manager.py --status
  python3 zotero_manager.py --init --title "T" --outline outline.md
  python3 zotero_manager.py --add-batch --section "2.1" --papers tmp/papers_2_1.json --root-key ROOT_KEY --index data/literature_index.json --lib-id X --api-key Y
  python3 zotero_manager.py --dedup --scope ROOT_KEY --lib-id X --api-key Y   # repair only
  python3 zotero_manager.py --get-section "2.1" --lib-id X --api-key Y
  python3 zotero_manager.py --export-bibtex --output refs.bib --lib-id X --api-key Y
"""

import argparse
import json
import os
import re
import sys
import time
import tempfile
import urllib.request
import urllib.error
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# pyzotero is imported lazily inside connect() so --help works without it installed


# ─────────────────────────────────────────────
# Credential persistence
# ─────────────────────────────────────────────
# Stored outside the skill repo (never enters git), 700 dir / 600 file.
CREDENTIALS_PATH = Path.home() / ".config" / "academic-skills" / "zotero.json"


def _mask(api_key: str) -> str:
    """Never echo an API key in full — show only the last 4 chars for logs."""
    return f"****{api_key[-4:]}" if api_key and len(api_key) >= 4 else "****"


def load_credentials(path: Path = CREDENTIALS_PATH) -> Optional[dict]:
    """Read persisted Zotero credentials, or None if the file is absent/unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return None


def save_credentials(lib_id: str, api_key: str, path: Path = CREDENTIALS_PATH) -> None:
    """Persist credentials with restrictive perms (dir 700, file 600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    data = {"library_id": lib_id, "api_key": api_key, "library_type": "user"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)


def resolve_credentials(cli_lib_id: Optional[str], cli_api_key: Optional[str]) -> Tuple[str, str]:
    """Resolve credentials by priority: CLI args > config file > prompt-and-exit.

    Returns (lib_id, api_key). Exits with clear guidance if neither source has them.
    """
    lib_id, api_key = cli_lib_id, cli_api_key
    if not (lib_id and api_key):
        cfg = load_credentials(CREDENTIALS_PATH) or {}
        lib_id = lib_id or cfg.get("library_id")
        api_key = api_key or cfg.get("api_key")
    if not (lib_id and api_key):
        sys.exit(
            "❌ 未找到 Zotero 凭据。请先保存一次（之后自动复用）：\n"
            "   1. 打开 https://www.zotero.org/settings/keys 获取 userID 和 API key\n"
            "      （API key 需勾选 Allow write access 写权限）\n"
            "   2. 运行：python3 zotero_manager.py save-credentials --lib-id <userID> --api-key <API_KEY>\n"
            f"   凭据将安全存于 {CREDENTIALS_PATH}（权限 600，不入 git）。"
        )
    return lib_id, api_key


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────

def connect(lib_id: str, api_key: str):
    """Create and return a Zotero Web API connection."""
    try:
        from pyzotero import zotero as _zotero
    except ImportError:
        sys.exit("❌ pyzotero not installed. Run: pip install pyzotero")
    return _zotero.Zotero(lib_id, "user", api_key)


# ─────────────────────────────────────────────
# --status
# ─────────────────────────────────────────────

def cmd_status(zot: zotero.Zotero, json_out: bool = False, find_root_title: Optional[str] = None) -> None:
    """Test connection and list top-level collections.

    If `json_out` is True, emit a machine-readable JSON document instead of human prose —
    useful for the AI to detect whether a project's root collection already exists.

    If `find_root_title` is provided, behave as an exact-match lookup:
      - exit 0 + print the single matching collection key when exactly one top-level
        collection has that name (machine-parseable)
      - exit 4 + print all candidate keys when multiple collections share the name
      - exit 3 (silent) when no match — caller should then run --init
    """
    try:
        collections = zot.collections()
    except Exception as e:
        sys.exit(f"❌ Connection failed: {e}")

    if find_root_title is not None:
        target = find_root_title.strip()
        matches = [c for c in collections if c["data"]["name"].strip() == target]
        if len(matches) == 1:
            print(matches[0]["key"])
            return
        if len(matches) > 1:
            for c in matches:
                print(c["key"])
            sys.exit(4)
        sys.exit(3)

    if json_out:
        payload = {
            "library_id": zot.library_id,
            "total_items": zot.count_items(),
            "top_level_collections": [
                {"key": c["key"], "name": c["data"]["name"]} for c in collections
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"✅ Connected to Zotero library (user ID: {zot.library_id})")
    print(f"   Total items: {zot.count_items()}")
    print(f"   Top-level collections ({len(collections)}):")
    for col in collections:
        print(f"     [{col['key']}] {col['data']['name']}")


# ─────────────────────────────────────────────
# --init
# ─────────────────────────────────────────────

def _parse_outline_sections(outline_path: str) -> List[Dict]:
    """
    Parse outline.md and extract section hierarchy (≤2 levels).

    Heading-level agnostic: identifies section level by the ID pattern (`N.` → level 1,
    `N.M` → level 2), NOT by `#` count. This way the parser works whether the outline uses
    `##`/`###` (Polish Mode rebuild from imported draft, common case) or `###`/`####` (the
    Write Mode template). Plain markdown labels like `## Outline (filled after...)` are
    ignored because they lack a numeric `N.` prefix.

    Returns list of {"level": 1|2, "id": "1.1", "name": "Background"}.
    """
    sections = []
    # Order matters: try the more specific level-2 pattern first (N.M), fallback to level-1 (N.)
    level2_pattern = re.compile(r"^#{2,}\s+(\d+\.\d+(?:\.\d+)*)\s+(.+)$")
    level1_pattern = re.compile(r"^#{2,}\s+(\d+)\.\s+(.+)$")

    with open(outline_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            m2 = level2_pattern.match(line)
            if m2:
                sections.append({"level": 2, "id": m2.group(1), "name": m2.group(2).strip()})
                continue
            m1 = level1_pattern.match(line)
            if m1:
                sections.append({"level": 1, "id": m1.group(1), "name": m1.group(2).strip()})
    return sections


def _create_collection(zot: zotero.Zotero, name: str, parent_key: Optional[str] = None) -> str:
    """Create a Zotero collection and return its key."""
    payload = {"name": name}
    if parent_key:
        payload["parentCollection"] = parent_key
    result = zot.create_collections([payload])
    # pyzotero returns {'success': {0: 'KEY'} or {'0': 'KEY'}, ...} (key may be int or str)
    success = result.get("success", {})
    key = success.get(0) or success.get("0")
    if not key:
        raise RuntimeError(f"Failed to create collection '{name}': {result}")
    time.sleep(0.5)  # respect rate limit
    return key


def cmd_init(zot: zotero.Zotero, title: str, outline_path: str) -> None:
    """Create root collection + subcollections from outline.md."""
    sections = _parse_outline_sections(outline_path)
    if not sections:
        sys.exit(
            "❌ No sections found in outline.md. "
            "Each section needs a numeric prefix under a ## or deeper heading, e.g. "
            "'## 1. Introduction' or '### 1.1 Background' (heading depth flexible; "
            "ID pattern `N.` / `N.M` is what matters)."
        )

    print(f"Creating root collection: '{title}'")
    root_key = _create_collection(zot, title)
    print(f"  ✅ Root key: {root_key}")

    # Track level-1 collection keys for parenting level-2 sections
    level1_keys: Dict[str, str] = {}

    for sec in sections:
        col_name = f"{sec['id']}. {sec['name']}"
        if sec["level"] == 1:
            key = _create_collection(zot, col_name, parent_key=root_key)
            level1_keys[sec["id"]] = key
            print(f"  ✅ [{key}] {col_name}")
        else:
            parent_id = sec["id"].rsplit(".", 1)[0]  # "1.2" → "1"
            parent_key = level1_keys.get(parent_id, root_key)
            key = _create_collection(zot, col_name, parent_key=parent_key)
            print(f"    ✅ [{key}] {col_name}")

    print(f"\nZotero collection tree created. Root key: {root_key}")
    print("Add this to outline.md → 'Zotero root collection key:'")


# ─────────────────────────────────────────────
# --add-batch
# ─────────────────────────────────────────────

def _find_collection_by_section(
    zot: zotero.Zotero,
    section_id: str,
    root_key: Optional[str] = None,
) -> Optional[str]:
    """Find collection key for a given section ID (e.g. '2.1').

    If root_key is provided, the search is scoped to descendants of that collection,
    preventing cross-project contamination when multiple reviews share similar section names.
    """
    all_cols = zot.everything(zot.collections())

    # Build set of keys that are descendants of root_key (recursive via parentCollection field)
    if root_key:
        def _descendants(parent: str) -> Set[str]:
            result: Set[str] = set()
            for col in all_cols:
                if col["data"].get("parentCollection") == parent:
                    k = col["key"]
                    result.add(k)
                    result |= _descendants(k)
            return result
        scoped: Optional[Set[str]] = _descendants(root_key)
    else:
        scoped = None

    for col in all_cols:
        if scoped is not None and col["key"] not in scoped:
            continue
        name = col["data"]["name"]
        # Use regex word boundary to avoid prefix collisions (e.g. "1.1" matching "1.10")
        if name == section_id or re.match(rf"^{re.escape(section_id)}(?:\.\s|\s)", name):
            return col["key"]
    return None


def _build_item_template(
    paper: dict,
    collection_keys: Optional[List[str]] = None,
    gid: Optional[int] = None,
) -> dict:
    """Build a Zotero journalArticle item from paper dict."""
    authors = []
    for a in paper.get("authors", []):
        if isinstance(a, str):
            a = a.strip()
            if "," in a:
                last, _, first = a.partition(",")
                last, first = last.strip(), first.strip()
            else:
                parts = a.split()
                # "First Last" format: last word is surname (Western convention)
                last = parts[-1] if parts else a
                first = " ".join(parts[:-1]) if len(parts) > 1 else ""
            authors.append({"creatorType": "author", "firstName": first, "lastName": last})
        elif isinstance(a, dict):
            authors.append({
                "creatorType": "author",
                "firstName": a.get("first", a.get("firstName", "")),
                "lastName": a.get("last", a.get("lastName", a.get("name", ""))),
            })

    tags = [{"tag": f"gid:{gid}"}] if gid is not None else []

    item = {
        "itemType": "journalArticle",
        "title": paper.get("title", ""),
        "creators": authors,
        "abstractNote": paper.get("abstract", ""),
        "date": str(paper.get("year", "")),
        "DOI": paper.get("doi", ""),
        "url": paper.get("url", ""),
        "publicationTitle": paper.get("journal", paper.get("source", "")),
        "tags": tags,
        "collections": collection_keys or [],
    }
    return item


# ─────────────────────────────────────────────
# Local index helpers (for safe dedup-at-write)
# ─────────────────────────────────────────────

def _load_local_index(index_path: str) -> List[dict]:
    """Load literature_index.json. Returns [] if missing or corrupt."""
    p = Path(index_path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_local_index(index_path: str, records: List[dict]) -> None:
    """Atomic write to literature_index.json via temp file."""
    p = Path(index_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _next_gid(index: List[dict]) -> int:
    """Return next available global_id (max existing + 1, minimum 1)."""
    existing = [r["global_id"] for r in index if isinstance(r.get("global_id"), int)]
    return (max(existing) + 1) if existing else 1


def _match_in_index(paper: dict, index: List[dict]) -> Optional[dict]:
    """Find matching record in local index by DOI exact or title fuzzy ≥0.85."""
    doi = (paper.get("doi") or "").strip().lower()
    title_norm = _normalize_title(paper.get("title", ""))
    for rec in index:
        rec_doi = (rec.get("doi") or "").strip().lower()
        if doi and rec_doi and doi == rec_doi:
            return rec
        rec_title = _normalize_title(rec.get("title", ""))
        if title_norm and rec_title:
            if SequenceMatcher(None, title_norm, rec_title).ratio() >= 0.85:
                return rec
    return None


def _add_item_to_collection(zot: "zotero.Zotero", item_key: str, col_key: str) -> None:
    """Add an existing Zotero item to a collection (non-destructive)."""
    item = zot.item(item_key)
    existing_cols: List[str] = item["data"].get("collections", [])
    if col_key not in existing_cols:
        item["data"]["collections"] = existing_cols + [col_key]
        zot.update_item(item)
        time.sleep(0.3)


def _fetch_oa_pdf_url(doi: str, email: Optional[str] = None) -> Optional[str]:
    """Query Unpaywall for OA PDF URL. Returns URL string or None."""
    if not doi:
        return None
    # Unpaywall requires a real email; fall back to generic if not provided
    addr = email or os.environ.get("UNPAYWALL_EMAIL", "unpaywall@example.edu")
    url = f"https://api.unpaywall.org/v2/{doi}?email={addr}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "review-tool/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        loc = data.get("best_oa_location") or {}
        return loc.get("url_for_pdf")
    except Exception:
        return None


def _download_pdf(pdf_url: str, dest_path: str) -> bool:
    """Download PDF from url to dest_path. Returns True on success."""
    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "review-tool/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception:
        return False


def cmd_add_batch(
    zot: "zotero.Zotero",
    section_id: str,
    papers_path: str,
    index_path: str,
    root_key: str,
) -> None:
    """
    Safe batch insert with dedup-at-write-time using local literature_index.json.

    For each paper in papers.json:
      - If already in local index (DOI exact or title fuzzy ≥0.85):
          Add the EXISTING Zotero item to the section collection only (no new item created).
      - If new:
          Create ONE item in [root_collection + section_collection] simultaneously.
          Tag gid:N at creation. Append to local index.

    This guarantees each canonical paper has exactly one Zotero item and one gid.
    --dedup is NOT needed in normal workflow; use it only for repair.
    """
    with open(papers_path, encoding="utf-8") as f:
        papers = json.load(f)

    if not papers:
        print("⚠️  papers.json is empty.")
        return

    col_key = _find_collection_by_section(zot, section_id, root_key)
    if not col_key:
        sys.exit(f"❌ Collection for section '{section_id}' not found within root collection '{root_key}'. Run --init first.")

    index = _load_local_index(index_path)
    new_count = existing_count = pdf_ok = pdf_missing = pdf_fail = 0

    print(f"Processing {len(papers)} papers for section {section_id}...")

    for paper in papers:
        match = _match_in_index(paper, index)

        if match and match.get("zotero_key"):
            # Already in Zotero — link to section collection + backfill missing metadata
            try:
                _add_item_to_collection(zot, match["zotero_key"], col_key)
            except Exception as e:
                print(f"  ⚠️  Could not link existing item {match['zotero_key']}: {e}")
            backfilled = _backfill_existing_metadata(zot, match["zotero_key"], match, paper)
            sections = match.setdefault("related_sections", [])
            if section_id not in sections:
                sections.append(section_id)
            existing_count += 1
            tag = "↩️ " if not backfilled else "🔧"
            print(f"  {tag} [gid:{match.get('global_id')}] {'backfilled metadata: ' if backfilled else 'already exists: '}{paper.get('title', '')[:70]}")
            continue

        # Create Zotero item — either brand new or local-index-only (no zotero_key yet)
        # Reuse existing global_id if record already in local index; otherwise assign new
        existing_gid = match.get("global_id") if match else None
        gid = existing_gid if existing_gid is not None else _next_gid(index)
        template = _build_item_template(paper, collection_keys=[root_key, col_key], gid=gid)

        try:
            result = zot.create_items([template])
            created_keys = list(result.get("success", {}).values())
            time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ Failed to create item: {e}")
            continue

        if not created_keys:
            print(f"  ❌ No key returned for: {paper.get('title', '')[:70]}")
            continue

        item_key = created_keys[0]

        # Belt-and-suspenders: explicitly assign to both root and section collections
        # create_items() with 'collections' in template is not guaranteed to be honored by the API;
        # update_item via _add_item_to_collection is authoritative and idempotent.
        time.sleep(0.2)
        _add_item_to_collection(zot, item_key, root_key)
        _add_item_to_collection(zot, item_key, col_key)

        # Abstract child note
        abstract = paper.get("abstract", "").strip()
        if abstract:
            note = {
                "itemType": "note",
                "parentItem": item_key,
                "note": f"<b>Abstract</b><br/>{abstract}",
                "tags": [],
            }
            zot.create_items([note])
            time.sleep(0.3)

        # PDF download attempt
        doi = paper.get("doi", "")
        arxiv_url = paper.get("url", "") if "arxiv" in paper.get("url", "") else ""
        pdf_url = _fetch_oa_pdf_url(doi) or (arxiv_url.replace("abs", "pdf") if arxiv_url else None)

        if pdf_url:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            if _download_pdf(pdf_url, tmp_path):
                try:
                    zot.attachment_simple([tmp_path], parentid=item_key)
                    pdf_ok += 1
                except Exception:
                    pdf_fail += 1
                    _tag_item(zot, item_key, "pdf:missing")
                finally:
                    os.unlink(tmp_path)
            else:
                pdf_fail += 1
                _tag_item(zot, item_key, "pdf:missing")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            pdf_missing += 1
            _tag_item(zot, item_key, "pdf:missing")

        # Update or append local index record
        if match:
            # Back-fill zotero_key into existing local-only record
            match["zotero_key"] = item_key
            sections = match.setdefault("related_sections", [])
            if section_id not in sections:
                sections.append(section_id)
            print(f"  🔗 [gid:{gid}] local→Zotero: {paper.get('title', '')[:70]}")
        else:
            record: dict = {
                "global_id": gid,
                "zotero_key": item_key,
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year", ""),
                "doi": paper.get("doi", ""),
                "pmid": paper.get("pmid", ""),
                "abstract": abstract,
                "related_sections": [section_id],
                "source_provider": paper.get("source_provider", ""),
                "verified": False,
            }
            index.append(record)
            print(f"  ✅ [gid:{gid}] {paper.get('title', '')[:70]}")
        new_count += 1

    _save_local_index(index_path, index)

    print(f"\n完成 section {section_id}:")
    print(f"  ✅ 新建 {new_count} 篇（已写入 Zotero + 本地索引，gid 已分配）")
    print(f"  ↩️  已存在 {existing_count} 篇（仅追加到 section collection，gid 不变）")
    print(f"  ✅ PDF 下载成功：{pdf_ok} 篇")
    print(f"  ⚠️  无 PDF：{pdf_missing} 篇")
    print(f"  ❌ PDF 失败：{pdf_fail} 篇")


def _tag_item(zot: zotero.Zotero, item_key: str, tag: str) -> None:
    """Add a tag to a Zotero item."""
    try:
        item = zot.item(item_key)
        existing_tags = item["data"].get("tags", [])
        if not any(t.get("tag") == tag for t in existing_tags):
            existing_tags.append({"tag": tag})
            item["data"]["tags"] = existing_tags
            zot.update_item(item)
    except Exception:
        pass  # non-critical


def _backfill_existing_metadata(
    zot: zotero.Zotero,
    item_key: str,
    match: dict,
    paper: dict,
) -> bool:
    """Backfill missing abstract/DOI/PMID into Zotero item + local index record.

    Only fills empty fields; never overwrites existing non-empty values.
    Local-index mutation is in-place on `match` (caller persists via _save_local_index).
    Returns True if any field was changed (local or Zotero).
    """
    local_changed = False
    zotero_changed = False

    # ── Local index backfill (in-place) ──
    if not match.get("abstract") and paper.get("abstract"):
        match["abstract"] = paper["abstract"]
        local_changed = True
    if not match.get("doi") and paper.get("doi"):
        match["doi"] = paper["doi"]
        local_changed = True
    if not match.get("pmid") and paper.get("pmid"):
        match["pmid"] = paper["pmid"]
        local_changed = True

    # ── Zotero item backfill (only fetch when there's at least one candidate field) ──
    has_zotero_candidate = bool(
        paper.get("abstract") or paper.get("doi") or paper.get("pmid")
    )
    if has_zotero_candidate:
        try:
            item = zot.item(item_key)
            data = item["data"]
            if not data.get("abstractNote") and paper.get("abstract"):
                data["abstractNote"] = paper["abstract"]
                zotero_changed = True
            if not data.get("DOI") and paper.get("doi"):
                data["DOI"] = paper["doi"]
                zotero_changed = True
            # PMID lives in `extra` field for journalArticle items (Zotero convention)
            # Use word-boundary match to avoid false positive from "PMCID" substring
            if paper.get("pmid") and not re.search(r'\bPMID:', data.get("extra", "")):
                extra = data.get("extra", "")
                pmid_line = f"PMID: {paper['pmid']}"
                data["extra"] = f"{extra}\n{pmid_line}".strip() if extra else pmid_line
                zotero_changed = True

            if zotero_changed:
                zot.update_item(item)
                time.sleep(0.3)
        except Exception as e:
            # Non-fatal: leave a trace so the user can re-run if needed
            print(f"  ⚠️  Could not backfill Zotero item {item_key}: {e}")

    return local_changed or zotero_changed


# ─────────────────────────────────────────────
# --dedup
# ─────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation for fuzzy comparison."""
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def cmd_dedup(zot: "zotero.Zotero", scope_key: Optional[str] = None) -> None:
    """
    REPAIR command: deduplicate and reassign gid:N within a scoped collection.

    Normal workflow does NOT need this — --add-batch deduplicates at write time.
    Use only when importing papers manually or repairing a corrupted state.

    --scope ROOT_KEY limits dedup to items under the review's root collection,
    preventing contamination of other Zotero projects.
    Without --scope the ENTIRE library is scanned (dangerous — use with caution).
    """
    if scope_key:
        print(f"⚠️  Repair mode: dedup scoped to collection {scope_key}")
        all_items = zot.everything(zot.collection_items(scope_key))
        all_items = [it for it in all_items if it["data"].get("itemType") == "journalArticle"]
    else:
        print("⚠️  No --scope provided — scanning ENTIRE library.")
        print("    This may corrupt gid tags in other projects. Ctrl-C to abort.")
        time.sleep(3)
        all_items = zot.everything(zot.items(itemType="journalArticle"))
    print(f"  Found {len(all_items)} journal articles.")

    # Build DOI → [items] and title → [items] maps
    doi_map: Dict[str, List] = {}
    title_map: Dict[str, List] = {}
    for item in all_items:
        doi = item["data"].get("DOI", "").strip().lower()
        title_norm = _normalize_title(item["data"].get("title", ""))
        if doi:
            doi_map.setdefault(doi, []).append(item)
        if title_norm:
            title_map.setdefault(title_norm, []).append(item)

    # Find duplicate groups
    merged: Set[str] = set()
    duplicate_groups: List[List] = []

    # DOI exact duplicates
    for doi, items in doi_map.items():
        if len(items) > 1:
            duplicate_groups.append(items)
            for it in items:
                merged.add(it["key"])

    # Title fuzzy duplicates (for items not already merged by DOI)
    norm_titles = list(title_map.keys())
    for i in range(len(norm_titles)):
        for j in range(i + 1, len(norm_titles)):
            ratio = SequenceMatcher(None, norm_titles[i], norm_titles[j]).ratio()
            if ratio >= 0.85:
                group_i = [it for it in title_map[norm_titles[i]] if it["key"] not in merged]
                group_j = [it for it in title_map[norm_titles[j]] if it["key"] not in merged]
                combined = group_i + group_j
                if len(combined) > 1:
                    duplicate_groups.append(combined)
                    for it in combined:
                        merged.add(it["key"])

    removed = 0
    for group in duplicate_groups:
        # Canonical = first item (keep it); rest are duplicates
        canonical = group[0]
        duplicates = group[1:]

        # Get all collections of duplicates
        dup_collections: Set[str] = set()
        for dup in duplicates:
            for col_key in dup["data"].get("collections", []):
                dup_collections.add(col_key)

        # Add canonical to those collections by updating its collections field
        if dup_collections:
            try:
                canonical_fresh = zot.item(canonical["key"])
                existing_cols: Set[str] = set(canonical_fresh["data"].get("collections", []))
                merged_cols = list(existing_cols | dup_collections)
                canonical_fresh["data"]["collections"] = merged_cols
                zot.update_item(canonical_fresh)
                time.sleep(0.3)
            except Exception:
                pass

        # Delete duplicates
        for dup in duplicates:
            try:
                zot.delete_item(dup)
                removed += 1
                time.sleep(0.3)
            except Exception:
                pass

    print(f"  Dedup complete: {removed} duplicate(s) removed.")

    # Assign gid:N tags in section outline order (scoped to avoid touching other projects)
    print("Assigning gid:N tags...")
    gid = 1
    assigned_keys: Set[str] = set()

    if scope_key:
        # Only scan subcollections of the review's root collection
        sub_cols = sorted(
            zot.everything(zot.collections_sub(scope_key)),
            key=lambda c: c["data"]["name"]
        )
        col_keys_to_scan = [scope_key] + [c["key"] for c in sub_cols]
    else:
        all_cols = sorted(zot.everything(zot.collections()), key=lambda c: c["data"]["name"])
        col_keys_to_scan = [c["key"] for c in all_cols]

    for col_key_iter in col_keys_to_scan:
        items_in_col = zot.everything(zot.collection_items(col_key_iter))
        for item in items_in_col:
            if item["key"] in assigned_keys:
                continue
            if item["data"].get("itemType") != "journalArticle":
                continue
            _replace_gid_tag(zot, item, gid)
            assigned_keys.add(item["key"])
            gid += 1
            time.sleep(0.2)

    print(f"  Assigned gid:1 … gid:{gid - 1} to {len(assigned_keys)} unique items.")


def _replace_gid_tag(zot: zotero.Zotero, item: dict, gid: int) -> None:
    """Replace any existing gid:X tag with gid:N."""
    tags = [t for t in item["data"].get("tags", []) if not t.get("tag", "").startswith("gid:")]
    tags.append({"tag": f"gid:{gid}"})
    item["data"]["tags"] = tags
    try:
        zot.update_item(item)
    except Exception:
        pass


# ─────────────────────────────────────────────
# --get-section
# ─────────────────────────────────────────────

def cmd_get_section(zot: zotero.Zotero, section_id: str, root_key: Optional[str] = None) -> None:
    """Print all papers in a section collection as JSON."""
    col_key = _find_collection_by_section(zot, section_id, root_key)
    if not col_key:
        scope_hint = f" within root '{root_key}'" if root_key else ""
        sys.exit(f"❌ Collection for section '{section_id}' not found{scope_hint}.")

    items = zot.everything(zot.collection_items(col_key))
    results = []
    for item in items:
        if item["data"].get("itemType") != "journalArticle":
            continue
        gid = next(
            (t["tag"].split(":")[1] for t in item["data"].get("tags", []) if t.get("tag", "").startswith("gid:")),
            None,
        )
        results.append({
            "gid": gid,
            "key": item["key"],
            "title": item["data"].get("title", ""),
            "authors": [
                f"{c.get('lastName', '')} {c.get('firstName', '')}".strip()
                for c in item["data"].get("creators", [])
            ],
            "year": item["data"].get("date", ""),
            "doi": item["data"].get("DOI", ""),
            "abstract": item["data"].get("abstractNote", ""),
        })

    # Sort by gid
    results.sort(key=lambda x: int(x["gid"]) if x["gid"] and x["gid"].isdigit() else 9999)
    print(json.dumps(results, indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────
# --export-bibtex
# ─────────────────────────────────────────────

def _sanitize_key(s: str) -> str:
    """Produce a safe BibTeX key fragment from a string."""
    return re.sub(r"[^\w]", "", s.lower())[:20]


def cmd_export_bibtex(zot: zotero.Zotero, output_path: str, root_key: Optional[str] = None) -> None:
    """Export gid-tagged articles as BibTeX with citation keys ref_N.

    If root_key is provided, only exports items in that collection (scoped to current project).
    Without root_key, exports ALL gid-tagged items from the entire library.
    """
    if root_key:
        print(f"Fetching items from root collection {root_key}...")
        all_items = zot.everything(zot.collection_items(root_key))
        all_items = [it for it in all_items if it["data"].get("itemType") == "journalArticle"]
    else:
        print("Fetching all tagged items (entire library)...")
        all_items = zot.everything(zot.items(itemType="journalArticle"))

    # Collect items that have a gid tag
    gid_items: List[Tuple[int, dict]] = []
    for item in all_items:
        for tag in item["data"].get("tags", []):
            if tag.get("tag", "").startswith("gid:"):
                try:
                    gid_n = int(tag["tag"].split(":")[1])
                    gid_items.append((gid_n, item))
                except ValueError:
                    pass

    gid_items.sort(key=lambda x: x[0])

    lines = []
    for gid_n, item in gid_items:
        d = item["data"]
        cite_key = f"ref_{gid_n}"

        # Author list for BibTeX
        authors_raw = d.get("creators", [])
        author_parts = []
        for c in authors_raw:
            last = c.get("lastName", "")
            first = c.get("firstName", "")
            if last:
                author_parts.append(f"{last}, {first}" if first else last)
        author_str = " and ".join(author_parts) if author_parts else "Unknown"

        title = d.get("title", "").replace("{", "").replace("}", "")
        journal = d.get("publicationTitle", "")
        year = d.get("date", "")[:4] if d.get("date") else ""
        doi = d.get("DOI", "")
        volume = d.get("volume", "")
        pages = d.get("pages", "")

        entry = [f"@article{{{cite_key},"]
        entry.append(f"  author  = {{{author_str}}},")
        entry.append(f"  title   = {{{title}}},")
        if journal:
            entry.append(f"  journal = {{{journal}}},")
        if year:
            entry.append(f"  year    = {{{year}}},")
        if volume:
            entry.append(f"  volume  = {{{volume}}},")
        if pages:
            entry.append(f"  pages   = {{{pages}}},")
        if doi:
            entry.append(f"  doi     = {{{doi}}},")
        entry.append("}")
        lines.append("\n".join(entry))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))

    print(f"✅ Exported {len(gid_items)} entries → {output_path}")


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

def main() -> None:
    # One-time credential save: `zotero_manager.py save-credentials --lib-id X --api-key Y`
    if len(sys.argv) > 1 and sys.argv[1] == "save-credentials":
        sub = argparse.ArgumentParser(prog="zotero_manager.py save-credentials")
        sub.add_argument("--lib-id", required=True, help="Zotero library ID / userID (numeric)")
        sub.add_argument("--api-key", required=True, help="Zotero API key (Write access)")
        sargs = sub.parse_args(sys.argv[2:])
        save_credentials(sargs.lib_id, sargs.api_key)
        print(f"✅ 凭据已保存到 {CREDENTIALS_PATH}（权限 600）")
        print(f"   library_id={sargs.lib_id}  api_key={_mask(sargs.api_key)}")
        return

    parser = argparse.ArgumentParser(
        description="Zotero Web API manager for general-review-writing skill"
    )
    parser.add_argument("--lib-id", help="Zotero library ID (numeric); optional if saved via save-credentials")
    parser.add_argument("--api-key", help="Zotero API key (Write access); optional if saved via save-credentials")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Test connection and list collections")
    group.add_argument("--init", action="store_true", help="Create collection tree from outline.md")
    group.add_argument("--add-batch", action="store_true", help="Batch add papers to section")
    group.add_argument("--dedup", action="store_true", help="Deduplicate and assign gid:N tags")
    group.add_argument("--get-section", metavar="SECTION_ID", help="List papers in section (e.g. '2.1')")
    group.add_argument("--export-bibtex", action="store_true", help="Export BibTeX for all gid-tagged items")

    # --init options
    parser.add_argument("--title", help="Review title (for --init)")
    parser.add_argument("--outline", help="Path to outline.md (for --init)")

    # --add-batch options
    parser.add_argument("--section", help="Section ID, e.g. '2.1' (for --add-batch)")
    parser.add_argument("--papers", help="Path to papers.json (for --add-batch)")
    parser.add_argument("--index", default="data/literature_index.json",
                        help="Path to local literature_index.json (for --add-batch, default: data/literature_index.json)")
    parser.add_argument("--root-key", help="Zotero root collection key for this review (required for --add-batch; strongly recommended for --get-section to prevent cross-project contamination)")

    # --dedup options
    parser.add_argument("--scope", help="Root collection key to scope dedup (for --dedup repair mode)")

    # --export-bibtex options
    parser.add_argument("--output", help="Output .bib file path (for --export-bibtex)")

    # --status options (machine-readable variants)
    parser.add_argument("--json", action="store_true",
                        help="With --status: emit JSON document instead of human prose")
    parser.add_argument("--find-root-title",
                        help="With --status: exact-match lookup for a top-level collection by name; "
                             "prints the matching key (exit 0), exits 3 if none, exits 4 if ambiguous")

    args = parser.parse_args()

    lib_id, api_key = resolve_credentials(args.lib_id, args.api_key)
    zot = connect(lib_id, api_key)

    if args.status:
        cmd_status(zot, json_out=args.json, find_root_title=args.find_root_title)

    elif args.init:
        if not args.title or not args.outline:
            sys.exit("❌ --init requires --title and --outline")
        if not os.path.exists(args.outline):
            sys.exit(f"❌ outline.md not found: {args.outline}")
        cmd_init(zot, args.title, args.outline)

    elif args.add_batch:
        if not args.section or not args.papers:
            sys.exit("❌ --add-batch requires --section and --papers")
        if not os.path.exists(args.papers):
            sys.exit(f"❌ papers.json not found: {args.papers}")
        if not args.root_key:
            sys.exit("❌ --add-batch requires --root-key (Zotero root collection key for this review)")
        cmd_add_batch(zot, args.section, args.papers, args.index, args.root_key)

    elif args.dedup:
        cmd_dedup(zot, scope_key=args.scope)

    elif args.get_section:
        if not args.root_key:
            print("⚠️  --root-key not provided for --get-section; search may return results from a different project.")
        cmd_get_section(zot, args.get_section, args.root_key)

    elif args.export_bibtex:
        if not args.output:
            sys.exit("❌ --export-bibtex requires --output")
        cmd_export_bibtex(zot, args.output, root_key=args.root_key)


if __name__ == "__main__":
    main()
