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
   */
  function computeAnnualTax(o) {
    o = o || {};
    var gross = Math.max(0, num(o.gross));
    var dependents = clamp(Math.round(num(o.dependents) || 1), 1, 11);
    var childCredit = childTaxCredit(o.children);
    var pensionAnnual = Math.max(0, num(o.pensionAnnual));
    var insuranceAnnual = Math.max(0, num(o.insuranceAnnual));

    var wageDed = wageDeduction(gross);
    var income = Math.max(0, gross - wageDed);
    var basicDed = R2026.basicPerPerson * dependents;
    var beforeSpecial = Math.max(0, income - basicDed - pensionAnnual);

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

  root.CalcCore = {
    R2026: R2026,
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
