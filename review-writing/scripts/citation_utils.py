#!/usr/bin/env python3
import re


_CITATION_GROUP_RE = re.compile(
    r"\[((?:\s*\d+(?:\s*[-–]\s*\d+)?\s*)(?:[,;]\s*\d+(?:\s*[-–]\s*\d+)?\s*)*)\]"
)


def _split_items(body):
    return [token.strip() for token in re.split(r"\s*[,;]\s*", body.strip()) if token.strip()]


def _expand_token(token):
    if re.fullmatch(r"\d+", token):
        return [int(token)]
    m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
    if not m:
        return None
    start = int(m.group(1))
    end = int(m.group(2))
    step = 1 if start <= end else -1
    return list(range(start, end + step, step))


def parse_citation_group(group_body):
    numbers = []
    for token in _split_items(group_body):
        expanded = _expand_token(token)
        if expanded is None:
            return None
        numbers.extend(expanded)
    return numbers


def extract_citation_ids(text):
    ids = []
    for match in _CITATION_GROUP_RE.finditer(text):
        parsed = parse_citation_group(match.group(1))
        if parsed is None:
            continue
        ids.extend(parsed)
    return ids
