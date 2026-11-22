#!/usr/bin/env python3
"""소득세법 시행령 [별표 2] 근로소득 간이세액표 PDF를 assets/withholding-table.js 로 변환한다.

사용:
    curl -sL -o table.pdf "https://www.law.go.kr/LSW/flDownload.do?flSeq=164357181"
    python3 tools/build_withholding_table.py table.pdf

표 구조: 월급여 770천원~10,000천원, 646개 구간 × 공제대상가족 1~11명.
1,500천원 미만은 5천원, 3,000천원 미만은 10천원, 그 이상은 20천원 간격이다.
"""
import json
import re
import sys

import pdfplumber

NUM = re.compile(r"[\d,]+$")


def parse(path):
    rows, at_10000 = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    if not raw or len(raw) < 13:
                        continue
                    low, high = (raw[0] or "").strip(), (raw[1] or "").strip()
                    if low == "10,000천원":
                        at_10000 = [to_int(c) for c in raw[2:13]]
                        continue
                    if not NUM.match(low) or not NUM.match(high):
                        continue
                    rows.append([to_int(c) for c in raw[2:13]])
    return rows, at_10000


def to_int(cell):
    cell = (cell or "").strip()
    if cell in ("-", ""):
        return 0
    if not NUM.match(cell):
        raise ValueError(f"예상하지 못한 값: {cell!r}")
    return int(cell.replace(",", ""))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "table.pdf"
    rows, at_10000 = parse(path)
    if len(rows) != 646:
        raise SystemExit(f"행 수가 646이 아닙니다: {len(rows)}")
    if not at_10000:
        raise SystemExit("10,000천원 행을 찾지 못했습니다")

    body = {
        "source": "소득세법 시행령 [별표 2] 근로소득 간이세액표 (2026. 2. 27. 개정, 2026년 3월 1일 이후 원천징수분)",
        "startMonthly": 770000,
        "smallStep": 5000,
        "smallCount": 146,
        "midStep": 10000,
        "midCount": 150,
        "bigStep": 20000,
        "at10000": at_10000,
        "rows": rows,
    }

    out = (
        "/*! 2026년 근로소득 간이세액표 — 소득세법 시행령 [별표 2](2026.2.27 개정)\n"
        " *  월급여(비과세 제외) 770,000원 ~ 10,000,000원 구간의 월 소득세.\n"
        " *  rows[i] = 공제대상가족 1~11명일 때의 세액(원). 자동 생성 파일이므로 직접 수정하지 마세요.\n"
        " *  생성: tools/build_withholding_table.py\n"
        " */\n"
        "(function (root) {\n"
        "  root.WITHHOLDING = " + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + ";\n"
        "})(typeof window !== 'undefined' ? window : this);\n"
    )
    with open("assets/withholding-table.js", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"저장 완료: assets/withholding-table.js ({len(out):,} bytes, {len(rows)}행)")


if __name__ == "__main__":
    main()
