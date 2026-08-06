#!/usr/bin/env python3
"""context-guard 判定库 —— 喂层/拦层/Bash 层三个钩子唯一共用的判定实现。

为什么只能有一份：判定若在三处各写一遍，迟早出现"状态卡说这节没盲检、门禁却
放行"的两套账，用户当场失去信任。故本文件是**唯一**的判定真源，三个钩子只做
输入解析与文案渲染，不自己判。

作为库：纯函数，不打印、不 sys.exit。
作为 CLI（排障 + 测试用）：
    python3 context_guard_core.py explain <路径>
    → 固定 8 键 JSON；0=成功 / 2=用法或输入错（与 structure_signoff_gate 一致）。

清单（state_files / managed_globs / signoff）一律从 gate_registry.json 读，
本文件只放判据函数（证据签名、差集算法），**不重复存任何一份技能清单**——
两处各存一份 = 加一家技能时必漏改一处。

契约真源：.devflow/INTERFACE-context-guard.md（§0 全局约定 / §0.1 清洗 /
§2.5 逐家差集 / §2.6 证据签名表 / §4 explain / §5.2 审计）。
"""
from __future__ import annotations

# 🔴 stdout/stderr 强制 UTF-8（照抄 academic_gate_hook.py:27-32 的既有写法）。
# 不加这段的后果（已实测复现）：deny 理由含中文，在英文语系 Windows（cp1252）
# 与 cp437 上 print() 抛 UnicodeEncodeError → 脚本非 0 退出 → Claude Code 只认
# exit 2 为阻断、其余一律"非阻断错误"放行 → **门禁在真正命中拦截的那一刻自己炸掉、
# 然后放行**。fail-open 是对"认不出项目"的设计取向，不该被编码问题借去用。
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------ 常量

# 与 academic-gate/.claude-plugin/plugin.json 的 version 保持一致；插件目录不在
# 身边（vendored 到 _shared/ 或单技能 scripts/）时用这个常量兜底。
# 一致性由 tests/unit/test_academic_gate_version_lock.py 守着，漂了会红。
FALLBACK_PLUGIN_VERSION = "0.9.1"

MAX_ROOT_DEPTH = 8           # 向上找根的层数上限（INTERFACE §2.6）
NONEMPTY_PROBE = 1024        # _nonempty 只读首 1 KB，绝不整读正文
LIST_MAX = 12                # 列表类字段最多列 12 项（INTERFACE §0.1）
PLACEHOLDER = "<非常规名称已省略>"
AUDIT_NAME = ".academic_gate_audit.jsonl"
AUDIT_MAX_BYTES = 1024 * 1024
# 允许在"算不出项目根"时落 CLAUDE_PLUGIN_DATA 的规则白名单。这几条记的正是
# "这一次没检查成"，落不下就等于没发生过——而它们恰恰全都发生在没有项目根的时刻。
# 其余规则一律要求有项目根（宁可少一条记录，也不在陌生目录里造文件）。
NO_ROOT_RULES = {"path-parse-failed", "F9B-skipped-no-cwd", "internal-error",
                 "stdin-truncated", "F8-weak-ask", "F11-infra-write",
                 "registry-unreadable"}
# 连 CLAUDE_PLUGIN_DATA 都没有时还允许回落 ~/.claude/ 的规则。只给 F11 开：它的目标
# 路径本来就全在 ~/.claude 下，往同一目录写审计不算"在陌生目录造文件"；而 legacy 装法
# 通常没有 CLAUDE_PLUGIN_DATA，不给回落就等于"最该留痕的那条反而无痕"。
# registry-unreadable 一并给：注册表就住在 ~/.claude/skills 下，往同一棵树写审计
# 不算"在陌生目录造文件"；而 legacy 装法通常没有 CLAUDE_PLUGIN_DATA，不给回落就等于
# "门禁整体失效的那一刻反而一点痕迹都没有"。
HOME_AUDIT_RULES = {"F11-infra-write", "registry-unreadable"}
DONE_STATUS = {"done", "completed", "finalized"}

# nsfc 的节级白名单：**硬编码**，不得复用 prewrite_gate.SECTION_ORDER。
# 来由：`.review_pass/` 设计上最多只产 P1/P2/P3_1 三个标记；SECTION_ORDER 还含
# P3_2~P3_4，一旦复用，差集恒非空 → nsfc 项目被永久锁死。谁想"顺手统一"，先看这句。
NSFC_REVIEWED_SECTIONS = ("P1", "P2", "P3_1")

# 路径解析失效 / 无 ask 能力端的告知承载（INTERFACE §2.1.2 / §7.1，S8 定稿）：
#   "A" = PreToolUse 的 additionalContext 确实被模型消费 → 随决策直接发；
#   "B" = 不被消费 → 只写审计 + pending_notice，由下一次 UserPromptSubmit 补报。
# 默认取 B：S8 尚未实测，不把"告知"压在未验证的字段上（压错了等于以为说了、其实没说）。
# S8 通过后把这里改成 "A" 即可，两条路径都已实现。
NOTICE_MODE = "B"

# ------------------------------------------------------------------ §0.1 插值清洗

_INVISIBLE_RE = re.compile(
    "[\x00-\x1f\x7f-\x9f"          # C0 / C1 控制字符（含 \r\n\t）
    "​-‏"                # 零宽 + 双向标记
    "  "                 # 行/段分隔符
    "‪-‮⁠-⁤"   # 双向控制符、不可见连接符
    "⁦-⁩﻿]"         # 隔离符、BOM
)
_IDENT_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_CJK_CHAPTER_RE = re.compile(r"^第\d{1,3}章$")
# B 类白名单：ASCII 常规路径字符 + CJK + 空格；其余一律剔除。
# 含 `\` 与 `:`：Windows 路径（C:\Users\...）少了它们会被清成面目全非的残串，
# 再触发"垃圾占比过半"整字段替换 —— 状态卡上全是 <非常规名称已省略>。
# 这两个字符不构成新风险：仍然剥换行，插值内容无法另起一行冒充系统消息。
_TEXT_DENY_RE = re.compile(r"[^A-Za-z0-9._/\\:\- 一-鿿]")


def sanitize_field(value, kind: str = "text", maxlen: int | None = None) -> str:
    """把来自被审查目录的任意文本清洗成可以进 AI 上下文的样子（INTERFACE §0.1）。

    kind="ident"（节 id / 证书文件名主干 / 技能名 / 缺失签名字段名）：严格模式，
        剥不可见字符后必须整体匹配 ^[A-Za-z0-9._-]{1,64}$ 或 ^第\\d{1,3}章$，
        否则**整字段**替换为 <非常规名称已省略>（不做部分保留——过滤后的残片仍
        可能是通顺句子）。
    kind="text"（项目根路径 / 正文文件名）：合法形态无法穷举，只做白名单字符集 +
        截断。**不承诺挡住语义级注入**，见 INTERFACE §8 非承诺清单。

    清洗只决定"怎么显示"，绝不影响"拦不拦"——否则改个文件名就能绕过 F10。
    """
    try:
        s = value if isinstance(value, str) else str(value)
    except Exception:
        return PLACEHOLDER
    s = _INVISIBLE_RE.sub("", s)
    if kind == "ident":
        return s if (_IDENT_RE.match(s) or _CJK_CHAPTER_RE.match(s)) else PLACEHOLDER
    original_len = len(s)
    s = _TEXT_DENY_RE.sub("", s).strip()
    if not s:
        return PLACEHOLDER
    # 垃圾占比过半 → 整字段替换（剩下的残片没有可读性，还可能是半句指令）
    if original_len and (original_len - len(s)) * 2 > original_len:
        return PLACEHOLDER
    limit = maxlen or 120
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


def sanitize_list(values, kind: str = "ident", maxlen: int | None = None) -> list:
    """逐元素清洗，最多列 LIST_MAX 项，超出追加一条 `…等 N 项` 说明。"""
    items = list(values or [])
    out = [sanitize_field(v, kind, maxlen) for v in items[:LIST_MAX]]
    if len(items) > LIST_MAX:
        out.append("…等 %d 项" % len(items))
    return out


# ------------------------------------------------------------------ 基础设施

def shared_dir() -> Path:
    return Path(__file__).resolve().parent


def plugin_version() -> str:
    """插件版本号：状态卡首行要带它——这是零成本的"钩子在岗"证据。"""
    here = shared_dir()
    for cand in (here.parent / ".claude-plugin" / "plugin.json",
                 here / ".claude-plugin" / "plugin.json"):
        try:
            if cand.is_file():
                v = json.loads(cand.read_text(encoding="utf-8")).get("version")
                if isinstance(v, str) and v:
                    return v
        except Exception:
            pass
    return FALLBACK_PLUGIN_VERSION


REGISTRY_NAME = "gate_registry.json"
_REGISTRY_UNREADABLE = False


def registry_unreadable() -> bool:
    """上一次 load_registry 是不是撞上了"文件在、但读不出/解析不了"。

    喂层据此在状态卡上留一行，让这个状态对用户可见。**不放在拦层**：判定该
    fail-open 就 fail-open，这里只解决"静默"。
    """
    return _REGISTRY_UNREADABLE


def load_registry() -> dict:
    """读不到 → 空表 → 所有钩子放行（既有 fail-open 行为，不改）。

    但"文件不在"和"文件坏了"要分开：前者是正常形态（单技能分发时可能就没有），
    后者是**门禁整体静默失效**——registry 一坏（`chmod 000` 就够了），8 家全部
    不设防。方向仍是 fail-open（正常损坏时不该把用户卡死），但不许静默：
    专属规则名进审计（与"签名函数自己炸了"的 internal-error 分开，事后 grep 得出来）
    + 置位供状态卡显示。
    """
    global _REGISTRY_UNREADABLE
    path = shared_dir() / REGISTRY_NAME
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        _REGISTRY_UNREADABLE = True
        audit_append(None, rule="registry-unreadable", decision="unchecked",
                     target=REGISTRY_NAME,
                     detail="gate_registry %s" % type(exc).__name__)
        return {}
    if not isinstance(obj, dict):
        # 合法 JSON 但顶层不是对象：同样是"文件在、内容用不了"
        _REGISTRY_UNREADABLE = True
        audit_append(None, rule="registry-unreadable", decision="unchecked",
                     target=REGISTRY_NAME, detail="gate_registry not-an-object")
        return {}
    return obj


def plugin_data_dir() -> Path | None:
    """${CLAUDE_PLUGIN_DATA}：去重 / 待报状态 / 无项目根时的审计落点。"""
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not raw:
        return None
    try:
        p = Path(raw)
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        return None


# macOS / Windows 的默认文件系统大小写不敏感：`Sections/P1.MD` 与 `sections/P1.md`
# 是同一个文件（同 inode）。逐字节比路径 = 大小写一变就绕过 F6/F10，**实测可复现**。
# 判据用 normcase（Windows 上非恒等）+ 平台名（darwin 的 normcase 是恒等，测不出来）。
CASE_INSENSITIVE_FS = (os.path.normcase("A") != "A") or sys.platform in (
    "darwin", "win32", "cygwin")


def is_managed(rel_path: str, globs) -> bool:
    rel = str(rel_path).replace(os.sep, "/")
    patterns = list(globs or [])
    # 用 fnmatchcase 而不是 fnmatch：后者的大小写语义跟着 os.path.normcase 走，
    # 在 darwin 上是恒等（等于大小写敏感）、在 Windows 上又不是——同一份代码两种行为。
    # 这里自己按平台决定，行为可预期。
    if CASE_INSENSITIVE_FS:
        rel = rel.lower()
        patterns = [g.lower() for g in patterns]
    return any(fnmatch.fnmatchcase(rel, g) for g in patterns)


def nonempty(path) -> bool:
    """"这个文件算写过了吗" 的统一定义：读首 1 KB，strip 后非空即非空。

    不是 getsize()>0（`touch` 出的 0 字节与只含空白的文件都必须算空，否则 F10
    一步被绕过），也不是整读（正文动辄几十 KB × 十几个文件）。语义与既有
    sci2doc/scripts/prewrite_gate.py 的 file_nonempty() 一致，避免两套账。
    """
    try:
        with open(str(path), "rb") as fh:
            head = fh.read(NONEMPTY_PROBE)
    except Exception:
        return False
    return bool(head.decode("utf-8", "replace").strip())


def review_pass_path(root: Path, section_id) -> "Path | None":
    """`.review_pass/<sid>.json` 的**唯一**构造入口；sid 不可信就返回 None。

    sid 来自被审查项目的 state 文件，是纯外部输入。`Path / "/etc/x"` 会把项目根
    整个丢掉（pathlib 遇绝对路径就重置），`../..` 同样跳得出去 —— 那就成了拿别人
    项目的文件名去探测本机任意路径，违反"读只限项目根内"。

    两道都要：
    ① 白名单（与 §0.1 标识符槽位同一口径：^[A-Za-z0-9._-]{1,64}$ 或 ^第\d{1,3}章$，
       后者是 sci2doc 的真实章级形态）—— 挡已知形态，顺便挡掉所有含 / 的写法；
    ② 拼完再用 rel_to_root 兜一次底 —— 挡没想到的形态（软链、平台特殊语义）。
    """
    if not isinstance(section_id, str) or not section_id:
        return None
    if not (_IDENT_RE.match(section_id) or _CJK_CHAPTER_RE.match(section_id)):
        return None
    try:
        p = root / ".review_pass" / ("%s.json" % section_id)
    except Exception:
        return None
    return p if rel_to_root(p, root) is not None else None


def review_passed(root: Path, section_id: str) -> tuple[bool, bool]:
    """读 `.review_pass/<id>.json`。返回 (passed, manual)。

    fail-closed：sid 非法 / 文件损坏 / 读不动一律视为未通过（与既有
    prewrite_gate._load_json 行为一致）——证书坏了不是放行的理由，
    节号长得可疑更不是。
    """
    p = review_pass_path(root, section_id)
    if p is None:
        return (False, False)
    try:
        if not p.is_file():
            return (False, False)
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return (False, False)
    if not isinstance(obj, dict):
        return (False, False)
    return (obj.get("passed") is True, obj.get("manual") is True)


# ------------------------------------------------------------------ §2.6 证据签名

class _StateReader:
    """一个目录一份读缓存：同一次判定里同名 state 文件只读一次。"""

    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[str, tuple[str, object]] = {}

    def read(self, name: str) -> tuple[str, object]:
        """返回 (status, obj)，status ∈ missing/ok/broken/unreadable。"""
        if name in self.cache:
            return self.cache[name]
        res: tuple[str, object] = ("missing", None)
        p = self.root / name
        try:
            if p.is_file():
                try:
                    raw = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    res = ("unreadable", None)
                else:
                    try:
                        res = ("ok", json.loads(raw))
                    except Exception:
                        res = ("broken", None)
        except OSError:
            res = ("unreadable", None)
        self.cache[name] = res
        return res

    def exists(self, name: str) -> bool:
        try:
            return (self.root / name).is_file()
        except OSError:
            return False


# 每个签名函数：返回 None = 该家的标记文件根本不在（none）；
#               返回 (ok, missing_fields, matched_state_file)。
def _sig_gsw(r: _StateReader):
    st, obj = r.read("writing_progress.json")
    if st == "missing":
        if r.read("project_config.json")[0] == "missing":
            return None
        return (False, ["update_history"], "project_config.json")
    if st != "ok" or not isinstance(obj, dict):
        return (False, ["update_history"], "writing_progress.json")
    if isinstance(obj.get("update_history"), list):
        return (True, [], "writing_progress.json")
    st2, sl = r.read("storyline.json")
    if st2 == "ok" and isinstance(sl, dict):
        secs = sl.get("sections")
        if isinstance(secs, list) and secs and all(
                isinstance(x, dict) and "id" in x for x in secs):
            return (True, [], "writing_progress.json")
    return (False, ["update_history"], "writing_progress.json")


def _sig_rw(r: _StateReader):
    st, obj = r.read("state.json")
    if st == "missing":
        return None
    if st != "ok" or not isinstance(obj, dict):
        return (False, ["completed_sections", "zotero_root_key"], "state.json")
    missing = []
    if not isinstance(obj.get("completed_sections"), list):
        missing.append("completed_sections")
    if "zotero_root_key" not in obj:
        missing.append("zotero_root_key")
    return (not missing, missing, "state.json")


def _project_state_sig(skill_name: str, extra_check=None):
    """nsfc / sci2doc / revise-sci / reviewer-response-sci 共用 project_state.json，
    `skill` 字段是唯一干净的分辨器；nsfc 与 sci2doc 另有字段组合兜底。"""
    def check(r: _StateReader):
        st, obj = r.read("project_state.json")
        if st == "missing":
            return None
        if st != "ok" or not isinstance(obj, dict):
            return (False, ["skill"], "project_state.json")
        if obj.get("skill") == skill_name:
            return (True, [], "project_state.json")
        if extra_check is not None and extra_check(obj):
            return (True, [], "project_state.json")
        return (False, ["skill"], "project_state.json")
    return check


def _nsfc_fallback(obj: dict) -> bool:
    return ("gate" in obj
            and bool(re.match(r"^phase\d+$", str(obj.get("phase") or "")))
            and "project_info" not in obj)


def _sci2doc_fallback(obj: dict) -> bool:
    pi = obj.get("project_info")
    return (isinstance(pi, dict) and "save_path" in pi
            and "progress" in obj and "outline" in obj)


def _sig_revsim(r: _StateReader):
    # 点开头 + 独有名，文件名本身即强证据（INTERFACE §2.6）
    return (True, [], ".reviewer_sim_project.json") if r.exists(
        ".reviewer_sim_project.json") else None


def _sig_polish(r: _StateReader):
    st, obj = r.read("units_index.json")
    if st == "missing":
        return None
    if st != "ok" or not isinstance(obj, dict):
        return (False, ["units"], "units_index.json")
    missing = []
    if not isinstance(obj.get("unit_count"), int) or isinstance(obj.get("unit_count"), bool):
        missing.append("unit_count")
    units = obj.get("units")
    if not isinstance(units, list) or not units or not isinstance(units[0], dict) or not all(
            k in units[0] for k in
            ("idx", "section_type", "heading_level", "has_citation", "has_numeric")):
        missing.append("units")
    return (not missing, missing, "units_index.json")


SIGNATURES = {
    "general-sci-writing": _sig_gsw,
    "review-writing": _sig_rw,
    "nsfc-proposal": _project_state_sig("nsfc-proposal", _nsfc_fallback),
    "sci2doc": _project_state_sig("sci2doc", _sci2doc_fallback),
    "revise-sci": _project_state_sig("revise-sci"),
    "reviewer-response-sci": _project_state_sig("reviewer-response-sci"),
    "reviewer-simulator": _sig_revsim,
    "polish-sci": _sig_polish,
}

# 只为"如实标未知"而额外探一眼的附属文件（不参与分档判定）
AUX_FILES = {"general-sci-writing": ["storyline.json"]}


class Evidence:
    """一次分档结果。tier ∈ strong/weak/none。"""

    __slots__ = ("tier", "skill", "skills", "root", "matched_state_file",
                 "missing_signature", "unknown")

    def __init__(self, tier="none", skill="", skills=None, root=None,
                 matched_state_file="", missing_signature=None, unknown=None):
        self.tier = tier
        self.skill = skill
        self.skills = skills or []
        self.root = root
        self.matched_state_file = matched_state_file
        self.missing_signature = missing_signature or []
        self.unknown = unknown or []


def _unknown_from(reader: _StateReader) -> list:
    out = []
    for name, (st, _) in reader.cache.items():
        if st == "broken":
            out.append("%s 解析失败" % sanitize_field(name, "text"))
        elif st == "unreadable":
            out.append("%s 不可读" % sanitize_field(name, "text"))
    return sorted(out)


def evaluate_dir(d: Path, registry: dict) -> Evidence:
    """只看这一个目录，不向上找。"""
    reader = _StateReader(d)
    strong: list[tuple[str, str]] = []
    weak = None
    for name in registry.get("skills", {}):
        fn = SIGNATURES.get(name)
        if fn is None:
            continue
        try:
            res = fn(reader)
        except Exception as exc:
            # 签名函数自己炸了 ≠ 这不是学术项目。判定仍按"认不出"走（放行），
            # 但不许零痕迹——否则一个 bug 能让整家技能悄悄失去保护。
            audit_append(None, rule="internal-error", decision="unchecked",
                         detail="signature %s" % type(exc).__name__)
            res = None
        if res is None:
            continue
        ok, missing, state_file = res
        if ok:
            strong.append((name, state_file))
        elif weak is None:
            weak = (name, missing, state_file)
    if strong:
        for skill_name, _ in strong:
            for aux in AUX_FILES.get(skill_name, []):
                reader.read(aux)
        return Evidence("strong", strong[0][0], [n for n, _ in strong], d,
                        strong[0][1], [], _unknown_from(reader))
    if weak:
        # weak 的 skill 对外不公布（§4 的例子里 skill 为空串）——"不确定是哪家"
        # 正是 weak 的语义；内部仍留 skills 供 managed_globs 判断用。
        return Evidence("weak", "", [weak[0]], d, weak[2], list(weak[1]),
                        _unknown_from(reader))
    return Evidence("none")


def _candidate_dirs(start: Path) -> list:
    """向上找根的候选目录：最多 MAX_ROOT_DEPTH 层，命中 $HOME 或文件系统根即停。

    不扫 $HOME 自身：家目录里放着各种无关 json，扫它等于把用户所有项目都拖下水。
    """
    try:
        home = Path.home().resolve()
    except Exception:
        home = None
    dirs = []
    cur = start
    for _ in range(MAX_ROOT_DEPTH + 1):
        if cur.parent == cur:          # 文件系统根
            break
        if home is not None and cur == home:
            break
        dirs.append(cur)
        cur = cur.parent
    return dirs


def detect(start: Path, registry: dict | None = None) -> Evidence:
    """从 start 目录向上找项目根并分档。第一个 strong 即根；全程无 strong 但
    出现过 weak → 取最近的那个 weak 目录。"""
    registry = registry if registry is not None else load_registry()
    if not registry.get("skills"):
        return Evidence("none")
    weak_hit = None
    for d in _candidate_dirs(start):
        try:
            if not d.is_dir():
                continue
        except OSError:
            continue
        ev = evaluate_dir(d, registry)
        if ev.tier == "strong":
            return ev
        if ev.tier == "weak" and weak_hit is None:
            weak_hit = ev
    return weak_hit or Evidence("none")


def detect_for_path(path: Path, registry: dict | None = None) -> Evidence:
    """给一个文件/目录路径分档：目录以自身为起点，文件以父目录为起点
    （与钩子里 realpath(file_path) 的语义一致）。路径先 realpath，含 `..`
    或软链解析后落在别处的，按它真正所在的位置判——这正是路径穿越的封堵点。"""
    try:
        real = Path(os.path.realpath(str(path)))
    except Exception:
        return Evidence("none")
    start = real if real.is_dir() else real.parent
    return detect(start, registry)


# ------------------------------------------------------------------ §2.5 差集

def _gsw_left(root: Path) -> list:
    try:
        obj = json.loads((root / "writing_progress.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    hist = obj.get("update_history") if isinstance(obj, dict) else None
    if not isinstance(hist, list):
        return []
    last: dict[str, str] = {}
    for entry in hist:
        if not isinstance(entry, dict):
            continue
        # 老格式事件（如 figure_analyzed）有 section 无 status：不是状态更新，跳过。
        # 不跳的话它会把该节已记的 done 盖成空串 → 左集少一节、F10 少拦一次。
        if "status" not in entry:
            continue
        sid = None
        for key in ("section", "section_id", "id", "name"):
            v = entry.get(key)
            if isinstance(v, str) and v:
                sid = v
                break
        if sid is None:
            continue
        last[sid] = str(entry.get("status") or "").strip().lower()
    # 只看每节最后一条状态；completed_sections/pending_sections 是模板留的死字段
    # （全仓无写入点），名字看着正是差集想要的东西，**一律不采信**。
    return [sid for sid, status in last.items() if status in DONE_STATUS]


def rw_draft_name(section_id: str) -> str:
    """review-writing 草稿文件名：节号点转下划线、各段零填充 2 位。
    正向构造去查，不从文件名反推节号。"""
    return "section_" + "_".join(p.zfill(2) for p in str(section_id).split(".")) + ".md"


def _rw_left(root: Path) -> list:
    try:
        obj = json.loads((root / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    ids = obj.get("completed_sections") if isinstance(obj, dict) else None
    if not isinstance(ids, list):
        return []
    out = []
    for sid in ids:
        if not isinstance(sid, str) or not sid:
            continue
        # 🔴 "草稿存在且非空"这个与条件不能省：complete-section 在 Phase 2 检索
        # 完成时也会调用一次，只看 completed_sections 的话，Phase 2 一结束就
        # 100% 必然把整个项目锁死（此时一个字的正文都还没写）。
        try:
            draft = root / "drafts" / rw_draft_name(sid)
        except Exception:
            continue
        if nonempty(draft):
            out.append(sid)
    return out


def _nsfc_left(root: Path) -> list:
    try:
        names = os.listdir(str(root / "sections"))
    except Exception:
        return []
    out = []
    # 前缀/后缀比对折叠大小写：这是少数几个"自己拿文件名比"的地方（不是 FS 解析），
    # 逐字比的话 `p1_正文.md` 不进左集 → 该节的差集凭空消失 → F10 少拦一次。
    lowered = sorted((n.lower(), n) for n in names)
    for prefix in NSFC_REVIEWED_SECTIONS:
        low_prefix = prefix.lower()
        for low, name in lowered:
            stem = low[:-3] if low.endswith(".md") else None
            # 精确匹配：整名（去 .md）相等或"前缀+下划线"（设计文件名是 p1_正文.md）。
            # 裸 startswith 会让 "p1" 吞掉 "p10_*"（"P2" 吞 "p20_*" 同理）
            # → 不存在的 P1 节被凭空判"已写"，F10 差集漏拦。
            if (stem is not None
                    and (stem == low_prefix or stem.startswith(low_prefix + "_"))
                    and nonempty(root / "sections" / name)):
                out.append(prefix)      # 记规范写法，不记文件里那个大小写
                break
    return out


_SECTION_NUM_RE = re.compile(r"\d+(?:\.\d+)+")


def _sci2doc_left(root: Path) -> list:
    base = root / "atomic_md"
    out = []
    try:
        if not base.is_dir():
            return []
        for dirpath, dirnames, filenames in os.walk(str(base)):
            depth = Path(dirpath).relative_to(base).parts
            if len(depth) >= 3:          # 正常形态只有 atomic_md/第N章/x.md
                dirnames[:] = []
                continue
            for fname in sorted(filenames):
                if not fname.endswith(".md"):
                    continue
                full = Path(dirpath) / fname
                rel = str(full.relative_to(base))
                # 节号取路径里第一处 N.M 形态：优先文件名，文件名里没有（AI 偶尔
                # 把节号写在目录名上、或文件名含异常字符）再看所在子路径。
                m = _SECTION_NUM_RE.search(fname) or _SECTION_NUM_RE.search(rel)
                if not m or not nonempty(full):
                    continue
                sid = m.group(0)
                if sid not in out:
                    out.append(sid)
    except Exception:
        return out
    return sorted(out)


LEFT_SETS = {
    "general-sci-writing": _gsw_left,
    "review-writing": _rw_left,
    "nsfc-proposal": _nsfc_left,
    "sci2doc": _sci2doc_left,
}


def declared_sections(root: Path, skill: str, registry: dict) -> list:
    """左集：本项目里"已声明完成"的节（逐家判据不同，不得统一）。"""
    cfg = (registry.get("skills") or {}).get(skill) or {}
    if not cfg.get("signoff"):
        return []
    fn = LEFT_SETS.get(skill)
    if fn is None:
        return []
    try:
        return fn(root)
    except Exception:
        return []


def pending_review(root: Path, skill: str, registry: dict) -> list:
    """差集 = 声明完成 − 盲检通过。只有 signoff:true 的四家参与；节级，不做章级。"""
    return [sid for sid in declared_sections(root, skill, registry)
            if not review_passed(root, sid)[0]]


def manual_passed(root: Path, skill: str, registry: dict) -> list:
    """人工放行（manual:true）的盲检：差集按 passed==true 放行是对的（设计意图），
    但状态卡必须单列，否则会给 AI 一个"全绿"的假象。"""
    out = []
    for sid in declared_sections(root, skill, registry):
        passed, manual = review_passed(root, sid)
        if passed and manual:
            out.append(sid)
    return out


# ------------------------------------------------------------------ §2.1.1 路径归一化

_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.M)


def extract_file_paths(payload: dict) -> list:
    """取本次工具调用要写的文件路径（三端共用的唯一入口）。

    按序尝试，先命中先返回：
      1. tool_input.file_path（Claude Code / OpenCode 桥接层的形状）
      2. tool_input.notebook_path
      3. tool_input.command 当作 apply_patch 补丁文本扫 `*** Add/Update/Delete File:`
         （Codex 端 tool_input 里没有 file_path，改文件的信息全在补丁文本里）
    返回列表：一次 patch 可改多个文件，逐个过门禁、任一命中即 deny。
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    raw: list[str] = []
    fp = tool_input.get("file_path")
    if isinstance(fp, str) and fp.strip():
        raw.append(fp)
    if not raw:
        nb = tool_input.get("notebook_path")
        if isinstance(nb, str) and nb.strip():
            raw.append(nb)
    if not raw:
        cmd = tool_input.get("command")
        if isinstance(cmd, str) and cmd:
            raw += [m.strip() for m in _PATCH_FILE_RE.findall(cmd) if m.strip()]
    cwd = payload.get("cwd")
    base = cwd if isinstance(cwd, str) and cwd else None
    out, seen = [], set()
    for item in raw:
        try:
            p = Path(item)
            if not p.is_absolute() and base:
                p = Path(base) / p
            p = Path(os.path.realpath(str(p)))
        except Exception:
            continue
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out


def rel_to_root(path: Path, root: Path) -> str | None:
    """相对项目根的 posix 路径；落在根外返回 None（不属于本项目）。"""
    try:
        rel = os.path.relpath(os.path.realpath(str(path)), os.path.realpath(str(root)))
    except Exception:
        return None
    rel = rel.replace(os.sep, "/")
    if rel == ".." or rel.startswith("../"):
        return None
    return rel


def skill_for_rel(ev: "Evidence", registry: dict, rel: str) -> str:
    """同一个根上可能同时立着几家的标记（如 revise-sci 与 reviewer-response-sci
    共用 project_state.json）：谁的 managed_globs 命中这次的目标，就按谁判。
    都不命中 → 空串（该文件不是任何在场技能的受管产物）。"""
    skills = registry.get("skills") or {}
    for name in ev.skills:
        if is_managed(rel, (skills.get(name) or {}).get("managed_globs")):
            return name
    return ""


def is_protected_file(rel: str) -> str:
    """F6 受保护文件：'' / 'signoff' / 'cert'。

    一律小写后再比：两个受保护名本就全小写，而 macOS/Windows 上
    `Structure_Signoff.json`、`.review_pass/2.1.JSON` 指的是同一个文件——
    逐字节比等于留了个"改个大小写就伪造凭证"的口子（实测可复现）。
    全平台统一小写比：Linux 上顶多多拦一个真的叫 `Structure_Signoff.json`
    的无关文件，方向安全。

    附：**state 文件的存在性判定不需要同款处理**（已实测）——`(root/"state.json").is_file()`
    是由文件系统解析的，大小写不敏感 FS 上 `State.json` 天然能被找到，项目不会
    "对门禁隐身"。真正需要手动折叠的是**自己拿名字比对**的地方：本函数、is_managed，
    以及 _nsfc_left 的 listdir 前缀匹配。
    """
    low = str(rel).lower()
    if low == "structure_signoff.json":
        return "signoff"
    if low.startswith(".review_pass/") and low.endswith(".json"):
        return "cert"
    return ""


# ------------------------------------------------------------------ 本机开关（用户可关 / AI 不可关）

SWITCH_NAME = "academic-gate.local.json"
# 开关是几行 JSON。再大一律按畸形处理（＝"开"）：既防被塞垃圾拖慢每次 fire，
# 也免得为了读一个布尔值把几 MB 文件拉进内存。
SWITCH_READ_LIMIT = 256 * 1024

_SWITCH_CACHE = None


def switch_path() -> Path:
    """开关文件的绝对路径。`~` 一律按 $HOME 解析（Path.home() 的既有语义），
    禁止 pwd.getpwuid / 硬编码家目录 —— 那会让整套保护无法在重定向 HOME 下自测。"""
    return Path.home() / ".claude" / SWITCH_NAME


def _read_switch() -> dict:
    """读开关文件。**任何异常一律返回空字典**（= 保护开着、无豁免）。

    fail-safe 方向是硬要求：文件不在 / 坏 JSON / 顶层非对象 / 读不出 / 是目录 /
    断链 / 成环 / 非 UTF-8 字节 / 命名管道或设备文件，全都必须落到"开"那一侧。
    坏文件绝不等于关掉保护。
    唯一的宽容是 BOM（utf-8-sig）：用户是这个文件的唯一合法写者，而不少编辑器默认写
    BOM，把它当坏文件 = 用户以为关了实际没关，是最坏的一种静默失效。
    """
    try:
        p = str(switch_path())
        # 🔴 open 之前先看清是不是普通文件。命名管道（mkfifo）在没有写者时会让
        # open/read 一直阻塞，三个钩子每次触发都卡到 CLI 的超时上限、被判为
        # "钩子失败"→ 一律放行 = 整套门禁被一条 mkfifo 静默下线（实测 >8s 不返回）。
        # 用 os.stat 而不是 lstat：要判的是"最终会被 open 的那个东西"是什么类型，
        # lstat 只看软链本身、会把"软链指向真开关文件"这种合法用法误判成非普通文件。
        # os.stat 自身对 FIFO 不阻塞（阻塞的是 open）。
        if not stat.S_ISREG(os.stat(p).st_mode):
            return {}
        with open(p, "rb") as fh:
            raw = fh.read(SWITCH_READ_LIMIT + 1)
        if len(raw) > SWITCH_READ_LIMIT:
            return {}
        obj = json.loads(raw.decode("utf-8-sig"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def switch_doc() -> dict:
    """本进程内只读一次。每次 hook fire 都是新进程，所以这层 memo 不会让"用户中途
    改了开关"延迟生效；它挡的是 Bash 层逐 token 判定时的几十次重复读盘。"""
    global _SWITCH_CACHE
    if _SWITCH_CACHE is None:
        _SWITCH_CACHE = _read_switch()
    return _SWITCH_CACHE


def enforcement_disabled() -> bool:
    """用户关了拦截层吗。**关闭当且仅当值是 JSON 的 false**（严格身份比较）。

    用 `is False` 不用 `not ...`：后者会把键缺失（None）、0、空串、空数组统统判成
    "关"，那是最不能出错的方向。带引号的 "false" 同样不认。
    """
    return switch_doc().get("enforcement_enabled") is False


def gate_source_edits_allowed() -> bool:
    """维护者豁免（严格 JSON true）。只放开门禁源码目录，不放开 settings 与开关自身；
    豁免字段住在受保护文件里 → AI 无法自我授权。"""
    return switch_doc().get("allow_gate_source_edits") is True


def switch_note() -> str:
    """用户写的关闭理由，只回显给用户（安装器 stdout），不进任何喂给模型的文本。
    非字符串一律当作缺失。"""
    v = switch_doc().get("note")
    return v if isinstance(v, str) else ""


# ------------------------------------------------------------------ 门禁自身文件的写保护

INFRA_RULE = "F11-infra-write"
# 8 家技能 scripts/ 下受保护的门禁文件名。同目录其余脚本（proofread.py 等）不在内：
# 误拦正常维护的代价远大于收益。
INFRA_VENDORED_FILES = frozenset({
    "academic_gate_hook.py", "bash_guard_hook.py", "context_feed_hook.py",
    "context_guard_core.py", "gate_registry.json",
    "structure_signoff_gate.py", "install_gate_hook.py",
})
INFRA_SKILLS = frozenset({
    "general-sci-writing", "review-writing", "nsfc-proposal", "sci2doc",
    "revise-sci", "reviewer-response-sci", "reviewer-simulator", "polish-sci",
})
# 维护者豁免能放开的两类（本仓自己要用 AI 维护这些源码）；settings / 开关 / 部署位
# 一律不放开 —— 放开等于把"AI 不能自我授权"这条设计砸了。
INFRA_EXEMPTABLE = frozenset({"plugin-dir", "vendored"})

# deny 理由住在这里而不是各钩子里：两个入口（工具直写 / 经 shell）必须给同一套说法，
# 分两处写迟早漂。🔴 理由里绝不出现开关字段名、取值写法或任何"怎么关掉门禁"的操作
# 指引 —— deny 理由是被约束方必读的文本，写在这儿就是绕过说明书。
REASON_INFRA = (
    "[学术门禁] {target} 属于学术门禁自身的实现文件，AI 不得修改——改它等于自己拆掉"
    "自己的门禁。这次写入已被拦下。需要改门禁代码时，请把改动内容告诉用户，由用户本人修改。"
)
REASON_INFRA_SWITCH = (
    "[学术门禁] 这个文件是这台机器上的门禁配置，只能由用户本人在自己的编辑器或终端里"
    "修改，AI 的写入一律拦下。需要改它时，正确做法是把要改的内容告诉用户，由用户自己动手。"
)

_INFRA_TARGETS = None


def _norm_path(raw: str) -> str:
    """规范化：realpath（吃掉 `..`、软链）+ 大小写折叠（macOS/Windows 上
    Settings.JSON 与 settings.json 是同一个文件，逐字比 = 改个大小写就绕过）。"""
    real = os.path.realpath(raw)
    return real.lower() if CASE_INSENSITIVE_FS else real


def _infra_targets() -> tuple:
    """([(规范化路径, 类别名)], skills 目录的规范化路径)。每进程算一次。

    清单侧也要 realpath：受保护路径本身可能是软链（用户把开关软链去了别处），
    不解析的话写它的真实目标就绕过去了。
    """
    global _INFRA_TARGETS
    if _INFRA_TARGETS is not None:
        return _INFRA_TARGETS
    pairs = []
    skills = ""
    try:
        base = Path.home() / ".claude"
        for rel, cat in (("academic-gate", "legacy-deploy-dir"),
                         ("skills/academic-gate", "plugin-dir"),
                         ("settings.json", "settings"),
                         ("settings.local.json", "settings"),
                         (SWITCH_NAME, "killswitch")):
            try:
                pairs.append((_norm_path(str(base / rel)), cat))
            except Exception:
                continue
        try:
            skills = _norm_path(str(base / "skills"))
        except Exception:
            skills = ""
    except Exception:
        pairs, skills = [], ""
    _INFRA_TARGETS = (pairs, skills)
    return _INFRA_TARGETS


def _under(real: str, base: str) -> bool:
    """边界前缀：必须是同一条路径或它的子路径。裸 startswith 会让
    academic-gate-notes/ 这种"只是名字开头一样"的无关目录一起挨拦。"""
    return real == base or real.startswith(base + os.sep)


def infra_category(path, cwd=None) -> str:
    """这个写入目标属不属于门禁自己的文件；返回类别名或空串。**不看豁免**。

    path 收原始字符串（可能带 `~`、可能是相对路径、可能畸形）。解析不出来时按命中
    处理 —— 这是整套判据里唯一 fail-closed 的一条，理由是目标集合固定就那几条已知
    绝对路径，误伤面可控，而"解析炸了就放行"正是最好用的绕过口。
    """
    try:
        raw = str(path)
    except Exception:
        return "unparsable"
    if not raw.strip():
        return ""
    try:
        s = os.path.expanduser(raw)
        if not os.path.isabs(s) and cwd:
            s = os.path.join(str(cwd), s)
        real = _norm_path(s)
    except Exception:
        return "unparsable"
    pairs, skills = _infra_targets()
    for base, cat in pairs:
        if _under(real, base):
            return cat
    if skills and real.startswith(skills + os.sep):
        rest = real[len(skills) + 1:].split(os.sep)
        if (len(rest) == 3 and rest[0] in INFRA_SKILLS and rest[1] == "scripts"
                and rest[2] in INFRA_VENDORED_FILES):
            return "vendored"
    return ""


def protected_infra(path, cwd=None) -> str:
    """对外判据：命中且未被维护者豁免放开时返回类别名，否则空串。"""
    cat = infra_category(path, cwd)
    if cat and cat in INFRA_EXEMPTABLE and gate_source_edits_allowed():
        return ""
    return cat


def infra_target_strings(payload: dict) -> list:
    """本次工具调用要写的目标路径**原串**（不 realpath、不丢弃解析失败的那条）。

    与 extract_file_paths 分开是有意的：那个函数会把解析不出的路径静默丢掉，而
    infra 判定恰恰要求"解析不出来 = 按命中拦下"。另外这里多扫 apply_patch 的
    input/patch 两个字段（Codex 端不同版本的形状），只多不少。
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    out = []
    for key in ("file_path", "notebook_path"):
        v = tool_input.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v)
    for key in ("command", "input", "patch"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            out += [m.strip() for m in _PATCH_FILE_RE.findall(v) if m.strip()]
    seen, uniq = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


# ------------------------------------------------------------------ 技能安装目录探测

def skill_scripts_dir(skill: str) -> str | None:
    """按 插件根 → ~/.claude/skills → opencode 镜像 → codex 镜像 顺序取第一个存在的。
    让 AI 每轮猜一次脚本住址是纯浪费；四处都找不到就退化成不带路径的说法。"""
    if not skill:
        return None
    cands = []
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        cands.append(Path(root) / "skills" / skill / "scripts")
    home = Path.home()
    cands += [
        home / ".claude" / "skills" / skill / "scripts",
        home / ".config" / "opencode" / "skills" / skill / "scripts",
        home / ".codex" / "skills" / skill / "scripts",
    ]
    for c in cands:
        try:
            if c.is_dir():
                return sanitize_field(str(c), "text", 200)
        except OSError:
            continue
    return None


def _interpreter() -> str:
    """挑吐给 AI 的命令用的解释器名：探测 PATH 上真实存在的裸名，两个都不在时
    退 sys.executable 绝对路径兜底。写死 python3 的命令在只有 python 的
    Windows 上照抄就是断的——与 verify_command docstring 讲的路径引号是同一条
    道理，给跑不起来的命令比不给还糟。

    🔴 口径必须与 install_gate_hook._interpreter() 完全一致（先 python3 再
    python，理由见那边 docstring：按探测不按平台猜）。两边是有意的小重复而非
    互相 import：install_gate_hook 是自愈/修复工具，职责含重新部署损坏的本文件，
    修复工具 import 被修复对象 = 被修对象坏掉时修复工具跟着炸。4 行纯逻辑的
    重复由 tests/unit/test_interpreter_probe_lock.py 三分支逐一断相等锁死。"""
    for name in ("python3", "python"):
        if shutil.which(name):
            return name
    return sys.executable or "python3"


def verify_command(skill: str, root=None, with_root: bool = True) -> str:
    """本项目的盲检命令（真实路径，禁止吐 <技能安装目录> 这种占位符字面量）。

    路径先清洗、再 shlex.quote：用户目录里带空格是常态（如 `~/Documents/My Papers`），
    不加引号的话 AI 照抄这条命令就是断的 —— 给了个跑不起来的命令，比不给还糟。
    解释器名同理：运行时探测（_interpreter），不写死 python3。
    """
    d = skill_scripts_dir(skill)
    if d:
        # 兜底的 sys.executable 绝对路径可能含空格，与脚本路径同取向 quote；
        # 裸名 quote 后原样不变
        cmd = "%s %s verify --section <节号>" % (
            shlex.quote(_interpreter()),
            shlex.quote("%s/delegate_review.py" % d))
    else:
        cmd = "本技能 scripts/ 下的 delegate_review.py verify --section <节号>"
    if with_root and root is not None:
        cmd += " --root %s" % shlex.quote(sanitize_field(str(root), "text", 200))
    return cmd


# ------------------------------------------------------------------ §5.2 审计

def _clean_or_empty(value, maxlen: int) -> str:
    """缺值写空串（§5.2），不要走清洗——空串进 sanitize_field 会得到
    <非常规名称已省略>，既违反"缺值写空串"，又把这个注入哨兵稀释成日常噪音
    （每条 weak ask 的 skill 槽都会命中它，grep 出来全是假线索）。"""
    return sanitize_field(value, "text", maxlen) if value else ""


def _audit_line(event, tool, rule, decision, skill, target, detail) -> str:
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": _clean_or_empty(event, 40),
        "tool": _clean_or_empty(tool, 40),
        "rule": rule or "",
        "decision": decision or "",
        "skill": _clean_or_empty(skill, 60),
        "target": _clean_or_empty(target, 200),
        "detail": _clean_or_empty(detail, 200),
        "pid": os.getpid(),
    }
    return json.dumps(rec, ensure_ascii=False)


def _ensure_gitignored(root: Path) -> None:
    """首写时若同目录**已存在** .gitignore 且没有该行，追加一行。
    不存在就不创建——不在用户项目里凭空造文件。

    🔴 全程二进制，**绝不解码用户的文件**：上一版是"文本读回 + 整份重写"，
    errors="replace" 会把 GBK/Latin-1 编码的 .gitignore（中文 Windows 上很常见）
    里的中文注释永久变成 U+FFFD —— 我们把用户的文件改坏了，这是本项目最不能犯的
    一类错。追加模式只往末尾加字节，原有内容一个字节都不碰。
    """
    try:
        gi = root / ".gitignore"
        if not gi.is_file():
            return
        line = AUDIT_NAME.encode("utf-8")
        with open(str(gi), "rb") as fh:
            data = fh.read()
        if line in data:
            return
        with open(str(gi), "ab") as fh:
            if data and not data.endswith(b"\n"):
                fh.write(b"\n")     # 末尾没换行时先补一个，别把新行粘到旧行上
            fh.write(line + b"\n")
    except Exception:
        pass


def audit_append(root, event="", tool="", rule="", decision="", skill="",
                 target="", detail="") -> None:
    """追加一行审计。写失败一律吞异常，**决策绝不改变**——审计是记录，不是许可。

    落点 <项目根>/.academic_gate_audit.jsonl；只有 NO_ROOT_RULES 里那几条"那一刻
    根本没有项目根"的规则允许落 CLAUDE_PLUGIN_DATA，连该变量也没有就不写。
    除此之外一律不写——宁可少一条记录，也不在陌生目录造文件。
    """
    try:
        if root is not None:
            path = Path(root) / AUDIT_NAME
            first = not path.exists()
        elif rule in NO_ROOT_RULES:
            data = plugin_data_dir()
            if data is None and rule in HOME_AUDIT_RULES:
                # legacy 装法通常没有 CLAUDE_PLUGIN_DATA。F11 的目标路径本来就在
                # ~/.claude 下，回落到同一目录不算"在陌生目录造文件"。
                try:
                    data = Path.home() / ".claude"
                    data.mkdir(parents=True, exist_ok=True)
                except Exception:
                    data = None
            if data is None:
                return
            path = data / "academic_gate_audit.jsonl"
            first = False
        else:
            return
        try:
            if path.exists() and path.stat().st_size > AUDIT_MAX_BYTES:
                backup = Path(str(path) + ".1")
                if backup.exists():
                    backup.unlink()
                path.rename(backup)
        except Exception:
            pass
        line = _audit_line(event, tool, rule, decision, skill, target, detail)
        with open(str(path), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if root is not None and first:
            _ensure_gitignored(Path(root))
    except Exception:
        pass


# ------------------------------------------------------------------ 待报状态（S8 分支 B）

def _atomic_write(path: Path, text: str) -> None:
    """覆盖写一律"临时文件 + os.replace"：这三个状态文件（心跳/去重/待报）会被
    并发的钩子进程同时写，直接 write_text 中途被打断就留下半截内容，下次读到的是
    垃圾。os.replace 在同一文件系统上是原子的。写失败一律吞——它们都是省事用的，
    不是正确性。"""
    tmp = None
    try:
        tmp = path.with_name(path.name + ".tmp%d" % os.getpid())
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _digest(text: str) -> str:
    """只拿来当文件名的短哈希，不是安全用途。usedforsecurity=False：FIPS 模式的
    Python 里 md5 默认不可用、直接抛，喂层就整个哑了。"""
    try:
        return hashlib.md5(text.encode("utf-8", "replace"),
                           usedforsecurity=False).hexdigest()
    except TypeError:      # Python < 3.9 没这个关键字
        return hashlib.md5(text.encode("utf-8", "replace")).hexdigest()


def _notice_path(key: str):
    # 整个包 try：plugin_data_dir 会 mkdir、_digest 会编码，都可能抛；
    # 待报状态存不下是可接受的降级，绝不能因此把钩子掀翻。
    try:
        data = plugin_data_dir()
        if data is None or not key:
            return None
        return data / ("pending_notice_%s.txt" % _digest(str(key)))
    except Exception:
        return None


def push_notice(key: str, text: str) -> None:
    """留一条待报，由下一次 UserPromptSubmit 的状态卡补报（NOTICE_MODE="B"）。"""
    p = _notice_path(key)
    if p is None:
        return
    _atomic_write(p, text)


def pop_notice(key: str) -> str:
    """读后即删。取不到返回空串。"""
    p = _notice_path(key)
    if p is None:
        return ""
    try:
        if not p.is_file():
            return ""
        text = p.read_text(encoding="utf-8", errors="replace").strip()
        p.unlink()
        return text
    except Exception:
        return ""


# ------------------------------------------------------------------ 去重（§1.2.1 规则 2）

def card_is_duplicate(root_key: str, text: str) -> bool:
    """与上次注入的内容相同 → True（不注入）。存不下就当没重复过，照常注入
    ——去重是省钱，不是正确性。"""
    data = plugin_data_dir()
    if data is None or not root_key:
        return False
    digest = _digest(str(root_key))
    path = data / ("last_card_%s.txt" % digest)
    now = _digest(text)
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip() == now:
            return True
    except Exception:
        pass
    _atomic_write(path, now)
    return False


# ------------------------------------------------------------------ explain CLI

EXPLAIN_KEYS = ("tier", "skill", "root", "signoff", "pending_review",
                "missing_signature", "matched_state_file", "unknown")


def explain(path_str: str) -> tuple[int, dict]:
    """返回 (退出码, 输出对象)。键集固定 8 个，缺值填空，不随 tier 变化。"""
    if not path_str:
        return 2, {"error": "路径为空"}
    try:
        exists = os.path.exists(path_str)
        lexists = os.path.lexists(path_str)
    except Exception:
        exists = lexists = False
    if not exists:
        shown = sanitize_field(path_str, "text", 200)
        if lexists:
            return 2, {"error": "路径不存在(断开的软链): %s" % shown}
        return 2, {"error": "路径不存在: %s" % shown}

    registry = load_registry()
    ev = detect_for_path(Path(path_str), registry)
    out = {
        "tier": ev.tier,
        "skill": sanitize_field(ev.skill, "ident") if ev.skill else "",
        "root": sanitize_field(str(ev.root), "text", 200) if ev.root else "",
        "signoff": bool(((registry.get("skills") or {}).get(ev.skill) or {}).get("signoff")),
        "pending_review": [],
        "missing_signature": sanitize_list(ev.missing_signature, "ident"),
        "matched_state_file": sanitize_field(ev.matched_state_file, "text", 120)
                              if ev.matched_state_file else "",
        "unknown": sanitize_list(ev.unknown, "text", 120),
    }
    if ev.tier == "strong" and ev.root is not None:
        out["pending_review"] = sanitize_list(
            pending_review(ev.root, ev.skill, registry), "ident")
    return 0, out


def _usage() -> str:
    return ("用法: context_guard_core.py explain <路径>\n"
            "  explain  报告该路径所属项目的证据档位、技能、差集等（固定 8 键 JSON）\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "explain":
        sys.stderr.write(_usage())
        return 2
    try:
        code, obj = explain(argv[1])
    except Exception as exc:  # 内部异常也给结构化输出，别让排障的人看 traceback
        code, obj = 2, {"error": "%s: %s" % (type(exc).__name__,
                                             str(exc).splitlines()[0] if str(exc) else "")}
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
