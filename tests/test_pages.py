#!/usr/bin/env python3
"""정적 사이트 점검: 파일 참조·id 결선·메타데이터·사이트맵 일관성.

브라우저 없이 확인할 수 있는 범위를 검사한다.
실행:  python3 tests/test_pages.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://psh613.github.io/smart-calc-kr/"
PAGES = ["index.html", "salary.html", "crypto.html", "compound.html", "about.html", "privacy.html"]

problems = []
checks = 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        problems.append(f"{name} — {detail}")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


# ── 1. 파일 존재 ────────────────────────────────────────────────
for name in PAGES + ["sitemap.xml", "robots.txt", "favicon.svg", ".nojekyll", "README.md"]:
    check(f"{name} 존재", os.path.exists(os.path.join(ROOT, name)))

for root, _, files in os.walk(os.path.join(ROOT, "assets")):
    for f in files:
        check(f"assets/{f} 비어 있지 않음", os.path.getsize(os.path.join(root, f)) > 0)

# ── 2. HTML 안의 로컬 참조가 실제 파일을 가리키는지 ────────────
for page in PAGES:
    html = read(page)
    for ref in re.findall(r'(?:href|src)="([^"#:]+)"', html):
        if ref.startswith("http") or ref.startswith("//"):
            continue
        target = os.path.join(ROOT, ref)
        check(f"{page} → {ref}", os.path.exists(target), "파일 없음")

# ── 3. JS가 찾는 id가 HTML에 있는지 ─────────────────────────────
id_map = {}
for page in PAGES:
    id_map[page] = set(re.findall(r'\sid="([^"]+)"', read(page)))

SCRIPT_OF = {
    "salary.html": ["assets/salary.js", "assets/ui.js"],
    "crypto.html": ["assets/crypto.js", "assets/ui.js"],
    "compound.html": ["assets/compound.js", "assets/ui.js"],
}
GENERIC_IDS = {"year"}

for page, scripts in SCRIPT_OF.items():
    for script in scripts:
        js = read(script)
        used = set(re.findall(r"""\$\(['"]([\w-]+)['"]\)""", js))
        used |= set(re.findall(r"""getElementById\(['"]([\w-]+)['"]\)""", js))
        for name in sorted(used):
            if name in GENERIC_IDS:
                continue
            check(f"{page}: {script} id#{name}", name in id_map[page],
                  f"{page}에 id={name} 없음")

# onInput 목록의 id도 확인
for page, scripts in SCRIPT_OF.items():
    for script in scripts:
        js = read(script)
        for group in re.findall(r"UI\.onInput\(\[([^\]]+)\]", js):
            for name in re.findall(r"'([\w-]+)'", group):
                check(f"{page}: onInput #{name}", name in id_map[page],
                      f"{page}에 id={name} 없음")

# ── 4. 메타데이터 ───────────────────────────────────────────────
for page in PAGES:
    html = read(page)
    canonical = BASE if page == "index.html" else BASE + page
    check(f"{page} canonical", f'<link rel="canonical" href="{canonical}">' in html, canonical)
    check(f"{page} title", "<title>" in html and "</title>" in html)
    desc = re.search(r'<meta name="description" content="([^"]+)"', html)
    check(f"{page} description", desc is not None and len(desc.group(1)) >= 50,
          "설명이 없거나 짧음")
    check(f"{page} viewport", 'name="viewport"' in html)
    check(f"{page} lang=ko", 'lang="ko"' in html)
    check(f"{page} h1 하나", html.count("<h1") == 1, f"h1 {html.count('<h1')}개")

# ── 5. 사이트맵 ─────────────────────────────────────────────────
sitemap = read("sitemap.xml")
for url in re.findall(r"<loc>([^<]+)</loc>", sitemap):
    path = url.replace(BASE, "")
    if path == "":
        check("사이트맵 루트", True)
    else:
        check(f"사이트맵 {path}", os.path.exists(os.path.join(ROOT, path)), "파일 없음")
check("사이트맵 robots", BASE + "sitemap.xml" in read("robots.txt"))
check("robots Allow", "Allow: /" in read("robots.txt"))

# ── 6. JS 문법 (quickjs로 파싱) ─────────────────────────────────
try:
    import quickjs
    ctx = quickjs.Context()
    for f in ["assets/calc-core.js", "assets/withholding-table.js", "assets/ui.js",
              "assets/salary.js", "assets/crypto.js", "assets/compound.js"]:
        src = read(f)
        try:
            ctx.eval("(function(){" + src.replace("</script>", "") + "\n})")
            # DOM에 접근하는 파일은 실행하지 않고 파싱만 한다
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "SyntaxError" in msg:
                problems.append(f"{f} 문법 오류 — {msg}")
            # ReferenceError 등은 DOM이 없어서 생기는 정상적인 실행 오류
            checks += 1
        else:
            checks += 1
except ImportError:
    print("[!] quickjs 없음 — JS 문법 검사 생략")

# ── 7. 인라인 스크립트 문법 ────────────────────────────────────
for page in PAGES:
    for i, code in enumerate(re.findall(r"<script>(.*?)</script>", read(page), re.S)):
        check(f"{page} 인라인 스크립트 {i}", "document." in code or code.strip() == "")

# ── 결과 ────────────────────────────────────────────────────────
print(f"검사 {checks}건")
if problems:
    print(f"문제 {len(problems)}건")
    for p in problems:
        print(" ✗", p)
    sys.exit(1)
print("정적 점검 통과")
