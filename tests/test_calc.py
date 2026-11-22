#!/usr/bin/env python3
"""smart-calc-kr 계산 로직 검증.

1) assets/calc-core.js + assets/withholding-table.js 를 실제로 실행(quickjs)해
   - 근로소득 간이세액표 공개 값(국세청·언론·법제처 별표 샘플)과 일치하는지
   - 공개된 실수령액 예시(4대보험 388,690원 사례)와 맞는지
   대조한다.
2) 경계값(0, 음수, 상한 초과, 0으로 나누기, 표 범위 밖)에서 NaN/Infinity가
   나오지 않는지 확인한다.

실행:  python3 tests/test_calc.py
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "assets", "calc-core.js")
TABLE = os.path.join(ROOT, "assets", "withholding-table.js")

failures = []
checks = 0


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{name} — {detail}")


def near(name, actual, expected, tol=20):
    check(name, actual is not None and abs(actual - expected) <= tol,
          f"actual={actual}, expected={expected}±{tol}")


try:
    import quickjs
except ImportError:
    print("quickjs가 필요합니다: python3 -m pip install quickjs")
    sys.exit(1)

q = quickjs.Context()
for path in (TABLE, CORE):          # 계산 코어보다 표를 먼저 읽는다
    with open(path, encoding="utf-8") as f:
        q.eval(f.read())


def call(fn, payload):
    return json.loads(q.eval(f"JSON.stringify(CalcCore.{fn}({json.dumps(payload)}))"))


def call2(fn, a, b):
    return json.loads(q.eval(f"JSON.stringify(CalcCore.{fn}({json.dumps(a)}, {json.dumps(b)}))"))


def wt(monthly, dependents, children=0):
    """간이세액표 조회 (세액, 공제대상가족 수, 자녀 수)"""
    return json.loads(q.eval(
        f"JSON.stringify(CalcCore.withholdingTax({json.dumps(monthly)}, {json.dumps(dependents)}, {json.dumps(children)}))"))

# ── 1. 간이세액표 공개 값 대조 ─────────────────────────────────
# 국세청 별표2(2026.2.27 개정) 기준으로 여러 곳에서 동일하게 확인된 값.
PUBLISHED = {
    2_000_000: [19_520, 14_750, 6_600, 3_220],
    2_500_000: [35_600, 28_600, 16_530, 13_150],
    3_000_000: [74_350, 56_850, 31_940, 26_690],
    3_500_000: [127_220, 102_220, 62_460, 49_340],
    4_000_000: [195_960, 167_950, 109_590, 91_670],
    5_000_000: [335_470, 306_710, 237_850, 219_100],
    6_000_000: [505_900, 466_060, 395_720, 376_970],
    7_000_000: [732_700, 684_290, 557_350, 527_350],
}
for wage, expected in PUBLISHED.items():
    for i, want in enumerate(expected):
        got = wt(wage, i + 1)
        check(f"간이세액표 {wage:,}원·{i+1}명", got == want, f"got={got}, want={want}")

# 구간 경계: 3,000천원 미만은 10천원, 이상은 20천원 간격
check("5천원 구간 같은 값", wt(1_499_999, 1) == wt(1_495_000, 1),
      f"{wt(1_499_999, 1)} vs {wt(1_495_000, 1)}")
check("1만원 구간 같은 값", wt(2_999_999, 1) == wt(2_990_000, 1),
      f"{wt(2_999_999, 1)} vs {wt(2_990_000, 1)}")
check("구간 3,000,000 시작",
      wt(3_000_000, 1) == 74_350)

# 770천원 미만은 세액 0
check("770천원 미만 0원", wt(760_000, 1) == 0)
check("770천원 이상 유한값", wt(775_000, 1) >= 0)

# 1,000만원 초과 구간(별표2 계산식) 연속성
t10 = wt(10_000_000, 1)
t14 = wt(14_000_000, 1)
near("1,000만원 세액", t10, 1_507_400, tol=10)
near("1,400만원 세액 연속", t14, t10 + 1_397_000, tol=20)
gap = wt(10_000_001, 1) - t10
check("1,000만원 초과 시 별표2 계산식(+25,000원)", 24_900 <= gap <= 25_100, f"gap={gap}")
prev = None
for m in [10_000_000, 12_000_000, 14_000_000, 14_000_001, 20_000_000, 28_000_000,
          28_000_001, 30_000_000, 30_000_001, 45_000_000, 45_000_001, 87_000_000, 100_000_000]:
    v = wt(m, 1)
    check(f"{m:,}원 세액 유한", math.isfinite(v) and v > 0, f"v={v}")
    if prev is not None:
        check(f"{m:,}원 구간 증가", v >= prev, f"{v} < {prev}")
    prev = v

# 자녀 공제(비고 3): 1명 20,830 / 2명 45,830 / 3명 78,890
base1 = wt(5_000_000, 4, 0)
for kids, ded in [(1, 20_830), (2, 45_830), (3, 45_830 + 33_330)]:
    got = wt(5_000_000, 4, kids)
    check(f"자녀 {kids}명 공제", got == base1 - ded, f"got={got}, want={base1-ded}")

# 낮은 임금에서 자녀 공제가 세액을 음수로 만들지 않는다
low = wt(800_000, 1, 3)
check("자녀 공제 후 0 이상", low == 0, f"got={low}")

# 가족 수가 늘면 세액이 줄어든다
prev = None
for d in range(1, 12):
    v = wt(5_000_000, d)
    if prev is not None:
        check(f"가족 {d}명 세액 감소", v <= prev, f"{v} > {prev}")
    prev = v

# ── 2. 연봉 실수령액 (공개 사례 대조) ───────────────────────────
# 월 400만원·1명: 4대보험 388,690 · 소득세 195,960 · 지방소득세 19,590 → 3,395,760
a1 = call("computeSalary", {"annualSalary": 48_000_000, "meal": 0, "dependents": 1, "children": 0})
near("월 400만 4대보험 합계", a1["insuranceTotal"], 388_690, tol=1)
near("월 400만 소득세", a1["incomeTax"], 195_960)
near("월 400만 실수령", a1["net"], 3_395_760, tol=2)

# 월 400만원·4명(자녀 2명): 소득세 91,670 − 45,830 = 45,840 → 3,560,890
a2 = call("computeSalary", {"annualSalary": 48_000_000, "meal": 0, "dependents": 4, "children": 2})
near("월 400만·4명 소득세", a2["incomeTax"], 45_840)
near("월 400만·4명 실수령", a2["net"], 3_560_890, tol=2)

# 연봉 5,000만·식대 20만·1명 (구간 3,960~3,980천원: 190,620원)
r = call("computeSalary", {"annualSalary": 50_000_000, "meal": 200_000, "dependents": 1, "children": 0})
near("연봉 5,000만 국민연금", r["pension"], 188_380)
near("연봉 5,000만 건강보험", r["health"], 142_600)
near("연봉 5,000만 장기요양", r["ltc"], 18_730)
near("연봉 5,000만 고용보험", r["employ"], 35_700)
near("연봉 5,000만 소득세", r["incomeTax"], 190_620)
near("연봉 5,000만 지방소득세", r["localTax"], 19_060)
near("연봉 5,000만 실수령", r["net"], 3_571_577, tol=2)

# 국민연금 상·하한
r100 = call("computeSalary", {"annualSalary": 100_000_000, "meal": 200_000, "dependents": 2})
check("국민연금 상한 적용", r100["pensionBase"] == 6_590_000, f"base={r100['pensionBase']}")
near("국민연금 상한 금액", r100["pension"], 313_020, tol=10)
rlow = call("computeSalary", {"annualSalary": 3_000_000, "meal": 0, "dependents": 1})
check("국민연금 하한 적용", rlow["pensionBase"] == 410_000, f"base={rlow['pensionBase']}")
near("국민연금 하한 금액", rlow["pension"], 19_470, tol=10)

# 식대 20만원 상한
rmeal = call("computeSalary", {"annualSalary": 50_000_000, "meal": 400_000, "dependents": 1})
check("식대 20만원 상한", rmeal["mealAllowance"] == 200_000, f"meal={rmeal['mealAllowance']}")

# 비과세 식대가 늘면 실수령이 는다
r0 = call("computeSalary", {"annualSalary": 50_000_000, "meal": 0, "dependents": 1})
check("식대 비과세 효과", r["net"] > r0["net"], f"{r['net']} vs {r0['net']}")

# 부양가족·자녀가 늘수록 실수령이 준다
prev = None
for dep in range(1, 7):
    cur = call("computeSalary", {"annualSalary": 60_000_000, "meal": 200_000, "dependents": dep})["net"]
    check(f"부양가족 {dep}명 단조성", prev is None or cur >= prev, f"{cur} < {prev}")
    prev = cur
prev = None
for kids in range(0, 4):
    cur = call("computeSalary", {"annualSalary": 60_000_000, "meal": 200_000, "dependents": 4, "children": kids})["net"]
    check(f"자녀 {kids}명 단조성", prev is None or cur >= prev, f"{cur} < {prev}")
    prev = cur

# 연봉 구간 전체 유한값·단조성
salaries = [0, 1_000_000, 5_000_000, 9_240_000, 12_000_000, 20_000_000, 24_000_000,
            30_000_000, 40_000_000, 50_000_000, 60_000_000, 80_000_000, 100_000_000,
            150_000_000, 200_000_000, 500_000_000]
prev_net = -1
for s in salaries:
    res = call("computeSalary", {"annualSalary": s, "meal": 200_000, "dependents": 1, "children": 1})
    for key, val in res.items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            check(f"연봉 {s:,} {key} 유한", math.isfinite(val), f"value={val}")
    check(f"연봉 {s:,} 실수령 0 이상", res["net"] >= 0, f"net={res['net']}")
    check(f"연봉 {s:,} 공제 <= 급여", res["totalDeduction"] <= res["monthlyGross"] + 1,
          f"deduct={res['totalDeduction']}, gross={res['monthlyGross']}")
    check(f"연봉 {s:,} 실수령 단조", res["net"] >= prev_net, f"{res['net']} < {prev_net}")
    prev_net = res["net"]

# 정산(원천징수 − 결정세액)이 유한하고 급여 범위 안에 있다
for s in (24_000_000, 40_000_000, 60_000_000, 100_000_000):
    res = call("computeSalary", {"annualSalary": s, "meal": 200_000, "dependents": 2})
    check(f"연봉 {s:,} 정산 유한", math.isfinite(res["settlement"]), f"{res['settlement']}")
    check(f"연봉 {s:,} 정산 크기", abs(res["settlement"]) < res["taxableAnnual"] * 0.1,
          f"settle={res['settlement']}")

# 음수·문자 입력 방어
bad = call("computeSalary", {"annualSalary": -5_000_000, "meal": -100, "dependents": 0})
check("음수 입력 방어", bad["net"] == 0 and bad["dependents"] == 1, json.dumps(bad)[:120])

# ── 3. 코인 물타기 ─────────────────────────────────────────────
avg = call("computeAverage", {"qty": 1, "avgPrice": 15_000_000, "addQty": 0.5,
                              "addPrice": 10_000_000, "currentPrice": 11_000_000})
near("물타기 평단가", avg["newAvgPrice"], 13_333_333.33, tol=1)
check("물타기 총 수량", abs(avg["totalQty"] - 1.5) < 1e-9, f"qty={avg['totalQty']}")
near("물타기 총 투자금", avg["totalCost"], 20_000_000)
near("물타기 평단 하락률", avg["avgChange"], -0.1111111, tol=1e-6)
near("손익분기 상승률", avg["breakEvenFromCurrent"], 0.2121212, tol=1e-5)
near("평가손익", avg["unrealizedPnl"], -3_500_000)

avg0 = call("computeAverage", {"qty": 0, "avgPrice": 0, "addQty": 0, "addPrice": 0, "currentPrice": 0})
check("물타기 0 나누기 방어", avg0["newAvgPrice"] == 0 and math.isfinite(avg0["totalCost"]), json.dumps(avg0))

avg_no_add = call("computeAverage", {"qty": 2, "avgPrice": 10_000_000, "addQty": 0,
                                     "addPrice": 0, "currentPrice": 0})
near("추가 매수 없으면 평단 유지", avg_no_add["newAvgPrice"], 10_000_000)

# ── 4. 선물 청산가 ─────────────────────────────────────────────
fut = call("computeFutures", {"side": "long", "entry": 11_000_000, "leverage": 10,
                              "maintenanceMarginPct": 0.5, "margin": 1_000_000,
                              "targetPrice": 12_000_000})
near("롱 10배 청산가", fut["liquidationPrice"], 9_955_000, tol=1)
near("롱 청산 거리", fut["liquidationDistance"], -0.095, tol=1e-6)
near("명목 포지션", fut["positionSize"], 10_000_000)
near("목표가 ROI", fut["roiAtTarget"], 0.9090909090909083, tol=1e-6)
near("목표가 손익", fut["pnlAtTarget"], 909_090.9, tol=1)

short = call("computeFutures", {"side": "short", "entry": 11_000_000, "leverage": 10,
                                "maintenanceMarginPct": 0.5, "margin": 1_000_000,
                                "targetPrice": 10_000_000})
near("숏 10배 청산가", short["liquidationPrice"], 12_045_000, tol=1)
near("숏 청산 거리", short["liquidationDistance"], 0.095, tol=1e-6)
check("숏 목표가 수익", short["roiAtTarget"] > 0, f"roi={short['roiAtTarget']}")

one = call("computeFutures", {"side": "long", "entry": 100_000, "leverage": 1,
                              "maintenanceMarginPct": 0.5, "margin": 0, "targetPrice": 0})
near("1배 롱 청산가(유지증거금만)", one["liquidationPrice"], 500, tol=1)

for lev in [1, 2, 5, 10, 20, 50, 100, 200]:
    f = call("computeFutures", {"side": "long", "entry": 1000, "leverage": lev,
                                "maintenanceMarginPct": 0.5, "margin": 0, "targetPrice": 0})
    check(f"{lev}배 청산가 유한·양수", f["liquidationPrice"] > 0 and math.isfinite(f["liquidationPrice"]),
          f"liq={f['liquidationPrice']}")
    check(f"{lev}배 손실 폭 0~100%", -1 < f["liquidationDistance"] <= 0, f"dist={f['liquidationDistance']}")

# ── 5. 적립식·복리 ─────────────────────────────────────────────
c = call("computeCompound", {"initial": 0, "monthly": 500_000, "annualRatePct": 7,
                             "years": 10, "contributionTiming": "start"})
near("복리 10년 최종", c["finalBalance"], 86_009_441, tol=5_000)
near("복리 총 납입", c["totalPrincipal"], 60_000_000)
check("복리 연도별 행 수", len(c["rows"]) == 10, f"rows={len(c['rows'])}")
near("복리 10년차 원금", c["rows"][-1]["principal"], 60_000_000)

flat = call("computeCompound", {"initial": 0, "monthly": 500_000, "annualRatePct": 0,
                                "years": 10, "contributionTiming": "start"})
near("수익률 0% 최종", flat["finalBalance"], 60_000_000, tol=1)
near("수익률 0% 수익", flat["totalProfit"], 0, tol=1)

neg = call("computeCompound", {"initial": 10_000_000, "monthly": 0, "annualRatePct": -10,
                               "years": 10, "contributionTiming": "start"})
near("연 -10% 10년", neg["finalBalance"], 10_000_000 * 0.9 ** 10, tol=1)

init = call("computeCompound", {"initial": 10_000_000, "monthly": 0, "annualRatePct": 5,
                                "years": 1, "contributionTiming": "end"})
near("초기자금 1년 5%", init["finalBalance"], 10_500_000, tol=2)

edge = call("computeCompound", {"initial": 0, "monthly": 0, "annualRatePct": 5,
                                "years": 0, "contributionTiming": "start"})
check("기간 0년 → 1년 보정", edge["years"] == 1 and edge["finalBalance"] == 0, json.dumps(edge))

big = call("computeCompound", {"initial": 100_000_000, "monthly": -500_000,
                               "annualRatePct": 300, "years": 100})
check("범위 초과 입력 보정", big["years"] == 60 and big["monthly"] == 0
      and math.isfinite(big["finalBalance"]), json.dumps(big)[:160])

# ── 6. 세금 내부 함수 ──────────────────────────────────────────
check("근로소득공제 3,380만", abs(call("wageDeduction", 33_800_000) - 10_320_000) < 1,
      f"{call('wageDeduction', 33800000)}")
near("근로소득공제 한도", call("wageDeduction", 500_000_000), 20_000_000, tol=1)
near("기본세율 4,000만", call("bracketTax", 40_000_000), 4_740_000, tol=1)
near("산출세액 8,800만 경계", call("bracketTax", 88_000_000), 88_000_000 * 0.24 - 5_760_000, tol=1)
near("근로소득세액공제 한도(총급여 5,000만)",
     call2("laborTaxCredit", 3_000_000, 50_000_000),
     max(660_000, 740_000 - (50_000_000 - 33_000_000) * 0.008), tol=1)
for kids, want in [(0, 0), (1, 250_000), (2, 550_000), (3, 950_000), (4, 1_350_000)]:
    check(f"자녀세액공제 {kids}명", call("childTaxCredit", kids) == want,
          f"got={call('childTaxCredit', kids)}, want={want}")

# ── 결과 출력 ──────────────────────────────────────────────────
print(f"quickjs 엔진 · 검사 {checks}건")
print("\n연봉별 월 실수령 (식대 20만 · 부양가족 1명 · 자녀 0명)")
print(f"{'연봉':>12} {'월 실수령':>12} {'월 공제':>10} {'공제율':>7} {'연말정산 정산':>14}")
for s in [24_000_000, 30_000_000, 40_000_000, 50_000_000, 60_000_000, 70_000_000, 80_000_000, 100_000_000]:
    res = call("computeSalary", {"annualSalary": s, "meal": 200_000, "dependents": 1, "children": 0})
    print(f"{s:>12,} {res['net']:>12,} {res['totalDeduction']:>10,} "
          f"{res['deductionRate']*100:>6.1f}% {res['settlement']:>14,}")

if failures:
    print(f"\n실패 {len(failures)}건")
    for f in failures[:40]:
        print(" ✗", f)
    sys.exit(1)
print("\n모든 검사 통과")
