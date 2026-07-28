from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


BANNED_PLACEHOLDER_MARKERS = ("{{", "待ai", "ai_fill_required")
ALLOWED_PROVIDER_FAMILIES = {"paper-search", "user-provided"}
REFERENCE_SOURCE_NAME_RE = re.compile(r"(reference|references|bibliography|literature_index|refs?)", re.IGNORECASE)
REFERENCE_SOURCE_EXTS = {".json", ".md", ".txt", ".docx", ".bib", ".ris"}
MANUSCRIPT_VERSION_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")
GLOBAL_SKILL_ROOTS = (
    Path.home() / ".codex" / "skills",
    Path.home() / ".config" / "opencode" / "skills",
)
NON_MEANINGFUL_TEXT_VALUES = {
    "",
    "无",
    "none",
    "n/a",
    "na",
    "not provided by user",
    "not provided",
    "not available",
    "ai_fill_required",
    "待ai",
}
AI_STYLE_BANNED_PATTERNS: tuple[tuple[str, str], ...] = (
    ("delve into", r"\bdelve into\b"),
    ("comprehensive landscape", r"\bcomprehensive landscape\b"),
    ("pivotal role", r"\bpivotal role\b"),
    ("realm", r"\brealm\b"),
    ("tapestry", r"\btapestry\b"),
    ("underscore", r"\bunderscore(?:s|d)?\b"),
    ("testament", r"\btestament\b"),
    ("Moreover", r"\bMoreover\b"),
    ("Crucial", r"\bCrucial\b"),
    ("Landscape", r"\bLandscape\b"),
    ("Pivot", r"\bPivot(?:s|ed|ing)?\b"),
    ("Foster", r"\bFoster(?:s|ed|ing)?\b"),
    ("Spearhead", r"\bSpearhead(?:s|ed|ing)?\b"),
    ("It is worth noting", r"\bIt is worth noting\b"),
    ("As mentioned above", r"\bAs mentioned above\b"),
    ("serves as", r"\bserves as\b"),
    ("acts as", r"\bacts as\b"),
)

# MID: AI cliché term list aligned with general-sci-writing/scripts/style_checker.py
# FORBIDDEN_EXACT, extended with the Chinese academic boilerplate terms that the
# revise-sci polish fragment must also reject. English entries are matched
# case-insensitively as whole phrases; Chinese entries are matched as substrings.
AI_CLICHE_TERMS_EN: tuple[str, ...] = (
    "delve into",
    "comprehensive landscape",
    "pivotal role",
    "realm",
    "tapestry",
    "underscore",
    "testament",
    "it is well known",
    "it is worth noting",
    "it should be noted",
    "importantly",
    "interestingly",
    "remarkably",
    "notably",
    "in recent years",
    "a growing body of evidence",
    "has garnered significant attention",
    "plays a crucial role",
    "a plethora of",
    "myriad of",
    "in the context of",
    "shed light on",
    "pave the way",
    "of paramount importance",
    "a key player",
    "moreover",
    "furthermore",
)
AI_CLICHE_TERMS_ZH: tuple[str, ...] = (
    "值得注意的是",
    "值得一提的是",
    "众所周知",
    "不言而喻",
    "综上所述",
    "总而言之",
    "总的来说",
    "毋庸置疑",
    "显而易见",
    "至关重要",
    "举足轻重",
    "深入探讨",
    "近年来",
    "随着……的发展",
    "在……的背景下",
    "为……奠定了基础",
    "发挥着重要作用",
    "扮演着重要角色",
)

# Pre-compiled whole-phrase matchers for the English cliché list.
AI_CLICHE_PATTERNS_EN: tuple[tuple[str, Any], ...] = tuple(
    (term, re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)) for term in AI_CLICHE_TERMS_EN
)

# A: numeric token extractor for integers, decimals, percentages, p-values,
# confidence intervals, sample sizes (n=N). Used by numeric_tokens_preserved.
NUMERIC_TOKEN_RE = re.compile(
    r"""
    (?:
        [pP]\s*[<>=≤≥]\s*\d*\.?\d+        # p-values: p=0.03, p < 0.001
      | \b[nN]\s*=\s*\d+                   # sample sizes: n=42
      | \b(?:95%?\s*)?CI\b                 # CI / 95% CI marker
      | \d+(?:\.\d+)?\s*%                  # percentages: 12%, 3.5 %
      | \d+(?:\.\d+)?                      # plain integers / decimals
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# B: cautious (hedging) verbs vs. strong (assertive) verbs. The guard only
# blocks the upgrade direction (hedge -> strong claim), matching the
# conservative philosophy of preserving evidence strength.
CERTAINTY_HEDGE_PATTERNS: tuple[tuple[str, Any], ...] = (
    ("may", re.compile(r"\bmay\b", re.IGNORECASE)),
    ("might", re.compile(r"\bmight\b", re.IGNORECASE)),
    ("could", re.compile(r"\bcould\b", re.IGNORECASE)),
    ("suggests", re.compile(r"\bsuggest(?:s|ed)?\b", re.IGNORECASE)),
    ("indicates", re.compile(r"\bindicate(?:s|d)?\b", re.IGNORECASE)),
    ("is associated with", re.compile(r"\b(?:is|are|was|were)\s+associated with\b", re.IGNORECASE)),
    ("appears", re.compile(r"\bappear(?:s|ed)?\b", re.IGNORECASE)),
    ("is consistent with", re.compile(r"\b(?:is|are|was|were)\s+consistent with\b", re.IGNORECASE)),
)
CERTAINTY_STRONG_PATTERNS: tuple[tuple[str, Any], ...] = (
    ("demonstrates", re.compile(r"\bdemonstrate(?:s|d)?\b", re.IGNORECASE)),
    ("proves", re.compile(r"\bprove(?:s|d|n)?\b", re.IGNORECASE)),
    ("establishes", re.compile(r"\bestablish(?:es|ed)?\b", re.IGNORECASE)),
    ("confirms", re.compile(r"\bconfirm(?:s|ed)?\b", re.IGNORECASE)),
    ("shows definitively", re.compile(r"\bshows? definitively\b", re.IGNORECASE)),
)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_meaningful_text(text: str) -> bool:
    normalized = normalize_ws(text).lower()
    return normalized not in NON_MEANINGFUL_TEXT_VALUES


def find_ai_style_markers(text: str) -> list[str]:
    normalized = normalize_ws(text)
    if not normalized:
        return []
    markers: list[str] = []
    for label, pattern in AI_STYLE_BANNED_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            markers.append(label)
    if "—" in normalized:
        markers.append("em dash")
    if re.search(r"\bnot only\b.*\bbut also\b", normalized, flags=re.IGNORECASE):
        markers.append("not only...but also")
    # "from A to B" 模式已移除:科学文本高频合法(谱系/转变/范围,如 "from gut to bone"、
    # "from unmodified probiotics to engineered strains"),纯修辞铺陈难以与合法用法可靠区分,
    # 信噪比差、误报率高(review-writing 的 style_checker 亦已移除)。
    if "?" in normalized:
        markers.append("rhetorical question")
    if re.search(r",\s*(?:thus|thereby|therefore)\s+[A-Za-z-]+ing\b", normalized, flags=re.IGNORECASE):
        markers.append("trailing -ing clause")
    if re.search(r",\s*(?:reflecting|ensuring|highlighting|suggesting|demonstrating|indicating|revealing)\b", normalized, flags=re.IGNORECASE):
        markers.append("trailing -ing clause")
    # Scare quotes: ordinary phrase (≥2 non-empty words) wrapped in double quotes
    # Exclusions: single technical term in quotes (likely a defined term/acronym), citations "[n]"
    for m in re.finditer(r'"([^"]{2,60})"', normalized):
        quoted = m.group(1).strip()
        # skip if it looks like a citation marker or pure number
        if re.fullmatch(r"[\d,\s]+", quoted):
            continue
        # flag when the quoted content is ≥2 words (scare-quote pattern)
        if len(quoted.split()) >= 2:
            markers.append("scare quotes")
            break
    # Explanatory colon: "Concept: explanation" — colon followed by a lowercase or sentence-starting word
    # Legitimate colons: ratios (1:2), time (10:30), list introduction after verb, headings
    # Heuristic: flag "word/phrase: word(s)" where the part before colon is ≤6 words and
    # the part after colon is a sentence fragment (starts with a word, not a number/abbreviation)
    for m in re.finditer(r"\b([A-Za-z][^:]{2,40}):\s+([A-Za-z][a-z][^.;!?]*)", normalized):
        before = m.group(1).strip()
        after = m.group(2).strip()
        # skip legitimate patterns: headings at start of text, figure labels, etc.
        if re.search(r"^(fig|figure|table|eq|equation|note|step)\b", before, re.IGNORECASE):
            continue
        # skip legitimate enumeration: colon followed by a comma/semicolon-separated list
        # (e.g. "three advantages: no risk, low cost, easy scaling") or a short "A and B"
        # pairing (e.g. "two groups: control and treatment"), not an explanatory clause
        if re.search(r", |; ", after):
            continue
        if " and " in after and len(after.split()) <= 4:
            continue
        before_words = before.split()
        if 1 <= len(before_words) <= 6:
            markers.append("explanatory colon")
            break
    # Sentence length: warn when any sentence exceeds 30 words (soft check)
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    if any(len(s.split()) > 30 for s in sentences if s.strip()):
        markers.append("sentence >30 words")
    # MID: AI cliché / boilerplate phrases (English whole-phrase + Chinese substring)
    for term, pattern in AI_CLICHE_PATTERNS_EN:
        if pattern.search(normalized):
            markers.append(f"cliche: {term}")
    for term in AI_CLICHE_TERMS_ZH:
        bare = term.replace("……", "")
        if bare and bare in normalized:
            markers.append(f"cliche: {term}")
    return markers


# 句长(sentence >30 words)这类形式项为"软提示"：仍由 find_ai_style_markers 检出并
# 向用户响亮上报，但不阻断交付（fail-close）。破折号(em dash)是硬门禁、禁止使用——不在软集，
# 由 hard_ai_style_markers 收回、对破折号 fail-close。真正阻断的还有套话禁词、scare quotes、
# 解释性冒号、-ing 假分析等"主干" AI 痕迹。
SOFT_STYLE_MARKERS: frozenset[str] = frozenset({"sentence >30 words"})


def hard_ai_style_markers(text: str) -> list[str]:
    """去 AI 硬门禁子集：剔除 SOFT_STYLE_MARKERS，只留会阻断交付的核心 AI 痕迹。"""
    return [m for m in find_ai_style_markers(text) if m not in SOFT_STYLE_MARKERS]


def soft_ai_style_markers(text: str) -> list[str]:
    """去 AI 软提示子集：句长/破折号等只上报、不阻断的形式项。"""
    return [m for m in find_ai_style_markers(text) if m in SOFT_STYLE_MARKERS]


def numeric_tokens(text: str) -> set[str]:
    """A: extract the set of numeric tokens (ints, decimals, %, p-values, CI, n=N)."""
    normalized = normalize_ws(text)
    found: set[str] = set()
    for m in NUMERIC_TOKEN_RE.finditer(normalized):
        token = re.sub(r"\s+", "", m.group(0)).lower()
        if token:
            found.add(token)
    return found


def numeric_tokens_preserved(raw: str, polished: str) -> dict[str, Any]:
    """A: compare numeric token sets between the locked raw fragment and the
    polished fragment. Fails when the polish introduces a numeric value that the
    raw fragment did not contain, or drops a value the raw fragment had."""
    raw_tokens = numeric_tokens(raw)
    polished_tokens = numeric_tokens(polished)
    introduced = sorted(polished_tokens - raw_tokens)
    dropped = sorted(raw_tokens - polished_tokens)
    return {
        "ok": not introduced and not dropped,
        "introduced": introduced,
        "dropped": dropped,
        "raw_tokens": sorted(raw_tokens),
        "polished_tokens": sorted(polished_tokens),
    }


def detect_certainty_upgrade(raw: str, polished: str) -> dict[str, Any]:
    """B: detect when a cautious hedging verb in the raw fragment is upgraded to
    a strong assertive claim in the polished fragment. Only the upgrade direction
    (weaker -> stronger) is blocked, preserving the conservative evidence stance."""
    raw_norm = normalize_ws(raw)
    polished_norm = normalize_ws(polished)
    raw_hedges = {label for label, pattern in CERTAINTY_HEDGE_PATTERNS if pattern.search(raw_norm)}
    raw_strong = {label for label, pattern in CERTAINTY_STRONG_PATTERNS if pattern.search(raw_norm)}
    polished_strong = {label for label, pattern in CERTAINTY_STRONG_PATTERNS if pattern.search(polished_norm)}
    raw_had_hedge = bool(raw_hedges)
    raw_had_strong = bool(raw_strong)
    # Newly introduced strong verbs that were not present in the raw fragment.
    introduced_strong = sorted(polished_strong - raw_strong)
    # Upgrade = raw leaned cautious (had a hedge, no strong verb) but the polished
    # text now asserts a strong verb that was absent before.
    upgraded = bool(raw_had_hedge and not raw_had_strong and introduced_strong)
    return {
        "ok": not upgraded,
        "raw_hedges": sorted(raw_hedges),
        "introduced_strong_verbs": introduced_strong,
    }


def polish_changed_text_locally(text: str) -> str:
    cleaned = normalize_ws(text)
    if not cleaned:
        return cleaned
    replacements = (
        (r"\bMoreover,\s*", ""),
        (r"\bCrucial\b", "Important"),
        (r"\bdelve into\b", "examine"),
        (r"\bcomprehensive landscape\b", "current evidence base"),
        (r"\bpivotal role\b", "key role"),
        (r"\brealm\b", "field"),
        (r"\btapestry\b", "pattern"),
        (r"\bunderscore(?:s|d)?\b", "show"),
        (r"\btestament\b", "evidence"),
        (r"\bIt is worth noting that\s*", ""),
        (r"\bAs mentioned above,\s*", ""),
        (r"\bserves as\b", "is"),
        (r"\bacts as\b", "is"),
        (r"\bFoster(?:s|ed|ing)?\b", "support"),
        (r"\bSpearhead(?:s|ed|ing)?\b", "lead"),
    )
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("—", ", ")
    cleaned = re.sub(r"\bnot only\s+(.+?)\s+but also\s+(.+?)([.;!?]|$)", r"\1 and \2\3", cleaned, flags=re.IGNORECASE)
    # "from X to Y" 改写已移除：科学文本里多为合法谱系/转变/范围，且改成 "across X and Y"
    # 会改变方向语义，违反 fragment-only 改写不动原意的原则；检测端亦不再标记。
    cleaned = re.sub(r",\s*(?:thus|thereby|therefore)\s+([A-Za-z-]+ing\b[^.;!?]*)", r".", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("?", ".")
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    cleaned = re.sub(r"\.\.+", ".", cleaned)
    cleaned = normalize_ws(cleaned)
    return cleaned


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    return cleaned or "section"


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compute_tree_signature(root: Path, patterns: tuple[str, ...] = ("*.py", "*.md", "*.json")) -> str:
    digest = hashlib.sha256()
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def path_signature(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False}
    resolved = path.resolve()
    if not resolved.exists():
        return {"path": str(resolved), "exists": False}
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def directory_signature(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False, "files": []}
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return {"path": str(resolved), "exists": False, "files": []}
    files = []
    for item in sorted(resolved.iterdir()):
        if not item.is_file():
            continue
        stat = item.stat()
        files.append({"name": item.name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return {"path": str(resolved), "exists": True, "files": files}


def _run_is_superscript(run) -> bool:
    try:
        return bool(run.font.superscript)
    except (AttributeError, ValueError):
        return False


def _run_is_subscript(run) -> bool:
    try:
        return bool(run.font.subscript)
    except (AttributeError, ValueError):
        return False


def serialize_paragraph_with_inline_format(paragraph) -> str:
    """Serialize a docx paragraph's run-level formatting into inline markers so the
    text round-trips italic/bold/superscript/subscript: `*italic*`, `**bold**`,
    `<sup>..</sup>`, `<sub>..</sub>` (same vocabulary export_docx.add_runs_with_bold
    reconstructs). Adjacent runs sharing a format are merged so we emit one marker
    per span, not one per run. Plain runs pass through verbatim.

    NOTE: This is opt-in (inline_format=True). The default reader stays plain so the
    numeric / citation / AI-style red-line comparisons that consume the shared reader
    are not polluted by markers they never expect.
    """
    out: list[str] = []
    # Coalesce consecutive runs that carry the same (bold, italic, sup, sub) tuple
    # into a single span; emit the span text once with its markers.
    span_text: list[str] = []
    span_fmt: tuple[bool, bool, bool, bool] | None = None

    def flush_span() -> None:
        nonlocal span_text, span_fmt
        if not span_text or span_fmt is None:
            span_text = []
            span_fmt = None
            return
        raw = "".join(span_text)
        if raw.strip():
            bold, italic, sup, sub = span_fmt
            inner = raw
            if sup:
                inner = f"<sup>{inner}</sup>"
            if sub:
                inner = f"<sub>{inner}</sub>"
            if bold:
                inner = f"**{inner}**"
            if italic:
                inner = f"*{inner}*"
            out.append(inner)
        else:
            out.append(raw)  # whitespace-only run: never wrap in markers
        span_text = []
        span_fmt = None

    for run in paragraph.runs:
        run_text = run.text or ""
        if not run_text:
            continue
        fmt = (
            bool(run.bold),
            bool(run.italic),
            _run_is_superscript(run),
            _run_is_subscript(run),
        )
        if span_fmt is None or fmt == span_fmt:
            span_fmt = fmt
            span_text.append(run_text)
        else:
            flush_span()
            span_fmt = fmt
            span_text.append(run_text)
    flush_span()
    return normalize_ws("".join(out))


def read_docx_paragraphs(path: Path, inline_format: bool = False) -> list[dict[str, Any]]:
    """Read docx body paragraphs as {paragraph_index, text, style_name} rows.

    inline_format=False (default): text is the plain paragraph text. Used by every
    red-line consumer (numeric/citation/AI-style guards, reference & comment parsing)
    that must not see formatting markers.

    inline_format=True: text carries run-level italic/bold/sup/sub as inline markers
    (`*..*` / `**..**` / `<sup>..</sup>` / `<sub>..</sub>`) so the atomized manuscript
    sections preserve semantic formatting through the revise -> export round-trip.
    """
    doc = Document(str(path))
    rows: list[dict[str, Any]] = []
    for i, paragraph in enumerate(doc.paragraphs):
        if inline_format:
            text = serialize_paragraph_with_inline_format(paragraph)
        else:
            text = normalize_ws(paragraph.text)
        if not text:
            continue
        style_name = normalize_ws(getattr(getattr(paragraph, "style", None), "name", "") or "")
        rows.append({"paragraph_index": i, "text": text, "style_name": style_name})
    return rows


def detect_comments_input_mode(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            rows = read_docx_paragraphs(path)
        except (PackageNotFoundError, KeyError, ValueError):
            return "docx-review-comments"
        texts = [normalize_ws(row.get("text", "")) for row in rows if normalize_ws(row.get("text", ""))]
        if any(
            re.match(
                r"^(editor(?:ial)?(?:\s+(?:comments?|email|letter|decision letter))?|associate editor(?:\s+comments?)?|decision letter)\b",
                text,
                flags=re.IGNORECASE,
            )
            for text in texts
        ):
            return "docx-review-letter"
        if any(
            re.match(
                r"^(overall (?:statement|assessment)|general assessment|general comments?|reviewer statement|summary|comments to the author)\s*[:：-]?",
                text,
                flags=re.IGNORECASE,
            )
            for text in texts
        ):
            return "docx-review-letter"
        if any(re.match(r"^Reviewer\s*#?\d+\s*[:：-]\s*.+$", text, flags=re.IGNORECASE) for text in texts):
            return "docx-review-letter"
        return "docx-review-comments"
    if suffix != ".html":
        return "unsupported"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "html-unknown"
    lowered = text.lower()
    if "class=\"comment-unit\"" in lowered or "data-comment-id=" in lowered:
        return "atomic-comment-html"
    if "critique-section" in lowered and "critique-list" in lowered:
        return "reviewer-simulator-html"
    if (
        "response to reviewer" in lowered
        and "evidence attachments" in lowered
        and ("page-u-" in lowered or "reviewer #1 |" in lowered or "reviewer #1 -" in lowered)
    ):
        return "reviewer-response-sci-html"
    return "html-unknown"


def reviewer_sort_key(reviewer: str) -> tuple[int, int, str]:
    label = normalize_ws(reviewer)
    lowered = label.lower()
    if lowered.startswith("editor") or lowered.startswith("associate editor") or lowered == "decision letter":
        return (0, 0, label)
    match = re.search(r"(\d+)", label)
    if match:
        return (1, int(match.group(1)), label)
    return (2, 999, label)


def docx_title_hint(path: Path) -> str:
    try:
        rows = read_docx_paragraphs(path)
    except (PackageNotFoundError, KeyError, ValueError):
        return ""
    for row in rows[:12]:
        text = normalize_ws(row.get("text", ""))
        if not text:
            continue
        lowered = text.lower()
        if lowered in {"highlights", "abstract", "keywords", "references"}:
            continue
        if re.match(r"^(fig|figure|table)\b", text, flags=re.IGNORECASE):
            continue
        return text
    return ""


def looks_like_reference_entry(text: str) -> bool:
    candidate = normalize_ws(text)
    lowered = candidate.lower()
    if re.search(r"\bdoi:\s*10\.", lowered) or re.search(r"\bpmid:\s*\d+", lowered):
        return True
    if re.match(r"^\[?\d+\]?[.)]?\s+", candidate):
        has_year = re.search(r"\b(19|20)\d{2}\b", candidate) is not None
        author_like = re.search(r"^\[?\d+\]?[.)]?\s+[A-Z][A-Za-z-]+(?:\s+[A-Z]\.)?", candidate) is not None
        if has_year and author_like:
            return True
    return False


def docx_reference_entry_count(path: Path) -> int:
    try:
        rows = read_docx_paragraphs(path)
    except (PackageNotFoundError, KeyError, ValueError):
        return 0
    in_references = False
    count = 0
    for row in rows:
        text = normalize_ws(row.get("text", ""))
        if not text:
            continue
        lowered = text.lower()
        style_name = row.get("style_name", "").lower()
        if lowered in {"references", "reference", "参考文献"}:
            in_references = True
            continue
        if in_references and is_heading(row):
            break
        if "bibliography" in style_name and looks_like_reference_entry(text):
            count += 1
            continue
        if in_references and looks_like_reference_entry(text):
            count += 1
    return count


def normalize_title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_ws(text).lower()).strip()


def normalize_stem_key(text: str) -> str:
    lowered = MANUSCRIPT_VERSION_SUFFIX_RE.sub("", normalize_ws(text).lower())
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def iter_nearby_docx_candidates(manuscript_path: Path) -> list[Path]:
    root = manuscript_path.parent
    candidates: list[Path] = []
    for candidate in sorted(root.rglob("*.docx")):
        if candidate.resolve() == manuscript_path.resolve():
            continue
        if candidate.name.startswith("~$"):
            continue
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) > 3:
            continue
        candidates.append(candidate)
    return candidates


def find_same_title_reference_docx(manuscript_path: Path | None) -> Path | None:
    if manuscript_path is None or not manuscript_path.exists() or manuscript_path.suffix.lower() != ".docx":
        return None
    manuscript_title = normalize_title_key(docx_title_hint(manuscript_path))
    manuscript_stem = normalize_stem_key(manuscript_path.stem)
    siblings: list[tuple[int, Path]] = []
    for candidate in iter_nearby_docx_candidates(manuscript_path):
        reference_count = docx_reference_entry_count(candidate)
        if reference_count < 3:
            continue
        candidate_title = normalize_title_key(docx_title_hint(candidate))
        candidate_stem = normalize_stem_key(candidate.stem)
        title_match = bool(manuscript_title and candidate_title and manuscript_title == candidate_title)
        stem_match = bool(manuscript_stem and candidate_stem and manuscript_stem == candidate_stem)
        title_overlap = 0
        if manuscript_title and candidate_title:
            manuscript_tokens = set(manuscript_title.split())
            candidate_tokens = set(candidate_title.split())
            title_overlap = len(manuscript_tokens.intersection(candidate_tokens))
        near_title_match = title_overlap >= 6
        if not title_match and not stem_match and not near_title_match:
            continue
        score = 0
        if title_match:
            score += 100
        elif near_title_match:
            score += 70
        if stem_match:
            score += 20
        if candidate.parent != manuscript_path.parent:
            score -= 5
        score += min(reference_count, 50)
        siblings.append((score, candidate.resolve()))
    if not siblings:
        return None
    siblings.sort(key=lambda item: (-item[0], str(item[1])))
    return siblings[0][1]


# 机构/地址行常以编号开头(如 "3 X University / X Key Laboratory of …"),易被编号标题正则误吞。
# 含明确机构实体词则判为 affiliation,不算章节标题(词数阈值挡不住较短机构名)。
_AFFILIATION_HINT_RE = re.compile(
    r"\b(?:universit|institut|laborator|hospital|college|faculty|academ|ministr)\w*"
    r"|\b(?:department|school|center|centre|division)\s+(?:of|for)\b"
    r"|大学|学院|研究院|研究所|重点实验室|实验室|医院",
    re.IGNORECASE,
)


_INLINE_FORMAT_MARKER_RE = re.compile(r"\*\*|\*|</?sup>|</?sub>")


def strip_inline_format_markers(text: str) -> str:
    """Remove the inline format markers (`**`, `*`, `<sup>`, `<sub>` and their
    closers) so plain-text matchers (headings, citation regexes) are unaffected
    when fed text produced by inline_format=True reads."""
    return _INLINE_FORMAT_MARKER_RE.sub("", text or "")


def is_heading(row: dict[str, Any]) -> bool:
    style_name = row.get("style_name", "").lower()
    text = strip_inline_format_markers(row.get("text", ""))
    if style_name.startswith("heading"):
        return True
    if (
        re.match(r"^\d+(?:\.\d+)*\.?\s+\S+", text)
        and len(text.split()) <= 12  # 真标题短(粗筛)
        and not _AFFILIATION_HINT_RE.search(text)  # "3 X Key Laboratory…"等机构行排除(阈值挡不住短机构名)
        and not re.match(r"^(fig|figure|table)\b", text, flags=re.IGNORECASE)
        and not looks_like_reference_entry(text)
    ):
        return True
    if len(text.split()) <= 8 and text.lower() in {
        "abstract",
        "introduction",
        "background",
        "methods",
        "materials and methods",
        "results",
        "discussion",
        "conclusion",
        "supplementary methods",
        "supplementary results",
        "references",
        "reference",
        "acknowledgement",
        "acknowledgment",
        "data availability",
        "declaration of competing interest",
        "credit authorship contribution statement",
        "author contributions",
        "funding",
    }:
        return True
    return False


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[\.\!\?;])\s+", normalize_ws(text))
    return [p for p in parts if p]


def tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in re.findall(r"[A-Za-z0-9]+", text or "")}


def choose_sentence(comment_text: str, paragraph_text: str) -> tuple[int, str]:
    sentences = split_sentences(paragraph_text)
    if not sentences:
        return 0, ""
    query = tokenize(comment_text)
    best_index = 0
    best_score = -1
    for idx, sentence in enumerate(sentences):
        score = len(query.intersection(tokenize(sentence)))
        if score > best_score:
            best_score = score
            best_index = idx
    return best_index, sentences[best_index]


def detect_comment_requirements(comment_text: str) -> dict[str, bool]:
    lowered = comment_text.lower()
    needs_methodology = bool(
        re.search(
            r"\b(methodology|methodologies|search strategy|search strategies|database|databases|keyword|keywords|"
            r"inclusion|exclusion|criteria|review method|review methods|evidence level|evidence levels|"
            r"novelty|scope|boundary|boundaries|logic|framework|restructure|reorganization|organization)\b",
            lowered,
        )
    ) or any(
        token in comment_text
        for token in (
            "方法学",
            "检索",
            "数据库",
            "关键词",
            "纳入",
            "排除",
            "证据等级",
            "综述方法",
            "创新性",
            "新颖性",
            "边界",
            "逻辑",
            "框架",
            "重构",
            "结构",
        )
    )
    return {
        "needs_experiment": bool(re.search(r"\b(experiment|assay|animal|western blot|validate|replicate)\b", lowered)),
        "needs_citation": bool(re.search(r"\b(reference|references|citation|citations|literature|pubmed)\b", lowered)),
        "needs_figure": bool(
            re.search(r"\b(figure|fig\.?|table|legend|panel|supplementary|caption|captions|copyright|redraw|graphic)\b", lowered)
        )
        and not needs_methodology,
        "needs_methodology": needs_methodology,
    }


def comment_nature(comment_text: str) -> str:
    requirements = detect_comment_requirements(comment_text)
    if requirements["needs_experiment"]:
        return "需要新增实验或结果支持"
    if requirements.get("needs_methodology"):
        return "需要实质性解释、结构重构或方法学澄清"
    if requirements["needs_citation"]:
        return "需要新增或核验文献支持"
    if requirements["needs_figure"]:
        return "需要核对图表、图注或补充材料"
    return "需要对现有表述进行澄清或收束"


def build_section_markdown(section: dict[str, Any]) -> str:
    parts = [f"# {section['heading']}"]
    for paragraph in section.get("paragraphs", []):
        parts.append("")
        parts.append(paragraph.get("current_text") or paragraph["text"])
    return "\n".join(parts).strip() + "\n"


def blocked_placeholder_found(value: object) -> bool:
    text = normalize_ws(str(value or "")).lower()
    if not text:
        return True
    return any(marker in text for marker in BANNED_PLACEHOLDER_MARKERS)


def autodiscover_reference_source(
    comments_path: Path | None,
    attachments_dir: Path | None,
    project_root: Path | None,
    manuscript_path: Path | None = None,
) -> Path | None:
    candidates: list[Path] = []
    sibling_docx = find_same_title_reference_docx(manuscript_path)
    if sibling_docx is not None:
        candidates.append(sibling_docx)
    if comments_path is not None:
        candidates.append(comments_path.parent / "data" / "literature_index.json")
    if attachments_dir is not None and attachments_dir.exists():
        for item in sorted(attachments_dir.iterdir()):
            if not item.is_file():
                continue
            if item.suffix.lower() not in REFERENCE_SOURCE_EXTS:
                continue
            if REFERENCE_SOURCE_NAME_RE.search(item.name):
                candidates.append(item)
    if project_root is not None:
        for name in (
            "reference_seed.json",
            "references_source.json",
            "legacy_references.json",
            "legacy_references.docx",
            "legacy_references.ris",
            "legacy_references.md",
            "legacy_references.txt",
            "references.bib",
            "references.ris",
        ):
            candidates.append(project_root / name)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def global_skill_install_paths(skill_name: str) -> list[Path]:
    normalized = normalize_ws(skill_name)
    if not normalized:
        return []
    return [root / normalized for root in GLOBAL_SKILL_ROOTS]


def discover_global_skill(skill_name: str) -> list[Path]:
    discovered: list[Path] = []
    for candidate in global_skill_install_paths(skill_name):
        skill_md = candidate / "SKILL.md"
        if skill_md.exists():
            discovered.append(candidate.resolve())
    return discovered


class AtomicCommentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.units: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._chunks: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "") or ""
        if tag == "div" and "comment-unit" in class_name:
            self._current = {
                "comment_id": attrs_dict.get("data-comment-id", "") or "",
                "reviewer": attrs_dict.get("data-reviewer", "") or "Reviewer #1",
                "severity": (attrs_dict.get("data-severity", "") or "major").lower(),
            }
            self._chunks = []
            self._depth = 1
            return
        if self._current is not None:
            self._depth += 1

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            text = normalize_ws(data)
            if text:
                self._chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        self._depth -= 1
        if self._depth <= 0:
            payload = dict(self._current)
            payload["comment_text"] = normalize_ws(" ".join(self._chunks))
            self.units.append(payload)
            self._current = None
            self._chunks = []
            self._depth = 0
