#!/usr/bin/env python3
"""페이지 스크립트 렌더링 스모크 테스트.

브라우저 없이 HTML에서 id/버튼 구조를 읽어 최소 DOM을 만들고,
assets/*.js 를 quickjs로 실제 실행해 결과 표에 NaN·undefined가 없는지 확인한다.

실행:  python3 tests/test_render.py
"""
import json
import os
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = {
    "salary.html": ["assets/withholding-table.js", "assets/calc-core.js", "assets/ui.js", "assets/salary.js"],
    "crypto.html": ["assets/withholding-table.js", "assets/calc-core.js", "assets/ui.js", "assets/crypto.js"],
    "compound.html": ["assets/withholding-table.js", "assets/calc-core.js", "assets/ui.js", "assets/compound.js"],
}

VOID = {"input", "br", "img", "meta", "link", "hr", "source"}


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = {}
        self.tree = []          # (id, tag) 스택
        self.children = {}      # 부모 id -> [자식 button 정보]
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        eid = a.get("id")
        info = {"tag": tag, "value": a.get("value", ""), "attrs": {}}
        for k, v in a.items():
            if k.startswith("data-") or k in ("type", "aria-pressed", "aria-current"):
                info["attrs"][k] = v if v is not None else ""
        if eid:
            self.elements[eid] = info
            if tag in VOID:
                return
            self.stack.append(eid)
        elif tag == "button" and self.stack:
            parent = self.stack[-1]
            self.children.setdefault(parent, []).append({
                "tag": "button",
                "attrs": {
                    "data-value": a.get("data-value", ""),
                    "aria-pressed": a.get("aria-pressed", "false"),
                },
            })

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack and tag not in ("input",):
            # 가장 가까운 같은 태그의 id 제거
            for i in range(len(self.stack) - 1, -1, -1):
                eid = self.stack[i]
                if self.elements[eid]["tag"] == tag:
                    del self.stack[i:]
                    break


SHIM = r"""
var ELEMENTS = __ELEMENTS__;
var CHILDREN = __CHILDREN__;
var _els = {};

function El(id, info) {
  this.id = id;
  this.tagName = (info.tag || 'div').toUpperCase();
  this.attrs = {};
  for (var k in (info.attrs || {})) this.attrs[k] = info.attrs[k];
  this._value = info.value === undefined ? '' : String(info.value);
  this._text = '';
  this._html = '';
  this.style = {};
  this.hidden = false;
  this._handlers = {};
  this._children = [];
  var self = this;
  this.classList = {
    add: function () {}, remove: function () {},
    contains: function () { return false; }
  };
}
Object.defineProperty(El.prototype, 'value', {
  get: function () { return this._value; },
  set: function (v) { this._value = String(v); }
});
Object.defineProperty(El.prototype, 'textContent', {
  get: function () { return this._text; },
  set: function (v) { this._text = String(v); }
});
Object.defineProperty(El.prototype, 'innerHTML', {
  get: function () { return this._html; },
  set: function (v) { this._html = String(v); }
});
El.prototype.addEventListener = function (type, fn) {
  (this._handlers[type] = this._handlers[type] || []).push(fn);
};
El.prototype.fire = function (type) {
  var hs = this._handlers[type] || [];
  for (var i = 0; i < hs.length; i++) hs[i].call(this, { target: this });
  return hs.length;
};
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); };
El.prototype.getAttribute = function (k) { return this.attrs[k]; };
El.prototype.querySelectorAll = function (sel) {
  if (sel === 'button') return this._children;
  return [];
};
El.prototype.querySelector = function (sel) {
  var m = sel.match(/\[aria-pressed="true"\]/);
  var list = this.querySelectorAll('button');
  for (var i = 0; i < list.length; i++) {
    if (m && list[i].getAttribute('aria-pressed') === 'true') return list[i];
  }
  return null;
};

var document = {
  getElementById: function (id) {
    if (!_els[id]) {
      if (!ELEMENTS[id]) return null;
      var el = new El(id, ELEMENTS[id]);
      var kids = CHILDREN[id] || [];
      for (var i = 0; i < kids.length; i++) el._children.push(new El(id + '_btn' + i, kids[i]));
      _els[id] = el;
    }
    return _els[id];
  }
};
var localStorage = {
  _d: {},
  getItem: function (k) { return this._d[k] === undefined ? null : this._d[k]; },
  setItem: function (k, v) { this._d[k] = String(v); }
};
function __set(id, value) {
  var el = document.getElementById(id);
  if (!el) return 'NO_ELEMENT';
  el.value = value;
  return el.fire('input');
}
function __text(id) { var el = document.getElementById(id); return el ? el.textContent : 'NO_ELEMENT'; }
function __html(id) { var el = document.getElementById(id); return el ? el.innerHTML : 'NO_ELEMENT'; }
function __has(id) { return document.getElementById(id) ? true : false; }
"""

failures = []
checks = 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{name} — {detail}")


def run_page(page, scripts):
    html_path = os.path.join(ROOT, page)
    with open(html_path, encoding="utf-8") as f:
        collector = Collector()
        collector.feed(f.read())

    import quickjs
    ctx = quickjs.Context()
    shim = SHIM.replace("__ELEMENTS__", json.dumps(collector.elements, ensure_ascii=False)) \
               .replace("__CHILDREN__", json.dumps(collector.children, ensure_ascii=False))
    ctx.eval(shim)

    for script in scripts:
        with open(os.path.join(ROOT, script), encoding="utf-8") as f:
            src = f.read()
        try:
            ctx.eval(src)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{page}: {script} 실행 실패 — {exc}")
            return ctx, collector
    return ctx, collector


def text(ctx, eid):
    return ctx.eval(f"__text({json.dumps(eid)})")


def html(ctx, eid):
    return ctx.eval(f"__html({json.dumps(eid)})")


def assert_clean(name, value):
    check(f"{name} 비어 있지 않음", bool(value) and value != "NO_ELEMENT", repr(value)[:80])
    for bad in ("NaN", "undefined", "Infinity"):
        check(f"{name}에 {bad} 없음", bad not in str(value), str(value)[:120])


# ── 연봉 페이지 ─────────────────────────────────────────────────
ctx, col = run_page("salary.html", PAGES["salary.html"])
check("salary: 스크립트 실행", not failures, "; ".join(failures[:2]))
net = text(ctx, "net")
assert_clean("salary net", net)
check("salary net 형식", net.endswith("원") and net.replace(",", "").replace("원", "").isdigit(), net)
# quickjs에는 Intl이 없어 천 단위 구분이 빠질 수 있다 → 쉼표 제거 후 비교
rows = html(ctx, "monthly-rows")
assert_clean("salary 월 공제 표", rows)
check("salary 표 항목 수", rows.count("<tr") >= 8, f"{rows.count('<tr')}행")
for label in ("국민연금", "건강보험", "장기요양보험", "고용보험", "소득세", "지방소득세", "월 실수령액"):
    check(f"salary 표에 {label}", label in rows)
arows = html(ctx, "annual-rows")
assert_clean("salary 연말정산 표", arows)
check("salary 연말정산 정산 행", "정산 예상" in arows, arows[-160:])
crow = html(ctx, "compare-rows")
check("salary 비교표 9행", crow.count("<tr") == 9, f"{crow.count('<tr')}행")
assert_clean("salary 비교표", crow)

# 기본값 확인: 연봉 5,000만·식대 20만·1명 → 3,571,577원
check("salary 기본 결과", net.replace(",", "") == "3571577원", net)

# 입력 변경 → 재계산
ctx.eval('__set("annual", "30000000")')
check("salary 연봉 3,000만 재계산", text(ctx, "net") != net, text(ctx, "net"))
assert_clean("salary 3,000만 결과", text(ctx, "net"))

ctx.eval('__set("annual", "0")')
assert_clean("salary 연봉 0", text(ctx, "net"))
ctx.eval('__set("annual", "200000000")')
assert_clean("salary 연봉 2억", text(ctx, "net"))
ctx.eval('__set("annual", "")')
assert_clean("salary 빈 입력", text(ctx, "net"))
ctx.eval('__set("annual", "50000000"); __set("dependents", "4"); __set("children", "2")')
assert_clean("salary 4인+자녀2", text(ctx, "net"))
check("salary 자녀 공제 표시", "자녀세액공제" in html(ctx, "annual-rows"), "")

# ── 코인 페이지 ─────────────────────────────────────────────────
ctx2, _ = run_page("crypto.html", PAGES["crypto.html"])
avg = text(ctx2, "avg-result")
assert_clean("crypto 평단가", avg)
check("crypto 평단가 기본값", avg.replace(",", "") == "13333333원", avg)
lev = html(ctx2, "lev-rows")
assert_clean("crypto 레버리지 표", lev)
check("crypto 레버리지 8행", lev.count("<tr") == 8, f"{lev.count('<tr')}행")
assert_clean("crypto 청산가", text(ctx2, "liq-result"))
check("crypto 청산가 기본값", text(ctx2, "liq-result").replace(",", "") == "9955000원", text(ctx2, "liq-result"))
assert_clean("crypto 목표 ROI", text(ctx2, "roi-target"))

# 달러 전환: 세그먼트 버튼 클릭 → 단위 표기 변경 + 금액 환산
check("crypto 초기 단위 원", text(ctx2, "cur1") == "원", text(ctx2, "cur1"))
ctx2.eval("""document.getElementById('currency-seg')._children[1].fire('click')""")
check("crypto 단위 달러 전환", text(ctx2, "cur1") == "$", text(ctx2, "cur1"))
check("crypto 달러 결과 표기", text(ctx2, "avg-result").startswith("$"), text(ctx2, "avg-result"))
assert_clean("crypto 통화 전환 후", text(ctx2, "avg-result"))
# 입력값이 모두 달러로 환산되어 평단가도 같은 비율로 바뀐다 (13,333,333 / 1,400 ≈ 9,523.81)
_avg_usd = text(ctx2, "avg-result").replace("$", "").replace(",", "").strip()
try:
    _v = float(_avg_usd)
except ValueError:
    _v = None
check("crypto 환율 환산", _v is not None and abs(_v - 9523.81) < 1, text(ctx2, "avg-result"))
ctx2.eval("""document.getElementById('currency-seg')._children[0].fire('click')""")
check("crypto 원복", text(ctx2, "cur1") == "원", text(ctx2, "cur1"))

ctx2.eval('__set("add-price", "0"); __set("qty", "")')
assert_clean("crypto 0 입력 방어", text(ctx2, "avg-result"))
ctx2.eval('__set("entry", "0")')
assert_clean("crypto 진입가 0", text(ctx2, "liq-result"))
ctx2.eval('__set("entry", "11000000"); __set("leverage", "1")')
assert_clean("crypto 1배", text(ctx2, "liq-result"))

# ── 복리 페이지 ─────────────────────────────────────────────────
ctx3, _ = run_page("compound.html", PAGES["compound.html"])
final = text(ctx3, "final")
assert_clean("compound 최종 자산", final)
check("compound 형식", final.endswith("원"), final)
years = html(ctx3, "year-rows")
assert_clean("compound 연도 표", years)
check("compound 연도 20행", years.count("<tr") == 20, f"{years.count('<tr')}행")
assert_clean("compound 수익률", text(ctx3, "return-rate"))

ctx3.eval('__set("rate", "0")')
assert_clean("compound 수익률 0", text(ctx3, "final"))
ctx3.eval('__set("rate", "-50"); __set("years", "0")')
assert_clean("compound 음수 수익률·0년", text(ctx3, "final"))
ctx3.eval('__set("initial", ""); __set("monthly", "")')
assert_clean("compound 빈 입력", text(ctx3, "final"))

print(f"검사 {checks}건 · 페이지 3개 렌더링")
if failures:
    print(f"실패 {len(failures)}건")
    for f in failures:
        print(" ✗", f)
    sys.exit(1)
print("렌더링 스모크 테스트 통과")
