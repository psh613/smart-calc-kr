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
    "rent-tax.html": ["assets/calc-core.js", "assets/ui.js", "assets/rent.js"],
    "card-tax.html": ["assets/calc-core.js", "assets/ui.js", "assets/card.js"],
    "staking.html": ["assets/calc-core.js", "assets/ui.js", "assets/staking.js"],
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

# ── 월세 공제 비교 페이지 ────────────────────────────────────────
ctx4, _ = run_page("rent-tax.html", PAGES["rent-tax.html"])
winner = text(ctx4, "winner")
assert_clean("rent 유리한 쪽", winner)
check("rent 기본 승자 = 세액공제", winner == "월세 세액공제", winner)
check("rent 세액공제 금액", text(ctx4, "credit-saving") == "1,428,000원", text(ctx4, "credit-saving"))
check("rent 현금영수증 금액", text(ctx4, "cash-saving") == "96,750원", text(ctx4, "cash-saving"))
check("rent 차액", text(ctx4, "gap") == "+1,331,250원", text(ctx4, "gap"))
check("rent 한계세율", text(ctx4, "marginal") == "15%", text(ctx4, "marginal"))
assert_clean("rent 승자 설명", text(ctx4, "winner-sub"))
detail = html(ctx4, "detail-rows")
assert_clean("rent 상세 표", detail)
check("rent 상세 표 6행", detail.count("<tr") == 6, f"{detail.count('<tr')}행")
for label in ("공제 방식", "공제율", "공제 대상 월세", "산출 공제액", "세금 감소", "결론"):
    check(f"rent 상세에 {label}", label in detail)
rent_rows = html(ctx4, "rent-rows")
assert_clean("rent 월세액별 표", rent_rows)
check("rent 월세액별 10행", rent_rows.count("<tr") == 10, f"{rent_rows.count('<tr')}행")
for note in ("credit-note", "stat-threshold-short", "stat-limit", "stat-break-even", "rent-caption"):
    assert_clean(f"rent {note}", text(ctx4, note))

# 요건 미충족으로 바꾸면 현금영수증 쪽이 이긴다
ctx4.eval("""document.getElementById('require-seg')._children[1].fire('click')""")
check("rent 요건 미충족 승자", text(ctx4, "winner") == "현금영수증 소득공제", text(ctx4, "winner"))
assert_clean("rent 요건 미충족 결과", text(ctx4, "winner-sub"))
ctx4.eval("""document.getElementById('require-seg')._children[0].fire('click')""")
check("rent 요건 복귀", text(ctx4, "winner") == "월세 세액공제", text(ctx4, "winner"))

# 총급여 8,000만 초과 → 둘 다 이득 없음
ctx4.eval('__set("gross-salary", "90000000"); __set("other-card", "40000000")')
assert_clean("rent 8,000만 초과", text(ctx4, "winner"))
check("rent 8,000만 초과 안내", "8,000만" in text(ctx4, "credit-note"), text(ctx4, "credit-note"))

# 월세를 늘리면 세액공제 금액이 늘어난다
ctx4.eval('__set("gross-salary", "45000000"); __set("other-card", "5000000"); __set("annual-rent", "3000000")')
low_credit = text(ctx4, "credit-saving")
ctx4.eval('__set("annual-rent", "8400000")')
check("rent 월세 증가 → 공제 증가", text(ctx4, "credit-saving") != low_credit, text(ctx4, "credit-saving"))
ctx4.eval('__set("annual-rent", "")')
assert_clean("rent 월세 빈 입력", text(ctx4, "winner"))
ctx4.eval('__set("annual-rent", "12000000"); __set("dependents", "")')
assert_clean("rent 부양가족 빈값", text(ctx4, "winner"))

# ── 카드 소득공제 페이지 ────────────────────────────────────────
ctx5, _ = run_page("card-tax.html", PAGES["card-tax.html"])
ded = text(ctx5, "deduction")
assert_clean("card 공제액", ded)
check("card 공제액 기본값", ded == "1,875,000원", ded)
check("card 절세액", text(ctx5, "tax-saving") == "281,250원", text(ctx5, "tax-saving"))
check("card 지방세 포함", text(ctx5, "total-saving") == "309,375원", text(ctx5, "total-saving"))
check("card 문턱", text(ctx5, "threshold") == "12,500,000원", text(ctx5, "threshold"))
check("card 남은 한도", text(ctx5, "limit-left") == "1,125,000원", text(ctx5, "limit-left"))
cdetail = html(ctx5, "detail-rows")
assert_clean("card 상세 표", cdetail)
check("card 상세 표 12행", cdetail.count("<tr") == 12, f"{cdetail.count('<tr')}행")
for label in ("최저사용금액", "신용카드 15%", "체크·현금영수증 30%", "공제 한도", "적용 소득공제액", "예상 절세액"):
    check(f"card 상세에 {label}", label in cdetail)
mix = html(ctx5, "mix-rows")
assert_clean("card 비율별 표", mix)
check("card 비율별 5행", mix.count("<tr") == 5, f"{mix.count('<tr')}행")
assert_clean("card 상태 안내", text(ctx5, "status"))
assert_clean("card 절세율 설명", text(ctx5, "saving-rate-note"))

# 결제수단을 체크카드로 몰면 공제액이 바뀐다
ctx5.eval('__set("credit-card", "0"); __set("debit-cash", "20000000")')
assert_clean("card 체크 100%", text(ctx5, "deduction"))
check("card 체크 100% 변화", text(ctx5, "deduction") != "1,875,000원", text(ctx5, "deduction"))

# 자녀 가산 한도
ctx5.eval('__set("credit-card", "40000000"); __set("debit-cash", "0"); __set("children", "2")')
assert_clean("card 한도 초과", text(ctx5, "deduction"))
check("card 자녀2 한도 표기", "자녀 2명 이상" in html(ctx5, "detail-rows"), "")

# 문턱 미달·빈 입력 방어
ctx5.eval('__set("credit-card", "6000000"); __set("debit-cash", "1000000"); __set("gross-salary", "35000000"); __set("children", "0")')
check("card 문턱 미달 0원", text(ctx5, "deduction") == "0원", text(ctx5, "deduction"))
check("card 문턱 안내", "모자랍니다" in text(ctx5, "status"), text(ctx5, "status"))
ctx5.eval('__set("credit-card", ""); __set("debit-cash", ""); __set("gross-salary", "")')
assert_clean("card 빈 입력", text(ctx5, "deduction"))
ctx5.eval('__set("gross-salary", "60000000"); __set("credit-card", "20000000"); __set("debit-cash", "5000000"); __set("dependents", ""); __set("children", "")')
assert_clean("card 부양가족 빈값", text(ctx5, "deduction"))

# ── 스테이킹 페이지 ─────────────────────────────────────────────
ctx6, _ = run_page("staking.html", PAGES["staking.html"])
be = html(ctx6, "breakeven")
assert_clean("staking 손익분기", be)
check("staking 기본 손익분기 17.5%", "17.5<small>%</small>" == be, be)
check("staking 실수령 보상", text(ctx6, "reward") == "212,700원", text(ctx6, "reward"))
check("staking 수수료", text(ctx6, "fee") == "23,633원", text(ctx6, "fee"))
check("staking 실효 보상률", text(ctx6, "eff-annual") == "18.13%", text(ctx6, "eff-annual"))
check("staking 순손익", text(ctx6, "net-pnl") == "+91,430원", text(ctx6, "net-pnl"))
assert_clean("staking 결과 설명", text(ctx6, "breakeven-sub"))
for note in ("min-note", "fee-note", "break-even-note", "eff-note",
             "asset-caption", "period-caption", "drop-caption"):
    assert_clean(f"staking {note}", text(ctx6, note))
check("staking 최소 수량 안내", "0.05 ATOM" in text(ctx6, "min-note"), text(ctx6, "min-note"))
detail = html(ctx6, "detail-rows")
assert_clean("staking 상세 표", detail)
check("staking 상세 9행", detail.count("<tr") == 9, f"{detail.count('<tr')}행")
for label in ("스테이킹 수량", "연 추정 보상률", "검증 수수료 10%", "실수령 보상",
              "손익분기 시세 하락률"):
    check(f"staking 상세에 {label}", label in detail)
assets = html(ctx6, "asset-rows")
assert_clean("staking 6종 비교", assets)
check("staking 6종 6행", assets.count("<tr") == 6, f"{assets.count('<tr')}행")
for ticker in ("ETH", "SOL", "ATOM", "ADA", "POL", "CRO"):
    check(f"staking 6종에 {ticker}", ticker in assets)
periods = html(ctx6, "period-rows")
assert_clean("staking 기간별", periods)
check("staking 기간 5행", periods.count("<tr") == 5, f"{periods.count('<tr')}행")
drops = html(ctx6, "drop-rows")
assert_clean("staking 하락 시나리오", drops)
check("staking 하락 6행", drops.count("<tr") == 6, f"{drops.count('<tr')}행")
check("staking 하락 판정", "보상이 방어" in drops and "원금 손실" in drops, drops[:120])

# 코인을 바꾸면 시세·보상률·대기일이 그 종목 값으로 바뀐다
ctx6.eval("""document.getElementById('coin-chips')._children[0].fire('click')""")
check("staking ETH 전환 현재가", text(ctx6, "reward") == "27,983원", text(ctx6, "reward"))
check("staking ETH 손익분기", html(ctx6, "breakeven") == "2.7<small>%</small>", html(ctx6, "breakeven"))
check("staking ETH 최소 수량", "0.02 ETH" in text(ctx6, "min-note"), text(ctx6, "min-note"))
ctx6.eval("""document.getElementById('coin-chips')._children[3].fire('click')""")
assert_clean("staking ADA 전환", text(ctx6, "reward"))
check("staking ADA 최소 수량 미확인", "확인하지 못했습니다" in text(ctx6, "min-note"), text(ctx6, "min-note"))

# 입력 변경·경계값
ctx6.eval("""document.getElementById('coin-chips')._children[2].fire('click')""")
ctx6.eval('__set("drop", "30")')
check("staking 30% 하락 시 손실", text(ctx6, "net-pnl").startswith("−"), text(ctx6, "net-pnl"))
ctx6.eval('__set("apr", "0")')
assert_clean("staking 보상률 0", text(ctx6, "reward"))
check("staking 보상률 0 손익분기", html(ctx6, "breakeven") == "0.0<small>%</small>", html(ctx6, "breakeven"))
ctx6.eval('__set("apr", "19.29"); __set("price", "0")')
assert_clean("staking 현재가 0", text(ctx6, "reward"))
check("staking 현재가 0 안내", "현재가를 1원 이상" in text(ctx6, "min-note"), text(ctx6, "min-note"))
ctx6.eval('__set("price", "1693"); __set("amount", "")')
assert_clean("staking 금액 빈칸", text(ctx6, "reward"))
ctx6.eval('__set("amount", "50"); __set("months", "")')
assert_clean("staking 최소 수량 미만", text(ctx6, "reward"))
check("staking 최소 미만 안내", "보다 적습니다" in text(ctx6, "min-note"), text(ctx6, "min-note"))
ctx6.eval('__set("months", "60"); __set("unstake-days", "0")')
assert_clean("staking 60개월·대기 0", text(ctx6, "reward"))
assert_clean("staking 기간별 재계산", html(ctx6, "period-rows"))

print(f"검사 {checks}건 · 페이지 {len(PAGES)}개 렌더링")
if failures:
    print(f"실패 {len(failures)}건")
    for f in failures:
        print(" ✗", f)
    sys.exit(1)
print("렌더링 스모크 테스트 통과")
