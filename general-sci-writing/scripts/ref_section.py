"""参考文献段标题识别 —— 全脚本唯一口径。

此前同一个判断分散成 4 份互不相同的正则（state_manager 两处、merge_manuscript、
cross_section_consistency），`## Bibliography` / `**References**` / `## 参考文献：`
只有一部分脚本认得。后果：`word-count` 把认不得的参考文献段算进正文（正文 9 词 +
30 条参考文献能多算约 400 词，直接把 SKILL.md "超 10% 必砍"的字数门禁带偏），
`merge --relocate-references` 也认不出这三种写法，各节参考列表被当正文并进合并稿。

要改识别口径，只改这个文件。

**不要把这里换成正则**：style_checker 那份同类判断因 ReDoS 被专门改成线性消费
（"References" + 1600 空格 + "x" 一次 .match() 要 4 秒，PDF 转文本的目录行就是
这个形状）。下面全部是左到右一次扫描，无回溯。
"""

# 长的排前面：先试 "references" 再试 "reference"，否则前者会被后者吃掉前缀。
# 只收 SCI 体例真正会用的标签。"Works Cited"（MLA/人文体例）故意不收：
# 它不出现在 SCI 稿里，收进来反而与 style_checker 的标签集产生分歧。
REF_LABELS = ("references", "reference", "bibliography", "参考文献", "引用文献")

# 标题里的装饰字符：**References** / __References__ / ## References ##
_DECOR = "*_#"
# 编号前缀允许的字符（"7." / "3.1)" / "2、"）
_NUM_CHARS = ".．、)）:："

# 标签词后面允许跟的尾巴，白名单而非"随便跟"。
# Nature 体例的参考文献段就叫 "References and Notes"，不认它等于 P1-B 原样复发；
# 但放开成前缀匹配又会把 "## Reference genome alignment"（Methods 里的正经小标题）
# 当成参考文献段起点，那会把整节正文从词数里抹掉。
# ponytail: 白名单只漏不误 —— 漏了退化成"当普通标题"，不会吞掉正文。
_ALLOWED_TAILS = ("and notes", "& notes", "and note", "cited", "list")


def _strip_leading_number(text):
    """吃掉标题里的编号前缀 "7." / "3.1)"；没有编号就原样返回。

    只在确实以数字开头时才吃，避免把正文里的别的东西当编号。
    """
    i = 0
    while i < len(text) and (text[i].isdigit() or text[i] in _NUM_CHARS):
        i += 1
    if i and text[0].isdigit():
        return text[i:].lstrip()
    return text


def is_reference_heading(line):
    """整行就是一个参考文献段标题时返回 True。

    认得：``## References`` / ``## Bibliography`` / ``**References**`` /
    ``## 参考文献：`` / ``## 参考文献`` / 裸行 ``References`` / ``## 7. References`` /
    编号包在装饰里的夹心形态 ``## **8. References**``。

    不认（关键的不误伤）：行里除了标签词还有别的内容，例如正文
    ``The method cites references [1,2] for details.`` —— 两端都锚定，
    多一个字就不算标题。
    """
    s = (line or "").strip()
    if not s:
        return False

    # ATX 标题标记；> 6 个 # 在 markdown 里不是标题
    hashes = len(s) - len(s.lstrip("#"))
    if hashes > 6:
        return False
    s = s[hashes:].lstrip()

    # 编号前缀只在带 # 的标题里吃。裸行不吃：目录里的 "3. References"
    # 是条目不是段起点，吃掉编号会让 word-count 从目录处就截断。
    if hashes:
        s = _strip_leading_number(s)

    s = s.lstrip(_DECOR).lstrip()
    # 编号包在装饰符号里的夹心形态（## **8. References**，两份真稿复发）：装饰剥掉
    # 之后编号才露头，再吃一次。仍只在带 # 的标题里吃，裸行口径不变（目录里的
    # 裸 "**8. References**" 是条目不是段起点，与裸 "8. References" 同样不认）。
    if hashes:
        s = _strip_leading_number(s)

    for kw in REF_LABELS:
        if s[:len(kw)].lower() == kw:
            s = s[len(kw):]
            break
    else:
        return False

    s = s.lstrip().lstrip(_DECOR).lstrip()
    if s[:1] in (":", "："):
        s = s[1:]
    s = s.strip()
    if not s:
        return True
    return s.lower() in _ALLOWED_TAILS


def find_reference_heading_offset(content):
    """返回正文里第一个参考文献段标题的起始字符偏移；没有则返回 None。"""
    pos = 0
    for line in (content or "").splitlines(keepends=True):
        if is_reference_heading(line):
            return pos
        pos += len(line)
    return None


def strip_reference_section(content):
    """砍掉参考文献段及其之后的内容，返回正文部分。"""
    offset = find_reference_heading_offset(content)
    return (content or "") if offset is None else (content or "")[:offset]


if __name__ == "__main__":
    YES = ["## References", "## Bibliography", "**References**", "## 参考文献：",
           "## 参考文献", "# REFERENCES", "References", "参考文献",
           "## 7. References", "###  Bibliography  ", "**参考文献**", "## References ##",
           "__References__", "## 引用文献", "#References",
           "## References and Notes", "## Reference List",
           "## **8. References**", "## **7. Bibliography**", "## **3. 参考文献**"]
    NO = ["The method cites references [1,2] for details.",
          "References were formatted per journal style.",
          "## Reference genome alignment", "1. Smith J. Title. Journal. 2020;1:1-9.",
          "参考文献格式见附录", "本节引用文献共 30 条", "", "   ",
          "####### References", "## Reference standards apply",
          "## **8. References** extra", "## **7. Competing Interests**",
          "## **8. Reference genome**", "**8. References**"]
    for line in YES:
        assert is_reference_heading(line), f"该认得却认不得: {line!r}"
    for line in NO:
        assert not is_reference_heading(line), f"不该认却认了: {line!r}"

    body = "Nine words of real body text go right here.\n\n## Bibliography\n\n1. a\n2. b\n"
    assert strip_reference_section(body).split() == \
        "Nine words of real body text go right here.".split()
    assert strip_reference_section("no refs here") == "no refs here"
    assert find_reference_heading_offset("a\n## References\n") == 2

    # ReDoS 哨兵：目录行形状（标签 + 长空格 + 页码）必须是线性时间。
    import time
    t = time.time()
    for n in (400, 800, 1600, 3200):
        is_reference_heading("References" + " " * n + "12")
    assert time.time() - t < 0.5, "ReDoS 回退：识别退化成非线性"

    print("PASS ref_section.py self-check")
