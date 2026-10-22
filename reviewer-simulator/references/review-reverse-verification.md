> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# 第五步·四分之三 -bis / -ter / -quater：数值 conflict、方法学漏写、异名混用的独立反向验证（与 SKILL.md 正文的交叉引用反向验证同构）

**第五步·四分之三-bis：数值 conflict 的独立反向验证（机器·出报告前·必做）**

第四步半视角⑥每条 `same_measurement==true && conflict==true` 的数值发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`same_measurement==false` 或完全相等的一律不入本层）。**真复用 `delegate_review.py`**（不改它，只 pack/verify），gate=`numeric-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/numeric_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"numeric-verify":{"title":"数值一致性·反向验证","items":[{"id":"num-001","name":"<metric：valA vs valB 摘要>","check":"<下方零容差极性模板逐字填>"}]}}}`。item 只放两处 `raw` 值、两处 location、`metric`、核验所需原文切片，**绝不放视角⑥的 `finding`/reasoning（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **≥3 值的组必须拆成两两配对的多个 item**：视角⑥ `values` 是数组，同指标出现 3+ 次进同一 `conflict` 组，但极性模板只有 A/B 两槽 → 把一个 N≥3 值的组拆成两两配对的多个 item（id 用 `num-<组>-<配对序>` 如 `num-001-a`），每 item 只放 A/B 两值及各自 id/location。**任一配对 item pass → 该组整体保留交人工；全部 fail → 该组剔除。**
   - **🔴【零容差极性模板·必须内联，禁占位符、禁自由发挥】**：`check` 逐字用下面固定模板（`{metric}`/`{valA}`/`{locA}`/`{valB}`/`{locB}` 处填值）——
     > "到给你的原稿全文里独立核实：`{locA}` 处的值『{valA}』与 `{locB}` 处的值『{valB}』，两者据称都是指标『{metric}』的测量结果。请逐字回源确认两点——**(1) 两处是否确指同一指标、同一测量对象、同一分组、同一时间点、同一单位**（即本就应当相等；跨单位如 μM vs nM，请换算到同一单位后再判是否本应相等）？请到原文找出各自邻近的分组/剂量/时间点/亚组/单位线索比对。**(2) 若确为同一测量，两值是否非完全相等**（**零容差：只要不是完全相同的数值即算不等，含末位舍入差异如 58% vs 58.3%**）？**只有『同一测量且非完全相等』才判 pass（矛盾属实，保留交人工裁决）；只要发现两者其实是不同分组/不同时间点/不同亚组/不同单位（正常差异），或换算后完全相等，一律判 fail（非矛盾，剔除）。** evidence 必填：逐字引出 A、B 两处原文句及各自的分组/时间点/单位线索。"

     即 **同一测量且非完全相等 → pass（=confirmed，保留交人工裁决）；不同分组/时间点/亚组/单位（正常差异）或换算后完全相等 → fail（=refuted，剔除）**。⚠️ 极性关键：check 必须显式要核验人**独立回源确认"同一测量"**（比对分组/时间点/单位），不能只问"两个数等不等"——"是否同一测量"判错是数值维度假阳主因。
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源确认 A/B 两处的分组/时间点/单位上下文，非只看结论切片）。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/numeric_verify_checklist.json" --gate numeric-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/numeric_verify_checklist.json" --gate numeric-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（矛盾属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。**零容差下所有 confirmed conflict 一律报出交人工，不做 severity 降级路由。** ⚠️ **退出码陷阱（务必理解）**：本 numeric-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在数值反向验证里 **fail = 成功剔除假矛盾 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，数值一致性标注"未经独立反向验证"。


**第五步·四分之三-ter：方法学漏写的独立反向验证（机器·出报告前·必做）**

第四步半视角⑦每条 `methods_missing==true` 的漏写发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`used_in_study==false` 或 `methods_section_covers==true` 的一律不入本层）。**真复用 base 版 `delegate_review.py`**（reviewer-simulator 是 base 版、零改动复用，不改它，只 pack/verify），gate=`methods-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/methods_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"methods-verify":{"title":"方法学交代完整性·反向验证","items":[{"id":"mth-001","name":"<method：结果用了、方法学疑似未写 摘要>","check":"<下方两条件极性模板逐字填>"}]}}}`。item 只放 `{method}`、结果处用到该方法的**原文命中句**（来自弱锚 `sentence` 或视角⑦ evidence）、核验所需切片，**绝不放视角⑦的 `finding`/reasoning（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **🔴【两条件极性模板·必须内联，禁占位符、禁自由发挥】**：M 维度比 numeric 多一层——**两条件同时成立才 pass**。`check` 逐字用下面固定模板（`{method}` 处填方法名）——
     > "到给你的原稿全文里独立核实两点——**(1) 结果/讨论是否确实报告了本研究做的『{method}』**（有对应实验数据/图/门控/条带等本研究结果，而非仅在背景/引言/讨论里引用他人研究提及该方法，也非讨论/局限里"将来/拟/计划/would/planned to/future work"等表述里打算做但本研究并未做的未来工作/计划实验）？请回源找邻近的数据/图引用与人称/时态/引文线索比对。**(2) 方法学章节是否确实【完全没有】交代『{method}』**——须同时满足三个『没有』才算完全没交代：**(2a)** 既无该方法的小节标题、也无任何描述其如何做的句子；**(2b)** 也没有任何指向补充材料/附录的表述（如『见补充材料』『详见附录』『see Supplementary Methods』『described in the Supplementary/Supporting Information』）；**(2c)** 也没有【引用文献描述该方法】的表述（如『方法参照文献[X]』『按照[X]的方法进行』『as previously described [12]』这类带文献引用标记的方法指向）。只要出现 (2b) 指向补充材料 或 (2c) 引用文献描述该方法，即算已交代、不算漏写。**只有『结果确实用了本研究的该方法』且『方法学确实没写、没指向补充材料、也没引用文献描述该方法』两条同时成立才判 pass（漏写属实，保留交人工裁决）；只要发现方法学其实写了该方法（哪怕只一句）、或主文有指向补充材料的交代、或方法学有引用文献描述该方法（带引文标记）、或结果里的该方法其实是引用他人研究/背景讨论（非本研究做的），一律判 fail（非漏写，剔除）。** evidence 必填：逐字引出结果处用到该方法的句 + 方法学处（有则引出该句证明写了/引出指向补充材料或引用文献的句，无则说明通读方法学未见）。"

     即 **两条件同时成立（本研究确用 AND 方法学确未写、未指向补充材料、未引用文献描述）→ pass（=confirmed，保留交人工裁决）；方法学其实写了 / 主文指向补充材料 / 方法学引用文献描述该方法 / 结果只是引用他人 → fail（=refuted，剔除）**。⚠️ 极性关键（写反＝假批评全放行）：check 必须逼核验人独立确认**两件事**——条件 (1)"本研究做的 vs 引用他人"（M 维度头号假阳源）与条件 (2) 里两类"从宽交代"（(2b) 指向补充材料、(2c) 方法学引用文献描述该方法）；不能只问"方法学有没有直接写该方法"，漏了这些会把引用他人/下沉补充材料/引用文献描述的方法误当漏写放行。**注意区分 (2c) 与条件 (1)**：(2c) 是**方法学**引用文献描述本研究做的方法（已交代、不报）；条件 (1) 排除的是**结果/讨论**里引用他人研究结果的方法（非本研究做的、不该核查）——都靠引文信号但落点不同。
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源判"本研究 vs 引用他人"、判方法学到底写没写），不给视角⑦的判断过程。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/methods_verify_checklist.json" --gate methods-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径 `$WORKROOT/.review_return_methods-verify.json`；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/methods_verify_checklist.json" --gate methods-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（漏写属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，漏写方法学是审稿硬伤，通常 MAJOR/CRITICAL，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。⚠️ **退出码陷阱（务必理解，照 -bis 原样搬）**：本 methods-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在方法学反向验证里 **fail = 成功剔除假漏写 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，方法学一致性标注"未经独立反向验证"。


**第五步·四分之三-quater：异名混用的独立反向验证（机器·出报告前·必做）**

第四步半视角⑧每条 `report==true`（`inconsistent_variant`）的异名混用发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`report==false`——不同实体/合规交替/gene↔protein 约定/普通同义词——的一律不入本层）。**只服务 `inconsistent_variant`**；`duplicate_definition` 是脚本确定性结果、走第五部分七『术语一致性核查产物的报告归位』软报告直报、**不上反向验证**（`undefined_use` 本轮不消费，卡点5 决策）。**真复用 base 版 `delegate_review.py`**（reviewer-simulator 是 base 版、零改动复用，不改它，只 pack/verify），gate=`term-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/term_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"term-verify":{"title":"异名混用·反向验证","items":[{"id":"term-001","name":"<entity：写法A vs 写法B 摘要>","check":"<下方 inconsistent_variant 双条件极性模板逐字填>"}]}}}`。item 只放两处写法 + 各自 location + 核验所需原文切片，**绝不放视角⑧的 `finding`/reasoning、也不放 `same_entity`/`is_compliant_alternation` 判据字段（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **🔴【inconsistent_variant 双条件极性模板·必须内联，禁占位符、禁自由发挥】**：T1 与 methods 同构——**两条件同时成立才 pass**。`check` 逐字用下面固定模板（`{写法A}`/`{写法B}` 处填值）——
     > "到给你的原稿全文里独立核实两点——**(1)** 原文里『{写法A}』与『{写法B}』是否**确指同一个精确定义的实体**（有一处是『全称(缩写)』/『缩写(全称)』式定义、或两者是同一基因/质粒/细胞系的**纯排版级变体**如 p53/P53 大小写、pBV220/pBV-220 连字符、IL-6/IL6 空格）？**(2)** 这个差异是否**超出合规写作**——即**不是**『缩写↔其对应全称』的正常交替、**不是**『中文名↔英文名』的对照并用、**不是**『gene↔protein 命名约定』（如 `TP53` 指基因、`p53` 指蛋白，HGNC 强制的正确区分、本该并存）、**也不是**两个通用同义词（如肿瘤/癌）？**只有『确指同一精确实体』且『差异不属上述任一合规交替』两条同时成立才判 pass（歧义异名属实，保留交人工）；只要发现两者其实是缩写与其全称的正常交替、或中英对照、或 gene↔protein 命名约定、或普通同义词、或根本是两个语义不同的实体（如 p53 vs p63、CD4 vs CD8），一律判 fail（剔除）。** evidence 必填：逐字引出 A、B 两处原文及各自指代。"

     即 **『确指同一精确实体』且『非合规交替』两条同时成立 → pass（=confirmed，保留交人工裁决）；缩写↔全称交替 / 中英对照 / gene↔protein 命名约定 / 普通同义词 / 根本是不同实体（p53 vs p63、CD4 vs CD8）→ fail（=refuted，剔除）**。⚠️ 极性关键（写反＝假批评全放行）：check 必须逼核验人独立回源确认**两件事**——"是否同一精确实体"与"是否合规交替（含 gene↔protein 约定）"，**不能只问"两个写法一样吗"**（判错是 T1 假阳主因，对应 numeric 的"是否同一测量"、methods 的"本研究 vs 引用他人"）。**gene↔protein 命名约定（TP53/p53）是穿透性陷阱——务必在条件 (2) 显式列为合规交替，否则会被当同实体混写 pass 成假批评。**
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源查指代、查是否合规交替），不给视角⑧的判断过程。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/term_verify_checklist.json" --gate term-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径 `$WORKROOT/.review_return_term-verify.json`；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/term_verify_checklist.json" --gate term-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（异名混用属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，异名引歧义视致命度，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。⚠️ **退出码陷阱（务必理解，照 -ter 原样搬）**：本 term-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在异名反向验证里 **fail = 成功剔除假批评 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，术语一致性标注"未经独立反向验证"。


