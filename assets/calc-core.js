/*!
 * smart-calc-kr — 계산 로직 (2026년 기준)
 * 화면과 분리된 순수 함수 모음. 브라우저에서는 window.CalcCore, 테스트에서는 전역 CalcCore.
 */
(function (root) {
  'use strict';

  /* ── 2026년 제도 상수 ────────────────────────────────────────────
   * 국민연금 9.5%(근로자 4.75%) · 건강보험 7.19%(근로자 3.595%)
   * 장기요양 = 건강보험료 × 13.14%(0.9448÷7.19) · 고용보험 실업급여 1.8%(근로자 0.9%)
   * 기준소득월액 2026.7~2027.6: 41만~659만 원
   */
  var R2026 = {
    pensionRate: 0.0475,
    pensionBaseMin: 410000,
    pensionBaseMax: 6590000,
    healthTotalRate: 0.0719,
    healthEmployeeRate: 0.03595,
    healthTotalMin: 20160,
    healthTotalMax: 9183480,
    ltcRate: 0.1314,
    employRate: 0.009,
    mealFreeMax: 200000,
    basicPerPerson: 1500000,
    standardCredit: 130000,
    wageDeductionCap: 20000000,
    localTaxRate: 0.1,
    childCredit1: 250000,
    childCredit2: 550000,
    childCreditExtra: 400000
  };

  function num(v) {
    if (v === null || v === undefined || v === '') return 0;
    var n = Number(v);
    return isFinite(n) ? n : 0;
  }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function floorTo(v, unit) { return Math.floor((v + 1e-6) / unit) * unit; }
  function floor10(v) { return floorTo(v, 10); }
  function trunc1000(v) { return floorTo(v, 1000); }

  /* ── 근로소득공제 (소득세법 §47, 2026년 귀속) ─────────────────── */
  function wageDeduction(gross) {
    var g = Math.max(0, num(gross)), d;
    if (g <= 5000000) d = g * 0.7;
    else if (g <= 15000000) d = 3500000 + (g - 5000000) * 0.4;
    else if (g <= 45000000) d = 7500000 + (g - 15000000) * 0.15;
    else if (g <= 100000000) d = 12000000 + (g - 45000000) * 0.05;
    else d = 14750000 + (g - 100000000) * 0.02;
    return Math.min(d, R2026.wageDeductionCap, g);
  }

  /* ── 기본세율 (2026년 귀속) ──────────────────────────────────── */
  var BRACKETS = [
    { upTo: 14000000, rate: 0.06, progressive: 0 },
    { upTo: 50000000, rate: 0.15, progressive: 1260000 },
    { upTo: 88000000, rate: 0.24, progressive: 5760000 },
    { upTo: 150000000, rate: 0.35, progressive: 15440000 },
    { upTo: 300000000, rate: 0.38, progressive: 19940000 },
    { upTo: 500000000, rate: 0.40, progressive: 25940000 },
    { upTo: 1000000000, rate: 0.42, progressive: 35940000 },
    { upTo: Infinity, rate: 0.45, progressive: 65940000 }
  ];
  function bracketTax(base) {
    var b = Math.max(0, num(base));
    if (b <= 0) return 0;
    for (var i = 0; i < BRACKETS.length; i++) {
      if (b <= BRACKETS[i].upTo) return b * BRACKETS[i].rate - BRACKETS[i].progressive;
    }
    return 0;
  }

  /* ── 근로소득세액공제 (소득세법 §59, 한도 포함) ───────────────── */
  function laborTaxCredit(tax, gross) {
    var t = Math.max(0, num(tax)), g = Math.max(0, num(gross));
    if (t <= 0) return 0;
    var credit = t <= 1300000 ? t * 0.55 : 715000 + (t - 1300000) * 0.30;
    var limit;
    if (g <= 33000000) limit = 740000;
    else if (g <= 70000000) limit = Math.max(660000, 740000 - (g - 33000000) * 0.008);
    else if (g <= 120000000) limit = Math.max(500000, 660000 - (g - 70000000) * 0.5);
    else limit = Math.max(200000, 500000 - (g - 120000000) * 0.5);
    return Math.min(credit, limit);
  }

  /* ── 자녀세액공제 (소득세법 §59의2, 2026년 귀속) ────────────────
   * 1명 25만원 · 2명 55만원 · 3명 이상은 55만원 + (2명 초과 1명당) 40만원
   */
  function childTaxCredit(children) {
    var c = clamp(Math.round(num(children) || 0), 0, 10);
    if (c <= 0) return 0;
    if (c === 1) return R2026.childCredit1;
    if (c === 2) return R2026.childCredit2;
    return R2026.childCredit2 + (c - 2) * R2026.childCreditExtra;
  }

  /* ── 근로소득 간이세액표 (소득세법 시행령 별표2) ────────────────
   * 실제 급여명세서의 월 소득세. 표는 770,000~10,000,000원 구간만 담고 있어
   * 그 위는 별표2가 정한 계산식을 그대로 적용한다.
   */
  function withholdingTableIndex(monthly) {
    var W = typeof WITHHOLDING !== 'undefined' ? WITHHOLDING : null;
    if (!W) return -1;
    if (monthly < W.startMonthly || monthly >= 10000000) return -1;
    if (monthly < 1500000) return Math.floor((monthly - W.startMonthly) / W.smallStep);
    if (monthly < 3000000) return W.smallCount + Math.floor((monthly - 1500000) / W.midStep);
    return W.smallCount + W.midCount + Math.floor((monthly - 3000000) / W.bigStep);
  }

  function withholdingTax(monthlyTaxable, dependents, children) {
    var m = Math.max(0, num(monthlyTaxable));
    var d = clamp(Math.round(num(dependents) || 1), 1, 11);
    var kids = clamp(Math.round(num(children) || 0), 0, 10);
    var W = typeof WITHHOLDING !== 'undefined' ? WITHHOLDING : null;
    var tax;

    if (!W) {
      tax = Math.round(computeAnnualTax({ gross: m * 12, dependents: d, children: kids,
        pensionAnnual: Math.floor(Math.min(Math.max(Math.floor(m / 1000) * 1000, R2026.pensionBaseMin), R2026.pensionBaseMax) * R2026.pensionRate / 10) * 10 * 12,
        insuranceAnnual: 0 }).annualTax / 12);
    } else if (m < W.startMonthly) {
      tax = 0;
    } else if (m > 10000000) {
      var base = W.at10000[d - 1];
      var excess = m - 10000000;
      if (m <= 14000000) tax = base + excess * 0.98 * 0.35 + 25000;
      else if (m <= 28000000) tax = base + 1397000 + excess * 0.98 * 0.38;
      else if (m <= 30000000) tax = base + 6610600 + excess * 0.98 * 0.40;
      else if (m <= 45000000) tax = base + 7394600 + excess * 0.40;
      else if (m <= 87000000) tax = base + 13394600 + excess * 0.42;
      else tax = base + 31034600 + excess * 0.45;
    } else if (m === 10000000) {
      tax = W.at10000[d - 1];
    } else {
      var row = W.rows[withholdingTableIndex(m)];
      tax = row ? row[d - 1] : 0;
    }

    // 8세 이상 20세 이하 자녀 공제 (별표2 비고 3)
    if (kids > 0) {
      var childDed = kids === 1 ? 20830 : (kids === 2 ? 45830 : 45830 + (kids - 2) * 33330);
      tax -= childDed;
    }
    return Math.max(0, floor10(tax));
  }

  /* ── 연간 소득세 계산 ──────────────────────────────────────────
   * 보험료 특별소득공제와 표준세액공제(13만원) 중 유리한 쪽을 적용한다.
   * extraDeduction: 카드·월세처럼 나중에 더해지는 소득공제(기본 0).
   */
  function computeAnnualTax(o) {
    o = o || {};
    var gross = Math.max(0, num(o.gross));
    var dependents = clamp(Math.round(num(o.dependents) || 1), 1, 11);
    var childCredit = childTaxCredit(o.children);
    var pensionAnnual = Math.max(0, num(o.pensionAnnual));
    var insuranceAnnual = Math.max(0, num(o.insuranceAnnual));
    var extraDeduction = Math.max(0, num(o.extraDeduction));

    var wageDed = wageDeduction(gross);
    var income = Math.max(0, gross - wageDed);
    var basicDed = R2026.basicPerPerson * dependents;
    var beforeSpecial = Math.max(0, income - basicDed - pensionAnnual - extraDeduction);

    // A안: 건강·장기요양·고용보험료 특별소득공제 적용
    var baseA = Math.max(0, beforeSpecial - insuranceAnnual);
    var taxA = bracketTax(baseA);
    var creditA = laborTaxCredit(taxA, gross);
    var finalA = Math.max(0, taxA - creditA - childCredit);

    // B안: 보험료 공제 대신 표준세액공제 13만원
    var baseB = beforeSpecial;
    var taxB = bracketTax(baseB);
    var creditB = Math.min(taxB, laborTaxCredit(taxB, gross) + R2026.standardCredit);
    var finalB = Math.max(0, taxB - creditB - childCredit);

    var useA = finalA <= finalB;
    var annualTax = Math.round(useA ? finalA : finalB);

    return {
      gross: gross,
      wageDeduction: wageDed,
      income: income,
      basicDeduction: basicDed,
      pensionDeduction: pensionAnnual,
      insuranceDeduction: useA ? insuranceAnnual : 0,
      standardCredit: useA ? 0 : R2026.standardCredit,
      extraDeduction: extraDeduction,
      taxBase: useA ? baseA : baseB,
      computedTax: useA ? taxA : taxB,
      laborCredit: useA ? creditA : laborTaxCredit(taxB, gross),
      childCredit: childCredit,
      annualTax: annualTax,
      effectiveRate: gross > 0 ? annualTax / gross : 0,
      appliedOption: useA ? '보험료 특별소득공제' : '표준세액공제'
    };
  }

  /* ── 연봉 실수령액 ─────────────────────────────────────────────── */
  function computeSalary(input) {
    input = input || {};
    var annual = Math.max(0, num(input.annualSalary));
    var dependents = clamp(Math.round(num(input.dependents) || 1), 1, 11);
    var children = clamp(Math.round(num(input.children) || 0), 0, 10);
    var meal = clamp(num(input.meal), 0, R2026.mealFreeMax);

    var taxableAnnual = Math.max(0, annual - meal * 12);
    var monthlyTaxable = taxableAnnual / 12;

    // 국민연금: 기준소득월액(천원 미만 절사)에 상·하한 적용
    var pensionBase = clamp(trunc1000(monthlyTaxable), R2026.pensionBaseMin, R2026.pensionBaseMax);
    var pension = floor10(pensionBase * R2026.pensionRate);

    // 건강보험: 전체 보험료를 상·하한으로 자른 뒤 절반
    var healthTotal = clamp(monthlyTaxable * R2026.healthTotalRate, R2026.healthTotalMin, R2026.healthTotalMax);
    var health = floor10(healthTotal / 2);

    // 장기요양: 근로자 건강보험료 × 13.14%
    var ltc = floor10(health * R2026.ltcRate);

    // 고용보험 실업급여 근로자 0.9%
    var employ = floor10(monthlyTaxable * R2026.employRate);

    var insuranceTotal = pension + health + ltc + employ;

    var tax = computeAnnualTax({
      gross: taxableAnnual,
      dependents: dependents,
      children: children,
      pensionAnnual: pension * 12,
      insuranceAnnual: (health + ltc + employ) * 12
    });

    // 급여명세서에 실제로 찍히는 월 소득세 = 간이세액표 기준
    var incomeTax = withholdingTax(monthlyTaxable, dependents, children);
    var localTax = floor10(incomeTax * R2026.localTaxRate);
    var monthlyGross = monthlyTaxable + meal;
    var net = Math.max(0, Math.round(monthlyGross - insuranceTotal - incomeTax - localTax));

    return {
      annualSalary: annual,
      dependents: dependents,
      children: children,
      mealAllowance: meal,
      taxableAnnual: taxableAnnual,
      monthlyTaxable: monthlyTaxable,
      monthlyGross: monthlyGross,
      pensionBase: pensionBase,
      pension: pension,
      health: health,
      ltc: ltc,
      employ: employ,
      insuranceTotal: insuranceTotal,
      incomeTax: incomeTax,
      localTax: localTax,
      totalDeduction: insuranceTotal + incomeTax + localTax,
      net: net,
      netAnnual: net * 12,
      annualTaxDetail: tax,
      withholdingAnnual: incomeTax * 12,
      settlement: incomeTax * 12 - tax.annualTax,
      deductionRate: monthlyGross > 0 ? (insuranceTotal + incomeTax + localTax) / monthlyGross : 0
    };
  }

  /* ── 코인 물타기(평단가) ───────────────────────────────────────── */
  function computeAverage(input) {
    input = input || {};
    var qty = Math.max(0, num(input.qty));
    var avgPrice = Math.max(0, num(input.avgPrice));
    var addQty = Math.max(0, num(input.addQty));
    var addPrice = Math.max(0, num(input.addPrice));
    var currentPrice = Math.max(0, num(input.currentPrice));

    var totalQty = qty + addQty;
    var oldCost = qty * avgPrice;
    var addCost = addQty * addPrice;
    var totalCost = oldCost + addCost;
    var newAvg = totalQty > 0 ? totalCost / totalQty : 0;

    var avgChange = avgPrice > 0 ? newAvg / avgPrice - 1 : 0;
    var breakEven = currentPrice > 0 ? newAvg / currentPrice - 1 : null;
    var unrealized = currentPrice > 0 && totalQty > 0 ? (currentPrice - newAvg) * totalQty : 0;
    var unrealizedRate = newAvg > 0 && currentPrice > 0 ? currentPrice / newAvg - 1 : 0;

    return {
      oldQty: qty,
      oldCost: oldCost,
      addQty: addQty,
      addCost: addCost,
      totalQty: totalQty,
      totalCost: totalCost,
      newAvgPrice: newAvg,
      avgChange: avgChange,
      breakEvenFromCurrent: breakEven,
      valuation: totalQty * currentPrice,
      unrealizedPnl: unrealized,
      unrealizedRate: unrealizedRate
    };
  }

  /* ── 코인 선물 청산가 (격리 마진 근사) ────────────────────────── */
  function computeFutures(input) {
    input = input || {};
    var entry = Math.max(0, num(input.entry));
    var leverage = clamp(num(input.leverage) || 1, 1, 200);
    var mmrPct = clamp(num(input.maintenanceMarginPct), 0.01, 50);
    var side = input.side === 'short' ? 'short' : 'long';
    var margin = Math.max(0, num(input.margin));
    var target = Math.max(0, num(input.targetPrice));

    var mmr = mmrPct / 100;
    var liq;
    if (side === 'long') {
      liq = entry * (1 - 1 / leverage + mmr);
      liq = Math.max(liq, entry * 0.0001);
    } else {
      liq = entry * (1 + 1 / leverage - mmr);
    }
    if (entry <= 0 || liq <= 0) {
      liq = 0;
    }

    var liqDistance = entry > 0 ? liq / entry - 1 : 0;
    var positionSize = margin * leverage;          // 명목가
    var qty = entry > 0 ? positionSize / entry : 0;

    var roiAtTarget = 0, pnlAtTarget = 0;
    if (target > 0 && entry > 0) {
      var move = target / entry - 1;
      if (side === 'short') move = -move;
      roiAtTarget = move * leverage;
      pnlAtTarget = positionSize * move;
    }

    return {
      side: side,
      entry: entry,
      leverage: leverage,
      maintenanceMarginPct: mmrPct,
      liquidationPrice: liq,
      liquidationDistance: liqDistance,
      margin: margin,
      positionSize: positionSize,
      qty: qty,
      targetPrice: target,
      roiAtTarget: roiAtTarget,
      pnlAtTarget: pnlAtTarget
    };
  }

  /* ── 적립식 투자 · 복리 ───────────────────────────────────────── */
  function computeCompound(input) {
    input = input || {};
    var initial = Math.max(0, num(input.initial));
    var monthly = Math.max(0, num(input.monthly));
    var annualRatePct = clamp(num(input.annualRatePct), -99.9, 100);
    var years = clamp(Math.round(num(input.years) || 1), 1, 60);
    var atStart = input.contributionTiming !== 'end';

    var annualRate = annualRatePct / 100;
    var monthlyRate = Math.pow(1 + annualRate, 1 / 12) - 1;

    var balance = initial;
    var principal = initial;
    var rows = [];
    var months = years * 12;

    for (var m = 1; m <= months; m++) {
      if (atStart) {
        balance = (balance + monthly) * (1 + monthlyRate);
        principal += monthly;
      } else {
        balance = balance * (1 + monthlyRate) + monthly;
        principal += monthly;
      }
      if (m % 12 === 0) {
        rows.push({
          year: m / 12,
          principal: principal,
          balance: balance,
          gain: balance - principal
        });
      }
    }

    var totalProfit = balance - principal;
    return {
      initial: initial,
      monthly: monthly,
      annualRatePct: annualRatePct,
      years: years,
      monthlyRate: monthlyRate,
      rows: rows,
      totalPrincipal: principal,
      finalBalance: balance,
      totalProfit: totalProfit,
      returnRate: principal > 0 ? totalProfit / principal : 0
    };
  }

  /* ══ 연말정산 공통 ══════════════════════════════════════════════
   * 카드·월세 공제의 절세액은 "공제액 × 한계세율"로만 보면 실제보다 크게
   * 나온다. 산출세액이 줄면 근로소득세액공제(산출세액의 55%·30%)도 함께
   * 줄고, 공제가 구간을 넘으면 세율도 낮아지기 때문이다. 그래서 여기서는
   * 공제 전후의 결정세액을 각각 계산해 그 차이를 절세액으로 쓴다.
   */

  /** 과세표준이 속한 구간의 한계세율 */
  function marginalRate(taxBase) {
    var b = Math.max(0, num(taxBase));
    for (var i = 0; i < BRACKETS.length; i++) {
      if (b <= BRACKETS[i].upTo) return BRACKETS[i].rate;
    }
    return BRACKETS[BRACKETS.length - 1].rate;
  }

  /** 총급여·부양가족 수만으로 연말정산 과세표준과 결정세액을 추정한다 */
  function estimateTaxContext(grossSalary, dependents) {
    var g = Math.max(0, num(grossSalary));
    var dep = clamp(Math.round(num(dependents) || 1), 1, 11);
    var monthlyTaxable = g / 12;
    var pensionBase = clamp(trunc1000(monthlyTaxable), R2026.pensionBaseMin, R2026.pensionBaseMax);
    var pensionAnnual = floor10(pensionBase * R2026.pensionRate) * 12;
    var healthTotal = clamp(monthlyTaxable * R2026.healthTotalRate, R2026.healthTotalMin, R2026.healthTotalMax);
    var health = floor10(healthTotal / 2);
    var ltc = floor10(health * R2026.ltcRate);
    var employ = floor10(monthlyTaxable * R2026.employRate);
    var insuranceAnnual = (health + ltc + employ) * 12;
    var est = computeAnnualTax({
      gross: g,
      dependents: dep,
      children: 0,
      pensionAnnual: pensionAnnual,
      insuranceAnnual: insuranceAnnual
    });
    return {
      gross: g,
      dependents: dep,
      pensionAnnual: pensionAnnual,
      insuranceAnnual: insuranceAnnual,
      taxBase: est.taxBase,
      annualTax: est.annualTax,
      marginalRate: marginalRate(est.taxBase)
    };
  }

  /** 소득공제 1원이 실제로 줄여 주는 결정세액 */
  function deductionSaving(ctx, deduction) {
    var d = Math.max(0, num(deduction));
    if (!ctx) return { taxSaving: 0, totalSaving: 0, effectiveRate: 0, taxBaseAfter: 0 };
    if (d <= 0) return { taxSaving: 0, totalSaving: 0, effectiveRate: 0, taxBaseAfter: ctx.taxBase };
    var after = computeAnnualTax({
      gross: ctx.gross,
      dependents: ctx.dependents,
      children: 0,
      pensionAnnual: ctx.pensionAnnual,
      insuranceAnnual: ctx.insuranceAnnual,
      extraDeduction: d
    });
    var saving = Math.max(0, ctx.annualTax - after.annualTax);
    return {
      taxSaving: Math.round(saving),
      totalSaving: Math.round(saving * (1 + R2026.localTaxRate)),
      effectiveRate: d > 0 ? saving / d : 0,
      taxBaseAfter: after.taxBase
    };
  }

  /* ══ 2026년 월세 세액공제 vs 현금영수증 소득공제 ════════════════
   * 조세특례제한법 §95의2: 총급여 8,000만 원 이하 무주택 세대주,
   * 월세액 15%(총급여 5,500만 원 이하 17%), 연 1,000만 원 한도.
   * 같은 법 §126의2 ④: 세액공제 받은 월세는 카드 소득공제에서 제외.
   */
  var RENT2026 = {
    creditCap: 10000000,
    creditRateLow: 0.17,
    creditRateHigh: 0.15,
    lowIncomeLimit: 55000000,
    incomeLimit: 80000000,
    thresholdRate: 0.25,
    cashRate: 0.30,
    cardLimitGross: 70000000,
    cardLimitLow: 3000000,
    cardLimitHigh: 2500000
  };

  function computeRentCompare(input) {
    input = input || {};
    var gross = Math.max(0, num(input.grossSalary));
    var rent = Math.max(0, num(input.annualRent));
    var other = Math.max(0, num(input.otherCardSpend));
    var dependents = clamp(Math.round(num(input.dependents) || 1), 1, 11);
    var meetsRequirement = input.meetsRequirement !== false;

    var ctx = estimateTaxContext(gross, dependents);

    /* ① 월세액 세액공제 */
    var creditRate = gross <= RENT2026.lowIncomeLimit ? RENT2026.creditRateLow
      : (gross <= RENT2026.incomeLimit ? RENT2026.creditRateHigh : 0);
    var creditBase = Math.min(rent, RENT2026.creditCap);
    var creditAmount = Math.round(creditBase * creditRate);
    var creditApplied = meetsRequirement ? Math.min(creditAmount, ctx.annualTax) : 0;

    /* ② 현금영수증 소득공제 (세액공제를 받지 않는 경우에만 가능)
     * 월세를 카드 사용액에 "추가로" 넣었을 때 늘어나는 공제액을 본다.
     * 25% 문턱은 내가 어차피 쓰는 그 외 사용액이 먼저 채우는 것으로 계산한다.
     */
    var threshold = gross * RENT2026.thresholdRate;
    var totalSpend = other + rent;
    var excess = Math.max(0, totalSpend - threshold);
    var otherExcess = Math.max(0, other - threshold);
    var rentExcess = Math.max(0, rent - Math.max(0, threshold - other));
    var cardLimit = gross <= RENT2026.cardLimitGross ? RENT2026.cardLimitLow : RENT2026.cardLimitHigh;
    var otherDeduction = Math.min(otherExcess * RENT2026.cashRate, cardLimit);
    var remainingLimit = Math.max(0, cardLimit - otherDeduction);
    var rentDeduction = Math.min(rentExcess * RENT2026.cashRate, remainingLimit);
    var cash = deductionSaving(ctx, rentDeduction);

    var gap = creditApplied - cash.taxSaving;
    var winner = gap > 0 ? 'credit' : (gap < 0 ? 'cash' : 'tie');

    return {
      grossSalary: gross,
      annualRent: rent,
      otherCardSpend: other,
      dependents: dependents,
      meetsRequirement: meetsRequirement,
      taxableIncomeLimit: RENT2026.incomeLimit,
      lowIncomeLimit: RENT2026.lowIncomeLimit,
      creditRate: creditRate,
      creditBase: creditBase,
      creditCapApplied: rent > RENT2026.creditCap,
      creditAmount: creditAmount,
      creditApplied: creditApplied,
      creditLimitedByTax: meetsRequirement && creditAmount > ctx.annualTax,
      creditMax: Math.round(RENT2026.creditCap * creditRate),
      threshold: threshold,
      totalSpend: totalSpend,
      excessSpend: excess,
      thresholdShort: Math.max(0, threshold - totalSpend),
      rentExcess: rentExcess,
      cardLimit: cardLimit,
      otherDeduction: otherDeduction,
      remainingLimit: remainingLimit,
      rentDeduction: rentDeduction,
      rentDeductionCapped: rentExcess * RENT2026.cashRate > remainingLimit,
      cashTaxSaving: cash.taxSaving,
      cashTotalSaving: cash.totalSaving,
      cashEffectiveRate: cash.effectiveRate,
      marginalRate: ctx.marginalRate,
      taxBase: ctx.taxBase,
      annualTax: ctx.annualTax,
      breakEvenRate: creditRate > 0 ? creditRate / RENT2026.cashRate : null,
      winner: winner,
      gap: Math.abs(gap)
    };
  }

  /* ══ 2026년 신용카드 등 사용금액 소득공제 ══════════════════════
   * 조세특례제한법 §126의2: 총급여 25% 초과분에 신용 15%·체크/현금 30%.
   * 25% 문턱은 공제율이 낮은 신용카드 사용분부터 채운다(시행령 §121의2).
   * 한도 300/250만 원, 2026년 사용분부터 자녀 1명 350만·2명 이상 400만 원.
   */
  var CARD2026 = {
    thresholdRate: 0.25,
    creditRate: 0.15,
    debitRate: 0.30,
    limitGross: 70000000
  };

  function cardDeductionLimit(grossSalary, children) {
    var g = Math.max(0, num(grossSalary));
    var c = clamp(Math.round(num(children) || 0), 0, 6);
    if (g <= CARD2026.limitGross) {
      if (c >= 2) return 4000000;
      if (c === 1) return 3500000;
      return 3000000;
    }
    if (c >= 2) return 3000000;
    if (c === 1) return 2750000;
    return 2500000;
  }

  function computeCardDeduction(input) {
    input = input || {};
    var gross = Math.max(0, num(input.grossSalary));
    var credit = Math.max(0, num(input.creditCard));
    var debit = Math.max(0, num(input.debitCash));
    var children = clamp(Math.round(num(input.children) || 0), 0, 6);
    var dependents = clamp(Math.round(num(input.dependents) || 1), 1, 11);

    var ctx = estimateTaxContext(gross, dependents);
    var threshold = gross * CARD2026.thresholdRate;
    var totalSpend = credit + debit;

    var excessCredit = 0, excessDebit = 0;
    if (credit >= threshold) {
      excessCredit = credit - threshold;
      excessDebit = debit;
    } else {
      excessCredit = 0;
      excessDebit = Math.max(0, totalSpend - threshold);
    }
    var creditPart = excessCredit * CARD2026.creditRate;
    var debitPart = excessDebit * CARD2026.debitRate;
    var rawDeduction = creditPart + debitPart;
    var limit = cardDeductionLimit(gross, children);
    var deduction = Math.min(rawDeduction, limit);
    var saving = deductionSaving(ctx, deduction);

    return {
      grossSalary: gross,
      creditCard: credit,
      debitCash: debit,
      children: children,
      dependents: dependents,
      threshold: threshold,
      totalSpend: totalSpend,
      excessSpend: Math.max(0, totalSpend - threshold),
      thresholdShort: Math.max(0, threshold - totalSpend),
      excessCredit: excessCredit,
      excessDebit: excessDebit,
      creditPart: creditPart,
      debitPart: debitPart,
      rawDeduction: rawDeduction,
      limit: limit,
      limitApplied: rawDeduction > limit,
      lostDeduction: Math.max(0, rawDeduction - limit),
      deduction: deduction,
      limitLeft: Math.max(0, limit - deduction),
      marginalRate: ctx.marginalRate,
      taxBase: ctx.taxBase,
      annualTax: ctx.annualTax,
      taxSaving: saving.taxSaving,
      totalSaving: saving.totalSaving,
      effectiveSavingRate: saving.effectiveRate
    };
  }

  root.CalcCore = {
    R2026: R2026,
    marginalRate: marginalRate,
    estimateTaxContext: estimateTaxContext,
    deductionSaving: deductionSaving,
    RENT2026: RENT2026,
    computeRentCompare: computeRentCompare,
    CARD2026: CARD2026,
    cardDeductionLimit: cardDeductionLimit,
    computeCardDeduction: computeCardDeduction,
    wageDeduction: wageDeduction,
    bracketTax: bracketTax,
    laborTaxCredit: laborTaxCredit,
    computeAnnualTax: computeAnnualTax,
    childTaxCredit: childTaxCredit,
    withholdingTax: withholdingTax,
    computeSalary: computeSalary,
    computeAverage: computeAverage,
    computeFutures: computeFutures,
    computeCompound: computeCompound
  };
})(typeof window !== 'undefined' ? window : this);
