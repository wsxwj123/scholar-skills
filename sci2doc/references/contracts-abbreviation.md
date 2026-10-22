> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Abbreviation Contract

Rules:
- Before writing any new section, query the abbreviation registry to check which abbreviations are already known.
- When introducing a new abbreviation for the first time, use the full pattern: `中文全称（英文全称，缩写）`，例：`聚焦超声（focused ultrasound，FUS）`。英文全称按期刊惯例书写，**大小写均可**（`focused ultrasound` 与 `Polymerase Chain Reaction` 都合法）；含希腊字母（γ/β/α）须**原样保留**，缩写与全称都不得在希腊字母处截断（写 `IFN-γ` / `TGF-β`，不得残缺为 `IFN-`）。
- 中文全称前**不接动词或介词**：直接以术语起首（写"聚焦超声（…）"，不写"采用/使用/在聚焦超声（…）"），否则动词会被吞进全称，污染缩略语表。
- After the first occurrence is registered, all subsequent uses must be the bare abbreviation only.
- After AI generates a section markdown, run `abbreviation_registry.py process` to extract, register, and strip redundant expansions before saving.
- 缩略语对照表为三列：**英文缩写 / 英文全称 / 中文全称**（auto-generated from registry during full-thesis Word conversion）。

命令：`abbreviation_registry.py list`（写前查询）/ `process --file ... --in-place`（写后注册+去重展开）/ `table`（生成缩略语表 md）/ `validate`（交叉引用校验）。完整 CLI 见 `QUICK_START.md`。

