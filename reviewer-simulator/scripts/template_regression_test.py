#!/usr/bin/env python3
"""模板回归测试（开发者维护工具，非审稿运行时流程）。

维护规范：
- 每次修改 assets/report_template.html 后，必须执行回归测试：
    python scripts/template_regression_test.py
- 若为有意的样式/结构变更，先用 --bless 更新基线：
    python scripts/template_regression_test.py --bless
  随后再执行不带参数的回归校验确认通过。
"""
import argparse
import json
import re
from pathlib import Path

VALIDS = [
    ('拒稿', 'verdict-reject'),
    ('大修', 'verdict-major'),
    ('小修', 'verdict-minor'),
    ('接收', 'verdict-accept'),
]

PH_RE = re.compile(r"{{\s*([A-Z0-9_]+)\s*}}")

def fill_all(template: str, verdict: str, cls: str):
    placeholders = sorted(set(PH_RE.findall(template)))
    defaults = {k: '占位内容' for k in placeholders}
    defaults.update({
        'MANUSCRIPT_TITLE': '回归测试稿件',
        'TARGET_JOURNAL': 'Test Journal',
        'MANUSCRIPT_ID': 'RS-TEST-001',
        'DATE': '2026-03-08',
        'VERDICT_TEXT': verdict,
        'VERDICT_CLASS': cls,
        'FINAL_RECOMMENDATION': verdict,
        'SYNOPSIS': '测试摘要',
        'TECHNICAL_AUDIT_HTML': '<div class="tech-report-item"><span class="tech-report-label">核查</span>通过</div>',
        'TARGET_FIT_HTML': '<p>契合度测试</p>',
        'DEEP_ANALYSIS_HTML': '<div class="analysis-point"><strong>1.核心论点</strong><p>测试。</p></div>',
        'OVERALL_ASSESSMENT': '总体评估测试。',
        'STRENGTHS_HTML': '<li>优势测试</li>',
        'CRITICAL_ISSUES_HTML': '<li><div class="critique-title">【问题1】测试问题</div><span class="evidence-anchor">证据锚点: 第七部分</span></li>',
        'OTHER_SUGGESTIONS_HTML': '<li><div class="critique-title">【建议1】测试建议</div><span class="evidence-anchor">证据锚点: 建议1</span></li>',
        'FORENSIC_ANALYSIS_HTML': '<p>深度解剖测试</p>',
        'RECOMMENDATION_RATIONALE': '判定依据测试',
        'REFERENCES_HTML': '<li>Reference</li>',
        'REBUTTAL_DRAFT_HTML': '<p>回复草案测试</p>',
        'GENERATION_TIMESTAMP': '2026-03-08T10:00:00+08:00',
    })

    result = template
    for k, v in defaults.items():
        result = result.replace('{{' + k + '}}', v)
    return result


def snapshot(html: str):
    decision = re.search(r'<div class="decision-section"[\s\S]*?</div>', html)
    footer = re.search(r'<footer>[\s\S]*?</footer>', html)
    return {
        'decision': decision.group(0) if decision else '',
        'footer': footer.group(0) if footer else '',
        'has_placeholder': bool(PH_RE.search(html)),
        'has_ip_notice': 'Reviewer Simulator' in html,
        'has_print_css': '@media print' in html,
    }


def main():
    ap = argparse.ArgumentParser(description='Regression test for reviewer template verdict states.')
    ap.add_argument('--template', default=str(Path(__file__).resolve().parents[1] / 'assets' / 'report_template.html'))
    ap.add_argument('--baseline', default=str(Path(__file__).resolve().parent / 'regression_baseline.json'))
    ap.add_argument('--bless', action='store_true')
    args = ap.parse_args()

    template = Path(args.template).read_text(encoding='utf-8')
    snaps = {}
    for verdict, cls in VALIDS:
        html = fill_all(template, verdict, cls)
        snap = snapshot(html)
        assert not snap['has_placeholder'], f'placeholder remained for {verdict}'
        assert snap['has_ip_notice'], 'ip notice missing'
        assert snap['has_print_css'], 'print css missing'
        assert verdict in snap['decision'], f'decision block missing verdict {verdict}'
        snaps[verdict] = snap

    b = Path(args.baseline)
    if args.bless:
        b.write_text(json.dumps(snaps, ensure_ascii=False, indent=2), encoding='utf-8')
        print('BASELINE_UPDATED', b)
        return

    if not b.exists():
        raise SystemExit('Baseline not found. Run with --bless once.')

    expected = json.loads(b.read_text(encoding='utf-8'))
    if snaps != expected:
        print('REGRESSION_FAILED')
        print('Run with --bless to update baseline if change is intentional.')
        raise SystemExit(1)

    print('REGRESSION_OK')

if __name__ == '__main__':
    main()
