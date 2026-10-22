> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## 缩略语首展一致性(Abbreviation Consistency)
改稿最易破坏缩略语一致性:改某句时删掉了首展、在首展之前的位置裸用 ABBR、或新增术语未首展。规则:
- **首展格式**:英文 `Full Name (ABBR)`;中文正文 `中文全称（English Full Name, ABBR）`。同一缩写全文只首展一次,之后裸用 ABBR,不重复展开。
- **Title 禁缩写**(DNA/RNA/PCR 等通用词除外);Abstract 独立,即使正文已定义,Abstract 内首次出现仍应重新展开。
- **改稿守则**:替换/删除句子时若该句承载某缩写的唯一首展,须把首展移到改后稿中该缩写的新首现处;新引入的术语必须在首现处首展。
- **核查**:`manuscript_index.py` 对改后稿产 `abbreviation_index.json`。`undefined_use`(裸用未定义)/`duplicate_definition`(重复首展)/`title_abbreviation`(Title 含缩写)为硬错须修;`defined_unused`(定义后未再用)为软警告,人工取舍。通用缩写见脚本 `UNIVERSAL_ABBREVIATIONS` 白名单,自动跳过。索引为启发式辅助,可疑项人工复核。
