#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

VALID = {'拒稿', '大修', '小修', '接收'}
PH_RE = re.compile(r"{{\s*[A-Z0-9_]+\s*}}")
VERDICT_CLASS_MAP = {
    '拒稿': 'verdict-reject',
    '大修': 'verdict-major',
    '小修': 'verdict-minor',
    '接收': 'verdict-accept',
}

def text_of_id(html: str, element_id: str):
    m = re.search(rf'id="{re.escape(element_id)}"[^>]*>(.*?)</', html, flags=re.S)
    if not m:
        return None
    text = re.sub(r'<[^>]+>', '', m.group(1))
    return text.strip()

def classes_of_id(html: str, element_id: str):
    """Return list of CSS classes on the element with given id."""
    m = re.search(rf'id="{re.escape(element_id)}"[^>]*class="([^"]*)"', html)
    if not m:
        m = re.search(rf'class="([^"]*)"[^>]*id="{re.escape(element_id)}"', html)
    if not m:
        return []
    return m.group(1).split()

def normalize(v: str | None):
    if v is None:
        return None
    return v.replace('{', '').replace('}', '').strip()

def main():
    ap = argparse.ArgumentParser(description='Validate reviewer simulator HTML output gates.')
    ap.add_argument('html_path', help='Path to generated report html')
    args = ap.parse_args()

    p = Path(args.html_path)
    html = p.read_text(encoding='utf-8')

    errors = []

    # 剥离 <script>/<style> 区后再扫占位符，对齐模板 JS unresolvedPlaceholders() 的行为：
    # 模板自带的预览检测脚本硬编码了 {{...}} 字面量，不剥离会误报为未替换占位符。
    html_no_code = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
    placeholders = sorted(set(PH_RE.findall(html_no_code)))
    if placeholders:
        errors.append('Unreplaced placeholders found: ' + ', '.join(placeholders[:12]) + (' ...' if len(placeholders) > 12 else ''))

    header_verdict = normalize(text_of_id(html, 'decisionVerdict'))
    final_recommendation = normalize(text_of_id(html, 'finalRecommendationText'))

    if header_verdict not in VALID:
        errors.append(f'Invalid or missing decisionVerdict: {header_verdict!r}')
    if final_recommendation not in VALID:
        errors.append(f'Invalid or missing finalRecommendationText: {final_recommendation!r}')
    if header_verdict in VALID and final_recommendation in VALID and header_verdict != final_recommendation:
        errors.append(f'Verdict mismatch: header={header_verdict}, section10={final_recommendation}')

    # A2: VERDICT_CLASS must match verdict one-to-one
    verdict_classes = classes_of_id(html, 'decisionVerdict')
    if header_verdict in VALID:
        expected_class = VERDICT_CLASS_MAP[header_verdict]
        found_verdict_classes = [c for c in verdict_classes if c.startswith('verdict-')]
        if not found_verdict_classes:
            errors.append(f'VERDICT_CLASS missing: expected "{expected_class}" on #decisionVerdict, found no verdict-* class')
        elif expected_class not in found_verdict_classes:
            errors.append(
                f'VERDICT_CLASS mismatch: verdict="{header_verdict}" expects class "{expected_class}", '
                f'but found {found_verdict_classes}'
            )

    if errors:
        print('VALIDATION_FAILED')
        for e in errors:
            print('- ' + e)
        raise SystemExit(1)

    expected_class = VERDICT_CLASS_MAP.get(header_verdict, '?')
    print('VALIDATION_OK')
    print(f'- verdict: {header_verdict}')
    print(f'- verdict_class: {expected_class}')
    print(f'- final_recommendation: {final_recommendation}')

if __name__ == '__main__':
    main()
