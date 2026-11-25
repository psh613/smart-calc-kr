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

# ── 7. 연말정산 공통: 과세표준·한계세율 ───────────────────────
ctx = json.loads(q.eval("JSON.stringify(CalcCore.estimateTaxContext(45000000, 1))"))
near("4,500만 과세표준 추정", ctx["taxBase"], 27_127_320, tol=1)
check("4,500만 한계세율 15%", abs(ctx["marginalRate"] - 0.15) < 1e-9, ctx["marginalRate"])
near("4,500만 결정세액 추정", ctx["annualTax"], 2_149_098, tol=1)

for base, want in [(0, 0.06), (14_000_000, 0.06), (14_000_001, 0.15), (50_000_000, 0.15), (50_000_001, 0.24),
                   (88_000_001, 0.35), (150_000_001, 0.38), (500_000_001, 0.42), (2_000_000_000, 0.45)]:
    got = call("marginalRate", base)
    check(f"한계세율 {base:,}", abs(got - want) < 1e-9, f"got={got}, want={want}")

# 소득공제 100만원의 실제 절세액은 한계세율보다 작다(근로소득세액공제 동반 감소)
sv = json.loads(q.eval("JSON.stringify(CalcCore.deductionSaving(CalcCore.estimateTaxContext(30000000, 1), 1000000))"))
check("3,000만 소득공제 절세 < 한계세율", sv["taxSaving"] < 150_000, f"saving={sv['taxSaving']}")
check("3,000만 소득공제 절세 > 0", sv["taxSaving"] > 0, f"saving={sv['taxSaving']}")
check("지방소득세 포함 = ×1.1", abs(sv["totalSaving"] - round(sv["taxSaving"] * 1.1)) <= 1, sv)

# ── 8. 월세 세액공제 vs 현금영수증 소득공제 ───────────────────
r1 = call("computeRentCompare", {"grossSalary": 45_000_000, "annualRent": 8_400_000,
                                  "otherCardSpend": 5_000_000, "dependents": 1})
check("4,500만 공제율 17%", abs(r1["creditRate"] - 0.17) < 1e-9, r1["creditRate"])
near("4,500만 세액공제 절세", r1["creditApplied"], 1_428_000, tol=1)          # 840만 × 17%
near("4,500만 현금영수증 대상", r1["rentExcess"], 2_150_000, tol=1)           # 문턱 1,125만 초과분
near("4,500만 현금영수증 소득공제", r1["rentDeduction"], 645_000, tol=1)        # 215만 × 30%
near("4,500만 현금영수증 절세", r1["cashTaxSaving"], 96_750, tol=1)
check("4,500만 세액공제 우세", r1["winner"] == "credit", r1["winner"])
near("4,500만 차액", r1["gap"], 1_331_250, tol=1)

r2 = call("computeRentCompare", {"grossSalary": 60_000_000, "annualRent": 10_800_000,
                                  "otherCardSpend": 15_000_000, "dependents": 1})
check("6,000만 공제율 15%", abs(r2["creditRate"] - 0.15) < 1e-9, r2["creditRate"])
near("월세 1,080만 → 1,000만 한도", r2["creditBase"], 10_000_000, tol=1)
near("6,000만 세액공제 절세", r2["creditApplied"], 1_500_000, tol=1)
near("6,000만 카드 한도 적용", r2["rentDeduction"], 3_000_000, tol=1)
near("6,000만 현금영수증 절세", r2["cashTaxSaving"], 450_000, tol=1)

r3 = call("computeRentCompare", {"grossSalary": 30_000_000, "annualRent": 7_200_000,
                                  "otherCardSpend": 3_000_000, "dependents": 1})
check("3,000만 결정세액 한도", r3["creditLimitedByTax"], f"credit={r3['creditAmount']}, tax={r3['annualTax']}")
near("3,000만 한도 = 결정세액", r3["creditApplied"], r3["annualTax"], tol=1)

r4 = call("computeRentCompare", {"grossSalary": 90_000_000, "annualRent": 9_600_000,
                                  "otherCardSpend": 40_000_000, "dependents": 1})
check("8,000만 초과 세액공제 없음", r4["creditRate"] == 0 and r4["creditApplied"] == 0, json.dumps(r4)[:120])

r5 = call("computeRentCompare", {"grossSalary": 45_000_000, "annualRent": 8_400_000,
                                  "otherCardSpend": 5_000_000, "dependents": 1, "meetsRequirement": False})
check("요건 미충족 → 세액공제 0", r5["creditApplied"] == 0, r5["creditApplied"])
check("요건 미충족 → 현금영수증 우세", r5["winner"] == "cash", r5["winner"])

# 문턱 미달이면 현금영수증 소득공제는 0원
r6 = call("computeRentCompare", {"grossSalary": 45_000_000, "annualRent": 8_400_000,
                                  "otherCardSpend": 0, "dependents": 1})
check("문턱 미달 소득공제 0", r6["rentDeduction"] == 0 and r6["thresholdShort"] > 0, json.dumps(r6)[:120])

# 그 외 사용액이 카드 한도를 다 채우면 월세 몫은 0
r7 = call("computeRentCompare", {"grossSalary": 60_000_000, "annualRent": 6_000_000,
                                  "otherCardSpend": 60_000_000, "dependents": 1})
check("카드 한도 소진 시 월세 몫 0", r7["rentDeduction"] == 0, r7["rentDeduction"])

# 경계값·방어
for bad in [{"grossSalary": 0, "annualRent": 0, "otherCardSpend": 0},
            {"grossSalary": -1000, "annualRent": -1000, "otherCardSpend": -1000},
            {"grossSalary": 45_000_000, "annualRent": 120_000_000, "otherCardSpend": 0}]:
    out = call("computeRentCompare", bad)
    for key, v in out.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            check(f"월세비교 {bad['grossSalary']}/{bad['annualRent']} {key} 유한", math.isfinite(v), f"{key}={v}")

# 월세액이 늘수록 두 쪽 절세액 모두 줄지 않는다
prev_c = prev_k = -1
for rent in range(0, 14_000_001, 1_000_000):
    s = call("computeRentCompare", {"grossSalary": 45_000_000, "annualRent": rent,
                                    "otherCardSpend": 5_000_000, "dependents": 1})
    check(f"월세 {rent:,} 세액공제 단조", s["creditApplied"] >= prev_c, f"{s['creditApplied']} < {prev_c}")
    check(f"월세 {rent:,} 현금영수증 단조", s["cashTaxSaving"] >= prev_k, f"{s['cashTaxSaving']} < {prev_k}")
    prev_c, prev_k = s["creditApplied"], s["cashTaxSaving"]

# ── 9. 신용카드 등 사용금액 소득공제 ───────────────────────────
for gross, kids, want in [(50_000_000, 0, 3_000_000), (50_000_000, 1, 3_500_000), (50_000_000, 2, 4_000_000),
                          (70_000_000, 0, 3_000_000), (70_000_001, 0, 2_500_000),
                          (80_000_000, 1, 2_750_000), (80_000_000, 2, 3_000_000)]:
    got = json.loads(q.eval(f"JSON.stringify(CalcCore.cardDeductionLimit({gross}, {kids}))"))
    check(f"카드 한도 {gross:,}·자녀{kids}", got == want, f"got={got}, want={want}")

c1 = call("computeCardDeduction", {"grossSalary": 50_000_000, "creditCard": 15_000_000,
                                    "debitCash": 5_000_000, "dependents": 1, "children": 0})
near("카드 25% 문턱", c1["threshold"], 12_500_000, tol=1)
near("카드 신용카드 초과분", c1["excessCredit"], 2_500_000, tol=1)
near("카드 체크·현금 전액", c1["excessDebit"], 5_000_000, tol=1)
near("카드 산출 공제액", c1["rawDeduction"], 1_875_000, tol=1)      # 250만×15% + 500만×30%
near("카드 적용 공제액", c1["deduction"], 1_875_000, tol=1)
near("카드 절세액", c1["taxSaving"], 281_250, tol=1)              # 15% 구간
near("카드 지방세 포함 절세", c1["totalSaving"], 309_375, tol=1)
near("카드 남은 한도", c1["limitLeft"], 1_125_000, tol=1)

# 신용카드가 문턱을 먼저 채운다
c2 = call("computeCardDeduction", {"grossSalary": 50_000_000, "creditCard": 20_000_000,
                                    "debitCash": 0, "dependents": 1})
near("신용 2,000만 전액 신용공제", c2["excessCredit"], 7_500_000, tol=1)
near("신용 2,000만 공제액", c2["rawDeduction"], 1_125_000, tol=1)

# 체크카드가 문턱을 채우는 경우
c3 = call("computeCardDeduction", {"grossSalary": 40_000_000, "creditCard": 8_000_000,
                                    "debitCash": 4_000_000, "dependents": 3, "children": 2})
check("문턱 일부만 넘음", c3["excessCredit"] == 0 and abs(c3["excessDebit"] - 2_000_000) < 1, json.dumps(c3)[:120])
near("자녀2 한도 400만", c3["limit"], 4_000_000, tol=1)
near("자녀2 공제액", c3["deduction"], 600_000, tol=1)
near("자녀2 절세액", c3["taxSaving"], 90_000, tol=1)

# 한도 초과
c4 = call("computeCardDeduction", {"grossSalary": 50_000_000, "creditCard": 40_000_000,
                                    "debitCash": 0, "dependents": 1})
check("한도 적용", c4["limitApplied"] and c4["deduction"] == 3_000_000, json.dumps(c4)[:160])
near("잘린 공제액", c4["lostDeduction"], c4["rawDeduction"] - 3_000_000, tol=1)

# 문턱 미달
c5 = call("computeCardDeduction", {"grossSalary": 35_000_000, "creditCard": 6_000_000,
                                    "debitCash": 1_000_000, "dependents": 1})
check("문턱 미달 0원", c5["deduction"] == 0 and c5["taxSaving"] == 0, json.dumps(c5)[:120])
check("문턱 부족액", abs(c5["thresholdShort"] - 1_750_000) < 1, c5["thresholdShort"])

# 체크카드 사용액을 늘리면 공제액이 줄지 않는다(같은 총액)
prev = -1
for debit in range(0, 21_000_001, 2_000_000):
    s = call("computeCardDeduction", {"grossSalary": 50_000_000, "creditCard": 20_000_000 - debit,
                                      "debitCash": debit, "dependents": 1})
    check(f"체크 {debit:,} 공제액 단조", s["deduction"] >= prev, f"{s['deduction']} < {prev}")
    prev = s["deduction"]

# 방어
for bad in [{"grossSalary": 0, "creditCard": 0, "debitCash": 0},
            {"grossSalary": -1, "creditCard": -1, "debitCash": -1},
            {"grossSalary": 100_000_000, "creditCard": 900_000_000, "debitCash": 0, "children": 99}]:
    out = call("computeCardDeduction", bad)
    for key, v in out.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            check(f"카드 {bad['grossSalary']} {key} 유한", math.isfinite(v), f"{key}={v}")

# ── 10. 업비트 스테이킹 ──────────────────────────────────────

def st(payload):
    return call("computeStaking", payload)

# 코스모스 100만 원 · 12개월 · 해제 22일 기본 예시
a1 = st({"assetKey": "ATOM", "amount": 1_000_000, "months": 12})
near("ATOM 수량 = 금액÷현재가", a1["qty"], 1_000_000 / 1693, tol=1e-9)
near("ATOM 연 보상률", a1["aprPct"], 19.29, tol=1e-9)
check("ATOM 해제 대기 22일", a1["unstakeDays"] == 22, a1["unstakeDays"])
near("ATOM 실수령 보상량", a1["netRewardQty"], 125.6348, tol=0.001)
near("ATOM 실수령 보상액", a1["netRewardKrw"], 212_700, tol=1)
near("ATOM 수수료 = 실수령÷9", a1["feeQty"], a1["netRewardQty"] / 9, tol=1e-9)
near("ATOM 수수료 전 = 실수령÷0.9", a1["grossRewardQty"], a1["netRewardQty"] / 0.9, tol=1e-9)
near("ATOM 기간 보상률", a1["periodReturn"], 0.2127, tol=0.0002)
near("ATOM 손익분기 하락률", a1["breakEvenDrop"], 0.17539, tol=0.0002)
near("ATOM 손익분기 시세", a1["breakEvenPrice"], 1396.06, tol=0.1)
near("ATOM 대기 하루당", a1["dailyAllowance"], 0.17539 / 22, tol=1e-6)
near("ATOM 1년 실효 보상률", a1["effAnnual"], 0.1929 * (365 - 1 / 24 - 22) / 365, tol=1e-9)
near("ATOM 하락 10% 순손익", st({"assetKey": "ATOM", "amount": 1_000_000, "months": 12,
                                  "expectedDropPct": 10})["netPnlKrw"], 91_429.74, tol=1)
check("ATOM 최소 수량 충족", a1["minQtyOk"] is True, a1["minQtyOk"])
near("ATOM 최소 수량 금액", a1["minAmount"], 0.05 * 1693, tol=1e-6)

# 복리 반영: 단리보다 많고, 지급 주기가 짧을수록 복리 효과가 크다
check("ATOM 복리 > 단리", a1["netRewardQty"] > a1["simpleRewardQty"],
      f"{a1['netRewardQty']} vs {a1['simpleRewardQty']}")

# 손익분기 정의: (1+기간보상률)(1-h)=1
def breakeven_ok(r):
    return abs((1 + r["periodReturn"]) * (1 - r["breakEvenDrop"]) - 1) < 1e-12

# 손익분기만큼 빠지면 순손익 0
a2 = st({"assetKey": "ATOM", "amount": 1_000_000, "months": 12,
         "expectedDropPct": a1["breakEvenDrop"] * 100})
near("손익분기 시 순손익 0", a2["netPnlKrw"], 0, tol=1e-6)
check("손익분기 시 판정 본전", abs(a2["netPnlRate"]) < 1e-9, a2["netPnlRate"])

# 6종 전부: 보상률별 손인분기 관계, 유한값, 최소 수량 정보
for asset in json.loads(q.eval("JSON.stringify(CalcCore.STAKING2026.assets)")):
    key = asset["key"]
    for months in (1, 6, 12, 24, 60):
        r = st({"assetKey": key, "amount": 3_000_000, "months": months})
        check(f"{key} {months}개월 손익분기 정의", breakeven_ok(r), f"{r['periodReturn']}/{r['breakEvenDrop']}")
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                check(f"{key} {months}개월 {k} 유한", math.isfinite(v), f"{k}={v}")
        check(f"{key} {months}개월 대기 하루당 = 손익분기÷대기",
              abs(r["dailyAllowance"] * r["unstakeDays"] - r["breakEvenDrop"]) < 1e-12,
              f"{r['dailyAllowance']}×{r['unstakeDays']}")
        check(f"{key} 실효 보상률 ≤ 연 보상률", r["effAnnual"] <= r["apr"] + 1e-12, r["effAnnual"])

# 업비트 공개 값 대조 (2026-11-25 14:03 신청 화면·시세 API)
EXPECT = {
    "ETH": (2.76, 10, 0.02, 2_257_000),
    "SOL": (4.67, 3, 0.01, 93_450),
    "ATOM": (19.29, 22, 0.05, 1_693),
    "ADA": (1.92, 2 / 24, None, 194),
    "POL": (6.55, 3, 2.7, 102),
    "CRO": (3.52, 29, 10, 53.3),
}
for key, (apr, days, minq, price) in EXPECT.items():
    a = json.loads(q.eval(f"JSON.stringify(CalcCore.stakingAsset('{key}'))"))
    near(f"{key} 공개 보상률", a["apr"] * 100, apr, tol=1e-9)
    near(f"{key} 공개 대기일", a["unstakeDays"], days, tol=1e-9)
    near(f"{key} 공개 현재가", a["price"], price, tol=1e-9)
    check(f"{key} 최소 수량", a["minQty"] == minq, f"{a['minQty']} vs {minq}")

# 에이다는 첫 보상이 약 20일 뒤 → 보상일수에서 빠진다
ada = st({"assetKey": "ADA", "amount": 1_000_000, "months": 12})
check("ADA 보상일수 345일", ada["rewardDays"] == 345, ada["rewardDays"])
check("ADA 첫 보상 지연 반영", ada["periodReturn"] < ada["apr"] - 0.0005,
      f"{ada['periodReturn']} vs {ada['apr']}")
check("ADA 345일치 보상률", abs(ada["periodReturn"] - (math.pow(1 + 0.0192 * 5 / 365, 69) - 1)) < 1e-9,
      ada["periodReturn"])
check("ADA 최소 수량은 미확인(null)", ada["minQty"] is None and ada["minQtyOk"] is None, ada["minQtyOk"])

# 이더리움 300만 원 · 하락 5% → 보상보다 시세 손실이 크다
eth = st({"assetKey": "ETH", "amount": 3_000_000, "months": 12, "expectedDropPct": 5})
near("ETH 실수령 보상액", eth["netRewardKrw"], 83_950, tol=1)
near("ETH 손익분기 하락률", eth["breakEvenDrop"], 0.02722, tol=0.00002)
near("ETH 5% 하락 순손익", eth["netPnlKrw"], -70_247.49, tol=1)
check("ETH 5% 하락 판정", eth["netPnlKrw"] < 0, eth["netPnlKrw"])
near("ETH 시세 손실 = 금액×하락률", eth["priceLossKrw"], 150_000, tol=1e-6)

# 최소 수량 미만
a3 = st({"assetKey": "ETH", "amount": 10_000})
check("ETH 최소 수량 미만", a3["minQtyOk"] is False, a3["minQtyOk"])

# 단조성: 보상률·기간이 늘면 보상과 손익분기 하락률이 줄지 않는다
prev_q = prev_h = -1
for apr in (0, 2, 5, 10, 19.29, 50):
    r = st({"assetKey": "ATOM", "amount": 1_000_000, "aprPct": apr})
    check(f"보상률 {apr}% 보상 단조", r["netRewardQty"] >= prev_q - 1e-9, f"{r['netRewardQty']} < {prev_q}")
    check(f"보상률 {apr}% 손익분기 단조", r["breakEvenDrop"] >= prev_h - 1e-12, f"{r['breakEvenDrop']} < {prev_h}")
    prev_q, prev_h = r["netRewardQty"], r["breakEvenDrop"]
prev_q = -1
for m in (1, 3, 6, 12, 24, 60):
    r = st({"assetKey": "SOL", "amount": 2_000_000, "months": m})
    check(f"{m}개월 보상 단조", r["netRewardQty"] >= prev_q - 1e-12, f"{r['netRewardQty']} < {prev_q}")
    prev_q = r["netRewardQty"]

# 경계값·방어 (0·음수·범위 초과·빈 값)
for bad in [{"assetKey": "ATOM", "amount": 0},
            {"assetKey": "ATOM", "amount": -1_000_000},
            {"assetKey": "ATOM", "amount": 1_000_000, "price": 0},
            {"assetKey": "ATOM", "amount": 1_000_000, "aprPct": 0},
            {"assetKey": "ATOM", "amount": 1_000_000, "aprPct": 1000},
            {"assetKey": "ATOM", "amount": 1_000_000, "months": 0},
            {"assetKey": "ATOM", "amount": 1_000_000, "months": 999},
            {"assetKey": "ATOM", "amount": 1_000_000, "unstakeDays": -5},
            {"assetKey": "ATOM", "amount": 1_000_000, "unstakeDays": 0},
            {"assetKey": "ATOM", "amount": 1_000_000, "expectedDropPct": 100},
            {"assetKey": "XXXX", "amount": 1_000_000},
            {"assetKey": "ATOM", "amount": 1_000_000, "aprPct": ""},
            {"assetKey": "ATOM", "amount": 1_000_000, "months": ""}]:
    out = st(bad)
    for key, v in out.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            check(f"스테이킹 {json.dumps(bad, ensure_ascii=False)} {key} 유한", math.isfinite(v), f"{key}={v}")
    check(f"스테이킹 {json.dumps(bad, ensure_ascii=False)} 하락률 범위", 0 <= out["breakEvenDrop"] <= 1,
          out["breakEvenDrop"])

# 알 수 없는 코인은 기본 종목(ETH)으로, 빈 보상률은 종목 기본값으로
check("미지 종목 → ETH", st({"assetKey": "XXXX", "amount": 1_000_000})["assetKey"] == "ETH", "")
near("빈 보상률 → 기본값", st({"assetKey": "ATOM", "amount": 1_000_000, "aprPct": ""})["aprPct"], 19.29, tol=1e-9)
check("대기 0일이면 하루당 0", st({"assetKey": "ATOM", "amount": 1_000_000, "unstakeDays": 0})["dailyAllowance"] == 0, "")

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
