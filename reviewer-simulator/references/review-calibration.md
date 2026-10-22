> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# 第六部分·三：可选模式 calibration 校准（细则）

当用户明确要求"校准/calibration/测审稿可信度"时，进入校准模式（细则见 `references/review_rubric.md` 第九节）：
- 用户提供**金标准集**（已知真实 accept/reject 的论文集）→ 用 `python "$SKILL_DIR/scripts/calibration.py" --input <金标准JSON路径>` 计算 FNR/FPR/balanced accuracy 并解读（`$SKILL_DIR` 见第三部分 CITATION_GUARD_RULE）。
- **无金标准集 → 优雅退出**：输出脚本返回的 `notice`（提示需提供已知结果的论文集），不报错、不进入常规审稿、不编造数据。
- 校准模式不产出 HTML 审稿报告，仅输出量化指标，且结果不可外推为对任意稿件的普适准确率。

