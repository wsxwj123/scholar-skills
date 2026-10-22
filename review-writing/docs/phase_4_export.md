> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Phase 4: Export & Finalization（Step 1–5、5b–8 全部步骤）

**Start: Read `outline.md` + `state.json`. If state.json shows phase=4 and completed=true, skip.**

**⚠️ MANDATORY entry gate: block Phase 4 when pending sections remain (Polish Mode):**
```bash
python3 scripts/state_manager.py check-pending
```
Write Mode has no `pending_sections` field so this gate is a no-op (no key → empty dict → pass).

> **⚠️ HALT before Round 3 sweep.** Show user:
> - Sections to search: [list from outline.md]
> - Estimated: ~5–10 new preprints per section
>
> Ask: "Proceed with Round 3 preprint sweep? (yes / skip)"
> **Do not proceed until explicit user answer.** If "skip" → record `"round3_papers": 0` in state.json and jump to Step 2.

1. **Round 3 search:** Scan arXiv/preprints (last 6 months) for each section topic → add to relevant sections.
2. **Citation consistency + online validation:**

   **Polish Mode guard** (skip Steps 2a–2b when EITHER condition below holds; on hit, append `Citations not validated — manual review required.` to outline.md Current Status):
   ```bash
   # Empty index — no citations to validate
   python3 -c "import json,pathlib; p=pathlib.Path('data/literature_index.json'); exit(0 if (not p.exists() or len(json.loads(p.read_text(encoding='utf-8') or '[]'))==0) else 1)" && echo "GUARD: empty index → skip 2a-2b"
   # OR state.json marks citations as not imported
   python3 -c "import json,pathlib; s=json.loads(pathlib.Path('state.json').read_text(encoding='utf-8')); exit(0 if s.get('citations_imported') is False else 1)" && echo "GUARD: citations_imported=false → skip 2a-2b"
   ```
   **引用总量校验（警告性，不阻断；尊重用户自定的短篇长度）:**
   ```bash
   python3 scripts/state_manager.py count-citations --drafts-dir drafts --threshold 150
   ```
   > **类型分布（人工核对）：** literature_index.json 未记录 Original/Review/Preprint 类型字段，无法机器统计。AI 对照 Constraints §2 的**软目标**（按学科浮动、类型配比按论点性质、预印本按需）人工抽查 index，明显失衡时提示用户；不按固定配额卡数。

   ```bash
   python3 scripts/check_global_citation_sequence.py
   python3 scripts/validate_citations.py --live --live-used-only --fail-on-orphan --fail-on-live --fail-on-trace --retries 2
   # 🔴 --fail-on-live / --fail-on-trace 必带：不带时联网核验失败（编造 DOI 打 404）
   #    只打 [LIVE-FAIL] 行而退出码仍为 0，会被误读成通过。
   # Final citation guard pass: write verification results back to index
   python3 scripts/citation_guard.py \
     --index data/literature_index.json \
     --log data/citation_guard_report.json \
     --write-back \
     --manual-review data/manual_review_queue.json
   ```
   If non-zero exit → list all gaps; block compilation until resolved.
   `--write-back`: persists `verified:true/false` fields into literature_index.json for traceability.
   `--manual-review`: writes unverifiable entries to `data/manual_review_queue.json` for human check; does NOT block compilation unless `--require-mcp` is also set.

   > **【P4·文献抽验·用户必做】** 综述的命是引文。文献进正文前用户应抽 2-3 篇让 AI 报 PMID/DOI 自己去 PubMed 核对。⚠️ 你在 Windows 上 edirect 联网核验常跑不起来（本 SKILL 已注明 edirect 在 PowerShell/CMD 不可用），**一旦不能真的联网查，AI 必须停下告诉用户，绝不许硬着头皮编 DOI/年份**。`validate_citations.py --live` 跑不起来时明说「联网核验不可用」，不许自判通过。
3. **Export bibliography:**
   ```
   [Zotero] python3 scripts/zotero_manager.py --export-bibtex \
              --output exports/references.bib --root-key ROOT_KEY
   [None/EndNote]   python3 scripts/export_bibtex.py \
              --input data/literature_index.json \
              --output exports/references.bib \
              --clean
   ```

4. **Compile:** Merge all section drafts in correct order（**跑这条，跨平台**）:
   ```bash
   python3 scripts/compile_manuscript.py merge --drafts-dir drafts --out exports/Final_Review.md
   # 按文件名数字段排序合并，强制写 UTF-8 无 BOM；打印实际合并了哪些节，核对是否为大纲顺序。
   # 非 zero-pad 文件名也能排对，但建议统一：mv drafts/section_1_1.md drafts/section_01_01.md
   ```
   > **🔴 别用 shell 重定向合并。** POSIX 下的等价形态是 `cat drafts/section_*.md > exports/Final_Review.md`（仅供理解本步在做什么）；**PowerShell 下绝对不要跑它**——PowerShell 5.1 的 `>` 默认写 UTF-16LE，而下游 `consolidate_references.py` / `structure_outline.py` / `export_docx.py` 全是 `read_text(encoding='utf-8')`，会当场 UnicodeDecodeError，Phase 4 从 4a 起全线崩。上面的脚本没有这个问题。
   > **导出范围注记：** Markdown（`exports/Final_Review.md`）是中间产物；最终 docx 由本技能 Step 5d 的 `scripts/export_docx.py` 产出。字符级排版契约里的上下标 `^...^`/`~...~` 通过 pandoc 的 `+superscript+subscript` 扩展转换，正文/标题字体（Times New Roman、标题加粗）由 `templates/reference.docx` 锁定（该模板由 `scripts/make_reference_docx.py` 烘焙）。图注和表注比正文小一号锁 10pt，摘要走独立样式层同样 10pt。
   4a. **Consolidate references into ONE global list** (run immediately after the `cat` merge):
   ```bash
   python3 scripts/consolidate_references.py \
     --md exports/Final_Review.md \
     --index data/literature_index.json
   ```
   > 写作阶段（Phase 3 规则 7）每节自带 `## References` 是**自包含核验用**，保证每节引用都能当场对账。`cat` 拼接会把这些每节列表全部塞进最终稿，导致 docx 出现多个参考表。本步把正文里散落的所有每节 `## References` 块**剥掉**，按全局编号 `[n]` 升序在**文末重建唯一一个** `## References`（Vancouver 条目来自 `literature_index.json`）。脚本幂等；若某 `[n]` 在 index 查不到，stderr 警告但不阻断导出（退出码仍 0），按需补 index 后重跑。
   4b. **Cross-section coherence scan** (on compiled `exports/Final_Review.md`):
   Read the full compiled text sequentially and check:
   - **Transition continuity:** The opening of each section/subsection must logically connect to the closing of the previous one. Flag abrupt topic jumps with no bridging sentence.
   - **Cross-references:** If Section 3.2 discusses a mechanism introduced in Section 2.1, it should contain an explicit reference ("as discussed in Section 2.1" or equivalent). Flag implicit back-references that assume the reader remembers without a pointer.
   - **Argument arc:** The review's overall narrative should follow the outline's intended logic (e.g., "background → mechanisms → applications → challenges → future"). Flag sections that repeat points already made elsewhere or contradict earlier conclusions without acknowledging the contradiction.
   - **Introduction funnel check:** Introduction must narrow from broad field → specific gap → this review's contribution. Flag introductions that jump directly to specifics without establishing context.
   - **Conclusion echo check:** Conclusion must directly address the Research Question(s) from `outline.md` and reference key findings from body sections. Flag conclusions that introduce new claims not supported in the body.
   - If violations found → AI fixes inline in `exports/Final_Review.md`, adds transition sentences or cross-references, and propagates changes back to source `drafts/section_XX_XX.md`.

   4c. **Abbreviation consistency scan**（先跑脚本硬门，再做脚本盖不住的人工补查）：
   ```bash
   python3 scripts/abbreviation_consistency.py --drafts-dir drafts
   ```
   > **参数别照抄 gsw**：本家这份脚本只认 `--drafts-dir`（`--help` 实测），**不认** gsw 那份的 `--root`，照抄会当场 argparse 报错。扫 `drafts/**/*.md`（重复定义要靠跨文件比对，故喂 drafts 而非编译后的单文件；merge 衍生物已自动排除）。检测 ① **重复定义** 同一缩写在多个 draft 文件首次定义；② **未定义就用** 裸用 ABBR 且全稿无内联定义、又不在通用白名单（DNA/RNA/PCR 等自动跳过）；③ **Title 出现缩写**。**阻断**：exit 非 0 → 逐条按 `ABBR_CHECK_FAIL` 修 `drafts/section_XX_XX.md`，改完重跑至 exit 0，未过不得进 4d/导出。
   - 以下为脚本未覆盖、须人工补查的部分 (on compiled `exports/Final_Review.md`)：
   - Scan for all uppercase sequences ≥2 chars (candidate abbreviations) and parenthetical definitions like `Full Name (ABBR)` or `中文全称（英文全称, ABBR）`.
   - **Check:** Every abbreviation used bare (without parenthetical definition) in the text must have exactly ONE prior definition. Flag: (a) undefined abbreviations, (b) abbreviations re-defined in multiple sections, (c) abbreviations defined but never used again.
   - Generate `exports/abbreviation_list.md` table (see format in `references/writing_guidelines.md` §4 Abbreviation Management).
   - Title and abstract must not contain unexpanded abbreviations (except universally known: DNA, RNA, PCR, HIV, WHO, FDA).
   - If violations found → list them; AI fixes inline in `exports/Final_Review.md` and propagates back to the source `drafts/section_XX_XX.md`.

   4d. **交叉引用核查（xref，三层 · 报告式软门 · HALT 交用户裁决）** (on compiled `exports/Final_Review.md`)：
   查正文里"见图 5 / 见 3.3 节 / 见表 2 / as discussed in Section 2.1 / as shown in Figure 1"这类**显式指向**的目标存不存在、指得对不对。综述是交叉引用密度最高的稿型（Figure 0 要求每节都引，4b 还会**新写**指向句），而现役对此零覆盖：`validate_citations.py` 管文献 `[N]`、4a 管参考表合并、4b 管"隐式回指缺指针"、R11 只问"引没引框架图"——四者与本步零重叠，都不改判据、不合并。**本步必须排在 4b/4c 之后**（4b 新写的指向句正是最该抓的那批）。
   - **① 合成语料（本步开头无条件覆盖重建，幂等）**：综述的图题注登记在 `figures/figure_index.md`、按设计**不在成稿里**（Phase 4 Step 4 的 `cat` 编译一个字不改，题注不塞进成稿），直接把成稿喂第 1 层 = 每张注册过的图都被判悬空 = **100% 系统性假阳**（再被第 3 层"找不到定义处→confirmed"全部坐实）。故先把注册题注行拼到成稿前面：
     ```bash
     python3 scripts/compile_manuscript.py xref-corpus \
       --figure-index figures/figure_index.md --body exports/Final_Review.md --out tmp/xref_corpus.md
     # 🔴 这里是 --body（成稿），不是 --manuscript：下面第 1 层的 --manuscript 只准指
     #    tmp/xref_corpus.md，两者抄混就是 100% 系统性假阳。
     # 幂等覆盖重建；自动按下面的错误契约处理（figure_index 缺失→退化为纯正文且不报错、
     # 成稿缺失→报错退出）并打印「注册 N 条、进锚 M 条」，N>M 时逐条列出写歪的原行。
     ```
     > **🔴 别用 bash 那套。** POSIX 下的等价形态是
     > `mkdir -p tmp` + `{ grep -E '^##[[:space:]]*Figure[[:space:]]*[0-9]+[[:space:]]*[.:：]' figures/figure_index.md; cat exports/Final_Review.md; } > tmp/xref_corpus.md`（仅供理解取法：行首 `##` + Figure + 编号 + 分隔符的注册标题行）；**PowerShell 下不要跑它**——无 `grep`、不认 `[[:space:]]`、不认 `{ …; }` 分组，且 `>` 写 UTF-16LE。**这不是崩、是静默产假数据**：按下面的错误契约「grep 空匹配 exit 1 属正常、不得中断本步」，grep 不存在时语料会退化成纯正文 → 每张注册图都判悬空 → 正是本步开头写的「100% 系统性假阳」。上面的脚本内置同一形态的判据，跨平台一致。
     > **分隔符类 `[.:：]` 必须含全角冒号**：`## Figure 0：概念框架图` 这种全角注册行若被筛掉就**根本进不了语料**，④ 护栏 3 的回查再怎么写也看不到它（对该形态是死代码），而 Figure 0 是要求每节都引的框架图 —— 一条写歪的注册行会稳定产一条假阳。收进语料后第 1 层**仍认不出**它（英文 `Figure N` 题注正则只认半角，中文 `图 N` 才认全角），`caption_found` 仍为 `false`，由护栏 3 逐条回查兜住。
     > **该修正的已知副作用（无害，但别当成 bug 查）**：全角注册行既然不被题注正则识别，就**不会进 `caption_rows`**，于是会被当成一条标题、多抽出一条 `number=null` 的**假 section 锚**（实测 `SEC [(None,'Figure 0：概念框架图'), ('2.1','Results')]`）。这使「喂题注前后 `sections` 逐条相同」这条不变式**只在全部注册行都用半角分隔符时成立**。假 section 无编号，且第 2 层通读时一眼能看出那是图题注不是小节标题 → **不产假阳**，只是 `outline.json` 的候选清单多一条噪声。
     **只取匹配 `^## Figure N:` 的注册标题行、绝不 `cat` 整份登记表**（整份会多出一条假 section「Figure Index」，且 `- Type:`/`- Section:`/`- Key Message:`/`- Caption:`/`- Node mapping:` 五类登记字段行会被当成正文里的图/节引用）。**表题注就写在正文里、不需要合并，别把表也塞进本流程。** 落点固定 `tmp/xref_corpus.md`、`outline.json` 落项目根，**两者绝不落 `drafts/`**（`drafts/section_*.md` 是 managed_globs，写进去会被 signoff hook 拦下）；本步只读 `exports/`，**不写 `exports/` 下任何文件**（正文修改只发生在 HALT 后的用户裁决环节）。
     - **错误契约**：`figures/figure_index.md` 缺失 → `grep` 空匹配 exit 1 属正常，语料退化为纯正文、**不得因这个非零退出码中断本步**（图类会因锚不可用自动整类 skip）；`exports/Final_Review.md` 缺失 → 报错并停（Step 4 还没跑，属流程错序），不得产出空语料静默通过。登记表有 N 条注册项而只有 M 条进锚 → 在本步 advisory 里列出"注册 N 条、进锚 M 条"，提示用户按 `## Figure N: Title` 模板修正。**计数口径（写死，免各跑各的）**：**N = `figures/figure_index.md` 里所有 `^##` 开头且含 `Figure` + 数字的注册标题行数**（不论用什么分隔符，含 `-`、破折号、无分隔符等一切写法）；**M = 上面 `grep` 实际命中的行数**（即真正进语料的题注行数）。`N > M` 就报，差的那 N−M 条逐条列出原行，让用户看得见哪一行写歪了。
   - **② 第 1 层 确定性结构锚**：
     ```bash
     python3 scripts/structure_outline.py --manuscript tmp/xref_corpus.md --project-root .
     ```
     产 `./outline.json`（`sections`/`figures`/`tables`/`items` 四类真实存在的结构锚 + `summary`）。退出码 **0 = 正常（含空稿；四类为空数组是合法结果，不是失败，本步照常继续）**、**2 = 用法/输入错**（文件不存在、后缀不支持）。该脚本与 `_shared/` byte-identical、5 家共享，**一个字节不许改**（中文 `如图 1 所示` 已被现役正则正常捕获，不需要为它改）。
   - **③ 锚可用性门（第 2 层开跑前的确定性前置判定，主 agent 算好写进 prompt）**：
     ```
     figures_anchor_available  = any(f["caption_found"] for f in outline["figures"])
     tables_anchor_available   = any(t["caption_found"] for t in outline["tables"])
     items_anchor_available    = False   # 🔴 写死的常量：条目类整类不做，与第 1 层抽到什么无关
     # 节类没有对应的布尔量：它的可核性是语义判断，由第 2 层通读全文定（见下条）
     ```
     某类 `*_anchor_available == false` → **该类交叉引用一律强制 skip：不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证**；并在本步末尾产一条 advisory「X 类锚不可用，X 交叉引用未核，需人工过目」（强制 skip 不等于静默放过，用户必须知道哪一类没核）。
     **为什么禁 `uncertain` 而不是"标 uncertain 走人工"**：`uncertain` 与 `missing_target` 共用第 3 层同一条极性模板（"连定义处都找不到 → pass=confirmed"），锚不可用时目标本来就没有定义处 → 每条 uncertain 都会被自动坐实成 confirmed → 假阳 HALT。这与补充材料 S 前缀是同一个形状的坑，处置必须一致。
     - **🔴 节类不设确定性锚门，`outline["sections"]` 降级为"候选清单"**：不作真值、不做门、不据它算任何布尔量。原因是第 1 层根本分不清"章节标题"和"正文编号列举"——实测一份标题全无编号的稿，正文写了 `1. 代谢物通路` / `2. 免疫通路` 就抽成 `SEC [(None,'综述标题'),(None,'背景'),('1','代谢物通路'),('2','免疫通路')]`，任何基于它的门都被翻真。**节类的可核性与逐条判定，全部由 ④ 第 2 层子代理通读全文决定**（它能看到 markdown 结构、代码围栏、上下文）；子代理通读后认为全稿没有编号小节标题 → **节类整类 skip + advisory**。
     - **🔴 判据层级要匹配问题性质（本轮的架构修正，留档）**：**节标题的识别是语义判断，不做机器判据**——历史上用字符规则做过三轮，被**正文编号列表 → 中文顿号 `1、代谢物` → 孤立单条编号 → 多级列举 `2.1/2.2` → 围栏代码块里的 `#` 注释**逐一击穿（形态是开放集合，规则永远追不上），**别再放回来**。图/表能用确定性判据，是因为它们的锚来自**作者亲手声明的实物**（`figures/figure_index.md` 登记表、正文里的 `Table N:` 题注行）→ 回查等于查表；节**没有这种产物**（本技能不要求标题带编号）→ 判定本质是"读懂这份文档的结构"，**必须交给能看懂上下文的那一层**。这与本技能一贯分工一致：脚本抽弱锚（确定性、可回归测试），LLM 做语义判断。
     - **三类的实情**：**图**——题注在成稿外，靠 ① 合并语料才查得了；Polish 模式登记表为空 → 整类 skip。**表**——**一等公民**，题注就写在正文里、直接抽（systematic 档强制四类表：exclusions-with-reasons / RoB / effect / SoF，量大且核心）；作者一张表题注都没写才 skip。**节**——无确定性门，全交第 2 层通读（上两条）。
     - **🔴 条目类恒 skip**：`items_anchor_available = False` 是常量，`outline["items"]` **不读、不喂给第 2 层**。条目编号（`(1)`/`（1）`/`①` 这类）的交叉引用本轮**一律不核**——第 1 层的判据是"编号后是否紧邻实词"，而门要的是"这是定义还是引用"，两者正交（`(1)中枢神经系统`是定义、`(2)中已说明`是引用，同为行首、同一个"中"字），字符级规则区分不了；换判据得改 5 家 byte-identical 的脚本 → 本轮不可通。属**已知限制**，在交付说明里明写告诉用户。
   - **④ 第 2 层 独立检测子代理（fresh context、非作者自评）**：派一个**没参与撰写**的独立子代理（`TaskCreate`/spawn_task），**只喂** `./outline.json`（去掉 `items` 字段）+ `tmp/xref_corpus.md`，**不给撰写过程上下文、不给 `outline.md` 提纲、不给作者意图**（防继承作者确认偏误 → 系统性假阴）。逐条指向型表述判**存在性**（目标编号在不在 → `missing_target`）与**语义对应**（编号在但指错内容 → `semantic_mismatch`），拿不准标 `uncertain` 不硬判。**真值口径分两类，别混**：**图/表**——`outline.json` 的 `figures`/`tables` 是**权威真值**（锚来自作者亲手声明的登记表/题注行），不得凭记忆假设稿里有某张图；**节**——`outline.json` 的 `sections` 只是**候选参考**，以通读全文的结论为准（护栏 1b）。产出 schema `[{"ref_id","citing_location","cited_target","issue_type":"missing_target|semantic_mismatch|uncertain","evidence_quote","outline_says","finding","severity"}]`（`severity` 仅信息字段，**HALT 不按它路由**，所有 confirmed 一律交作者裁决）。三道护栏逐条写进 prompt：
     - **护栏 1 · 锚可用性门（图/表/条目三类）**：③ 算出的布尔量原样写进 prompt，取 `false` 的类别**一条都不许报**（含**绝不标 `uncertain`**）。`items_anchor_available` 恒 `false`，prompt 里同时写死：「条目编号（`(1)`/`（1）`/`①` 这类）的交叉引用本轮一律不核：不产 finding、不标 uncertain、不报 missing_target、不送反向验证。outline.json 的 items 字段不作为真值，忽略它。」
     - **🔴 护栏 1b · 节类判断指引（不是机器判据，逐条写进 prompt）**：
       > 「**通读 `tmp/xref_corpus.md` 全文，自行判断哪些行是真正的小节标题**——你能看到 markdown 结构、代码围栏和上下文，这件事只有你做得了。
       > 下面三类**不是**章节标题，别把它们当小节：**(a) 正文编号列举**（`1、代谢物通路` / `1. 免疫通路` / `2) 临床转化`，中文列举常不加空格）；**(b) 围栏代码块（```…```）内以 `#` 开头的行**——`#` 在 bash/python 里是注释符不是标题，systematic 档登记 PubMed 检索式时很常见；**(c) 行内提及**（句子中间出现的编号）。
       > `outline.json` 的 `sections` **只是候选参考、不是真值**，它由脚本按字符规则抽取，分不清标题和编号列举；**与你的通读结论冲突时，一律以通读为准**。
       > **判不准就交人工**：某条节引用你无法确定目标小节是否存在，**标注出来交用户过目，不要猜**——宁可交人工，不要产假阳。附录编号（`A.1` / `附录 A` / `Appendix B`）同样按通读判断，判不准照样交人工。
       > **🔴 两种情况整类 skip（类级出口，不逐条判）**：**(a)** 通读后认为**全稿根本没有编号小节标题**（作者用的是 `## 背景` 这类无编号标题）；**(b)** 通读后发现**编号体系不完整或不一致**——部分小节有编号、部分没有，或正文引用的编号层级与实际标题体系对不上（4b 会照提纲补写 `Section 2.1` 这类指向，而 drafts 的标题未必对得上，此时"3.4 不存在"看着很像真的，逐条判会自信地判错）。两种情况都：**不产任何 finding、整类 skip**，并产 advisory 告知用户节类未核、需人工过目。」
     - **护栏 2 · 补充材料 S 前缀**：**补充材料引用（`S` 前缀编号，如 `Figure S1`/`Table S3`/`见图 S22`/`Supplementary Fig. 5`）不在 outline 范围内**——正文稿抽不到补充文件的定义，此类**一律强制 skip 丢弃（不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证）**（否则走 `uncertain` 支会连同 `missing_target` 一起被送第 3 层，而补充材料图注天然不在主文 → 第 3 层"连定义处都找不到→pass=confirmed"把整份补充材料 S1–Sn 批量假报为悬空、假阳 HALT）。⚠️ 实测落实说明：`Figure S1`/`Table S3` 因 `S` 挡住数字捕获，第 1 层天然抽不到、无害；但 **`Supplementary Fig. 5` 里的 `Fig. 5` 会被第 1 层正常捕获成 `Figure 5` 假锚**，只能靠本条款 skip 掉。
     - **🔴 护栏 3 · 定义形态逐条回查（三类通用，防第 1 层漏抽造成的假悬空）**：判**任何** `missing_target` 前——**图、表、节三类一视同仁，不分类别**——必须先到 `tmp/xref_corpus.md` 里回查该编号的**定义形态**，**命中任一即不报**（改判无问题）；只有连一处定义形态都找不到，才允许判该编号悬空。**判据要泛化、不是逐例枚举。**
       - **🔴 节类的适用范围更宽、且判法不同：任何节类 finding（含 `semantic_mismatch`，不只 `missing_target`）都要先回查**，但回查方式是**通读，不是套判据**——「判任何节类问题前，先通读一遍全文确认：这个编号有没有在**某个真正的小节标题**里出现过？（`outline.json` 的节锚会被正文编号列举污染，正文写 `1. 代谢物通路` 就会多出一条 `('1','代谢物通路')` 的假节锚，拿它当真值判'编号在、但指的内容对不上'同样会假阳。）确认出现过 → 不报存在性问题；确认没出现过 → 才可报；**确认不了 → 交人工，不要猜**。」
       - **图/表的定义形态（题注行）**：该行**去掉行首的任意组合修饰**后，以 `Figure N` / `Table N` 开头且后接冒号或句点，即算题注。行首修饰含（但不限于）`#` 标题标记、`>` 引用块、`-`/`*`/`+` 列表符、`**`/`*`/`***` 强调标记、任意空白；分隔符含半角 `:` `.` 与全角 `：` `。`；题注可位于图/表的**上方或下方**（题注扫描逐行、位置无关）。已实测第 1 层认不出、必须靠本护栏兜住的形态：**粗体** `**Table N: …**`、**斜体/粗斜体** `*Table N: …*` / `***Table N: …***`（Word 转 md 常见）、**前缀式** `**Table N.** 说明`（编号后跟句点、强调只包编号，投稿模板高频）、**全角冒号** `Table N：…`。**别把回查写成只匹配这四例**——枚举必漏，按上面的泛化判据实现。advisory 里顺带提示用户"表题注别加粗，写成 `Table N: 说明` 或 `#### Table N: 说明`"。
       - **节没有"定义形态"判据，别去补一个**：节标题的识别是语义判断，交第 2 层通读（护栏 1b）。理由见 ③ 的「判据层级要匹配问题性质」。
     - **降级**：派不出真正独立的子代理 → 照盲评降级告警，**不得自问自答冒充**，标注"交叉引用未经独立检测"交用户人肉核。
   - **⑤ 第 3 层 反向验证（gate=`xref-verify`，fail-closed）**：每条 `missing_target`/`semantic_mismatch`/`uncertain` 过 `delegate_review.py`（**不改它一个字节，只调用其打包/校验两步**；`--gate` 是 checklist 内的自由 key，**不查 gate_registry**）。动态合成 `./xref_verify_checklist.json`：`{"skill":"review-writing","gates":{"xref-verify":{"title":"交叉引用一致性·反向验证","items":[{"id":"xref-001","name":"<cited_target 摘要>","check":"<按下方极性模板逐字填>"}]}}}`；item 只放 `cited_target` + `evidence_quote` + `issue_type` + 核验所需原文切片（**绝不放第 2 层的 finding 措辞/理由、也不放 `outline.json`**，防带节奏），默认硬项。**按 issue_type 分流喂料**：`missing_target`/`uncertain` 的 item 待检文件给**合成语料**（含题注的完整语料，让核验人独立回源检索该编号到底有没有定义处）——给成稿的话每条图引用都会因"成稿里本来就没有题注"被错误确认为悬空、这层等于失效；`semantic_mismatch` 的 item **按类别拆开喂**——**图/表**：引用处上下文切片 + `outline.json` 里该编号的标题/caption（那是权威真值，锚来自作者亲手声明的登记表/题注行）；**🔴 节**：只给引用处上下文切片 + **第 2 层通读认定的那条小节标题行原文**（原样引自 `tmp/xref_corpus.md`），**绝不给 `outline["sections"]`**。
     > **为什么节类要拆（与 ④ 的真值口径一致）**：`outline["sections"]` 是被正文编号列举污染的**候选清单**，不是真值——正文写了 `1. 代谢物通路`，喂过去就等于告诉核验人"第 1 节的标题是代谢物通路"这个**脚本编造的事实**，他据此判"内容明显无关 → pass=confirmed"，第 3 层不但没兜住、还成了假阳共犯。护栏 3 的通读只管第 2 层报不报，管不到报出来之后喂什么，所以这里必须单独拆。
     > **措辞留档（勿"顺手还原"，会致测试红）**：上一段刻意写成"只调用其打包/校验两步"，而不是更顺口的"只 pack/verify"——验收考卷把"同一行里既出现该脚本名、又出现 pack 字样"的行**一律当成打包命令行**来断言（要求该行含 `tmp/xref_corpus.md`），散文里同现会误伤致红。契约本身没被削弱（真正的命令行在下面的代码块里），改这段措辞前先看这条。
     **🔴 `check` 逐字用极性模板（禁占位符、禁自由发挥，`{编号}` 处填 `cited_target`）**：
     > `missing_target`/`uncertain`："到给你的原稿全文里，找得到编号「{编号}」的**定义处**吗？定义处专指：图/表的图注行（以『Figure {N}』『图{N}』『Table {N}』『表{N}』开头、后接说明文字的 caption 行），或该编号的小节标题行（如独占一行的『3.2 方法』）；**把它当引用来提及的句子不算定义处**（如『见 Figure 3』『as shown in Figure 3』『详见 3.2 节』这类指向句，即便含该编号也一律不算）。只有连定义处都找不到（该编号只被引用、从未被定义）才判 pass；只要找到定义处就判 fail，并逐字引出该定义/caption 行。"

     > `semantic_mismatch`："正文该引用处的具体断言，与目标「{编号}」的标题/caption 是否明确无关？只有'正文明确断言见 X 讨论了 Y、而 X 根本不涉及 Y'这种明确错位才判 pass；若只是笼统指向或目标标题能合理概括该引用，一律判 fail。"

     ```bash
     python3 scripts/delegate_review.py pack --checklist xref_verify_checklist.json --gate xref-verify --files tmp/xref_corpus.md --workdir .
     python3 scripts/delegate_review.py verify --checklist xref_verify_checklist.json --gate xref-verify --workdir .
     ```
     **🔴 禁传 `--section` / `--root`（跨阶段污染）**：校验全过且提供了 `--section` 时，会往 `<root>/.review_pass/<section>.json` 落"该节盲检通过"标记，而那正是 Phase 3 `prewrite_gate` 的硬校验依据——等于用 Phase 4 的 xref 核查**伪造 Step 10 `manuscript-dod` 的逐节盲检通过**。跑完本步 `.review_pass/` 必须零新增文件。
     独立空白子代理（无撰写上下文、不给 outline、不给第 2 层 reasoning）逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回 `./.review_return_xref-verify.json`。**verdict 映射（恒定）**：`missing_target`/`uncertain` **找到定义处（caption/小节标题行，非引用句自身）→ fail = refuted 剔除**、**连定义处都找不到（悬空引用）→ pass = confirmed 保留**；`semantic_mismatch` **明确无关 → pass = confirmed 保留**、**笼统指向/合理概括 → fail = refuted 剔除**；`problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、**一律不进报告**（宁漏报）。极性写反 = 假批评全放行，务必让核验人区分"定义处 vs 引用处"。⚠️ **退出码陷阱**：任一 item fail 会让校验报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在 xref-verify 里 **fail = 成功剔除假问题 = 正常好结果**。主 agent **必须忽略退出码**，只读返回 JSON 的逐条 verdict + problems，切勿把 exit 1 误读成核查失败。
   - **⑥ HALT 与清理**：命中 confirmed → **HALT 交用户裁决**：打印全部 confirmed（`cited_target` + 引用处原文切片 + evidence），暂停 Phase 4、交用户逐条裁决，就地改 `exports/Final_Review.md` **并反向同步回** `drafts/section_XX_XX.md`（与 4b/4c 同节拍），重跑 4d 至无 confirmed 再进 Step 5。**不 auto-block 硬拦、不静默放过。** 清理两态：**本步无 confirmed、放行下一步时 `rm -f tmp/xref_corpus.md`**（`tmp/` 未进项目 `.gitignore`，不删会被 Step 7 的 git checkpoint 收进去）；**命中 HALT 时保留语料**（用户要照着它核对），处置后重跑本步会重建再删。`outline.json` 保留供诊断。
5. **Final word count:** Verify total ≥ target in `outline.md`.

5b. **结构化"未来方向/开放问题"段（强制，Phase 4 交付前）：**
   若结论节不含独立 Future Directions 段，在此强制补写并插入 `exports/Final_Review.md` + 反向同步到最后一节 `drafts/section_XX_XX.md`。
   规则：≥3 条具体可操作方向，每条含 gap 原因 + 突破路径，不引入正文未建立的概念。
   📖 格式模板详见 `references/writing_guidelines.md` §6。

5c. **元数据块（导出前补全）：** 在 `exports/Final_Review.md` 末尾追加 Manuscript Metadata 块（search cutoff / databases / COI / funding）。
   📖 字段模板详见 `references/writing_guidelines.md` §7。

5d. **导出 docx（最终交付物）：** 所有 md 修复（4b/4c/5/5b/5c）完成后，将 `exports/Final_Review.md` 编译为 `exports/Final_Review.docx`：
   ```bash
   python3 scripts/export_docx.py --md exports/Final_Review.md --out exports/Final_Review.docx
   # 若使用 BibTeX/CSL 渲染参考文献，追加：--bib exports/references.bib [--csl style.csl]
   ```
   样式由 `templates/reference.docx` 锁定（正文 Times New Roman 12pt、标题 TNR 加粗），上下标 `^...^`/`~...~` 经 pandoc `+superscript+subscript` 转为真实上下标。pandoc 缺失时脚本会报清晰错误并退出。

6. **Update state.json (merge, do NOT overwrite):**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 4 --completed true
   ```
   Only `phase` and `completed` are mutated; `completed_sections`, `mode`, `pending_sections`, `zotero_root_key`, `citations_imported` are preserved untouched.
7. **Git Checkpoint** (见复用块, msg: `[review] Phase 4: export finalized`)
8. **Update outline.md** current status section (human-readable summary).

**进入 Phase 5（投稿包）。** Phase 4 导出完成后不直接结束，继续生成投稿材料。

