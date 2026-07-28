#!/usr/bin/env python3
"""idea-bomb Zotero 只读读取器。

直接读 Zotero 的 zotero.sqlite（immutable 模式，无需开着 Zotero、无需 API key、无需联网）。
输出一律 JSON，供上层技能解析。

ponytail: 直连 Zotero 内部 sqlite schema。这是"不受支持"的内部接口，跨 Zotero 大版本
字段名可能变；真变了就来这里改字段名（升级路径：改用 pyzotero 本地 API zot=Zotero(...,local=True)，
需 Zotero 开着但 schema 无关）。当前对 Zotero 7.x schema 有效。

数据目录探测顺序：~/.idea-bomb/config.json 的 zotero_data_dir → 各 profile prefs.js → 常见位置。

用法：
  zotero_read.py collections            # 文件夹列表 + 条目数
  zotero_read.py search "<关键词>" [n]   # 按标题/摘要搜，返回 key+标题
  zotero_read.py get <itemKey>          # 单篇全部元数据
  zotero_read.py sample [n]             # 随机 n 篇（默认1），给"没方向时扔点东西"用
  zotero_read.py selftest               # 自检：能读到文件夹和一篇文献
"""
import glob
import json
import os
import re
import sqlite3
import sys

HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".idea-bomb", "config.json")
REAL = "it.typeName NOT IN ('attachment','note','annotation')"


def find_data_dir():
    if os.path.exists(CONFIG):
        try:
            d = json.load(open(CONFIG, encoding="utf-8")).get("zotero_data_dir")
            if d and os.path.exists(os.path.join(d, "zotero.sqlite")):
                return d
        except Exception:
            pass
    for pref in glob.glob(os.path.join(HOME, "Library/Application Support/Zotero/Profiles/*/prefs.js")):
        try:
            m = re.search(r'extensions\.zotero\.dataDir",\s*"([^"]+)"',
                          open(pref, encoding="utf-8", errors="ignore").read())
            if m and os.path.exists(os.path.join(m.group(1), "zotero.sqlite")):
                return m.group(1)
        except Exception:
            pass
    for d in (os.path.join(HOME, "Zotero"), os.path.join(HOME, "Zotero default")):
        if os.path.exists(os.path.join(d, "zotero.sqlite")):
            return d
    return None


def connect():
    d = find_data_dir()
    if not d:
        sys.exit("找不到 Zotero 数据目录。请在 ~/.idea-bomb/config.json 里设 zotero_data_dir。")
    con = sqlite3.connect(f"file:{os.path.join(d, 'zotero.sqlite')}?immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    return con


def field(con, item_id, name):
    r = con.execute(
        "SELECT idv.value FROM itemData d JOIN fields f ON d.fieldID=f.fieldID "
        "JOIN itemDataValues idv ON d.valueID=idv.valueID WHERE d.itemID=? AND f.fieldName=?",
        (item_id, name)).fetchone()
    return r["value"] if r else None


def item_collections(con, item_id):
    return [r["collectionName"] for r in con.execute(
        "SELECT c.collectionName FROM collectionItems ci "
        "JOIN collections c ON ci.collectionID=c.collectionID WHERE ci.itemID=?", (item_id,))]


def item_tags(con, item_id):
    return [r["name"] for r in con.execute(
        "SELECT t.name FROM itemTags itg JOIN tags t ON itg.tagID=t.tagID WHERE itg.itemID=?", (item_id,))]


def item_creators(con, item_id):
    out = []
    for r in con.execute(
        "SELECT cr.firstName, cr.lastName FROM itemCreators ic "
        "JOIN creators cr ON ic.creatorID=cr.creatorID WHERE ic.itemID=? ORDER BY ic.orderIndex", (item_id,)):
        out.append(" ".join(x for x in (r["lastName"], r["firstName"]) if x))
    return out


def brief(con, item_id):
    return {"key": con.execute("SELECT key FROM items WHERE itemID=?", (item_id,)).fetchone()["key"],
            "title": field(con, item_id, "title"),
            "collections": item_collections(con, item_id)}


def cmd_collections(con):
    return [{"name": r["n"], "count": r["cnt"]} for r in con.execute(
        "SELECT c.collectionName n, (SELECT COUNT(*) FROM collectionItems ci "
        "WHERE ci.collectionID=c.collectionID) cnt FROM collections c ORDER BY cnt DESC")]


def cmd_search(con, q, limit=20):
    ids = [r["itemID"] for r in con.execute(
        f"SELECT DISTINCT i.itemID FROM items i JOIN itemTypes it ON i.itemTypeID=it.itemTypeID "
        f"JOIN itemData d ON d.itemID=i.itemID JOIN fields f ON d.fieldID=f.fieldID "
        f"JOIN itemDataValues idv ON d.valueID=idv.valueID "
        f"WHERE {REAL} AND f.fieldName IN ('title','abstractNote') AND idv.value LIKE ? LIMIT ?",
        (f"%{q}%", limit))]
    return [brief(con, i) for i in ids]


def cmd_get(con, key):
    row = con.execute(
        f"SELECT i.itemID FROM items i JOIN itemTypes it ON i.itemTypeID=it.itemTypeID "
        f"WHERE i.key=? AND {REAL}", (key,)).fetchone()
    if not row:
        return {"error": f"未找到条目 {key}"}
    iid = row["itemID"]
    date = field(con, iid, "date") or ""
    ym = re.search(r"\d{4}", date)
    return {"key": key, "title": field(con, iid, "title"), "authors": item_creators(con, iid),
            "year": ym.group(0) if ym else None, "doi": field(con, iid, "DOI"),
            "publication": field(con, iid, "publicationTitle"),
            "abstract": field(con, iid, "abstractNote"),
            "tags": item_tags(con, iid), "collections": item_collections(con, iid)}


def cmd_sample(con, n=1):
    ids = [r["itemID"] for r in con.execute(
        f"SELECT i.itemID FROM items i JOIN itemTypes it ON i.itemTypeID=it.itemTypeID "
        f"WHERE {REAL} AND EXISTS (SELECT 1 FROM itemData d JOIN fields f ON d.fieldID=f.fieldID "
        f"WHERE d.itemID=i.itemID AND f.fieldName='abstractNote') ORDER BY RANDOM() LIMIT ?", (n,))]
    return [cmd_get(con, brief(con, i)["key"]) for i in ids]


def cmd_selftest(con):
    cols = cmd_collections(con)
    assert cols and cols[0]["count"] >= 0, "读不到文件夹"
    s = cmd_sample(con, 1)
    assert s and s[0].get("title"), "读不到样本文献标题"
    return {"ok": True, "collections": len(cols), "sample_title": s[0]["title"]}


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    con = connect()
    cmd = args[0]
    if cmd == "collections":
        out = cmd_collections(con)
    elif cmd == "search":
        out = cmd_search(con, args[1], int(args[2]) if len(args) > 2 else 20)
    elif cmd == "get":
        out = cmd_get(con, args[1])
    elif cmd == "sample":
        out = cmd_sample(con, int(args[1]) if len(args) > 1 else 1)
    elif cmd == "selftest":
        out = cmd_selftest(con)
    else:
        sys.exit(f"未知命令: {cmd}\n{__doc__}")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
