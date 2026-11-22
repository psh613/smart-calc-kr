/* 2026 연봉 실수령액 계산기 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var annualEl = $('annual');
  var mealEl = $('meal');
  var depEl = $('dependents');
  var childEl = $('children');
  var presets = $('annual-presets');

  var COMPARE = [24000000, 30000000, 40000000, 50000000, 60000000, 70000000, 80000000, 100000000, 120000000];

  function readInputs() {
    return {
      annualSalary: UI.num(annualEl),
      meal: UI.num(mealEl),
      dependents: UI.num(depEl),
      children: childEl ? UI.num(childEl) : 0
    };
  }

  function row(label, value, note, cls) {
    return '<tr' + (cls ? ' class="' + cls + '"' : '') + '><td>' + label + '</td><td>' + value + '</td>' + (note === null ? '' : '<td>' + note + '</td>') + '</tr>';
  }

  function render() {
    if (UI.num(mealEl) > 200000) mealEl.value = '200000';
    if (UI.num(annualEl) < 0) annualEl.value = '0';

    var input = readInputs();
    var r = CalcCore.computeSalary(input);
    var a = r.annualTaxDetail;

    UI.setText('net', UI.won(r.net));
    UI.setText('net-sub', '연 실수령 ' + UI.won(r.netAnnual) + ' · 월 공제 ' + UI.won(r.totalDeduction));
    UI.setText('deduct-total', UI.won(r.totalDeduction));
    UI.setText('deduct-rate', (r.deductionRate * 100).toFixed(1) + '%');

    var monthlyRows = [
      row('과세 월급여', UI.won(r.monthlyTaxable), '연봉 ÷ 12 − 비과세 식대', 'muted'),
      row('비과세 식대', UI.won(r.mealAllowance), '소득세·4대보험 산정 제외', 'muted'),
      row('국민연금', '−' + UI.won(r.pension), '기준소득월액 ' + UI.int(r.pensionBase) + '원 × 4.75%'),
      row('건강보험', '−' + UI.won(r.health), '보수월액 × 7.19% ÷ 2'),
      row('장기요양보험', '−' + UI.won(r.ltc), '근로자 건강보험료 × 13.14%'),
      row('고용보험', '−' + UI.won(r.employ), '보수월액 × 0.9%'),
      row('소득세', '−' + UI.won(r.incomeTax), '간이세액표 · 가족 ' + r.dependents + '명' + (r.children > 0 ? ' · 자녀 ' + r.children + '명 공제' : '')),
      row('지방소득세', '−' + UI.won(r.localTax), '소득세 × 10%'),
      row('공제 합계', '−' + UI.won(r.totalDeduction), '보수의 ' + (r.deductionRate * 100).toFixed(1) + '%', 'total'),
      row('월 실수령액', UI.won(r.net), '과세급여 + 식대 − 공제', 'total')
    ];
    UI.setHtml('monthly-rows', monthlyRows.join(''));

    var annualRows = [
      row('총급여 (과세 대상)', UI.won(a.gross), null),
      row('근로소득공제', '−' + UI.won(a.wageDeduction), null),
      row('근로소득금액', UI.won(a.income), null),
      row('기본공제', '−' + UI.won(a.basicDeduction), '150만원 × ' + r.dependents + '명'),
      row('연금보험료공제', '−' + UI.won(a.pensionDeduction), '국민연금 근로자 부담분'),
      row(a.appliedOption === '표준세액공제' ? '보험료 공제 (미적용)' : '보험료 특별소득공제',
        a.insuranceDeduction > 0 ? '−' + UI.won(a.insuranceDeduction) : '0원',
        '건강·장기요양·고용보험료'),
      row('과세표준', UI.won(a.taxBase), null),
      row('산출세액', UI.won(a.computedTax), '기본세율 6~45%'),
      row('근로소득세액공제', '−' + UI.won(a.laborCredit), '산출세액의 55%·30% (한도 적용)')
    ];
    if (a.childCredit > 0) {
      annualRows.push(row('자녀세액공제', '−' + UI.won(a.childCredit), '자녀 ' + r.children + '명'));
    }
    if (a.appliedOption === '표준세액공제') {
      annualRows.push(row('표준세액공제', '−' + UI.won(a.standardCredit), '특별공제 미신청 시 13만원'));
    }
    annualRows.push(row('결정세액 (연 소득세)', UI.won(a.annualTax), '실효세율 ' + (a.effectiveRate * 100).toFixed(2) + '%', 'total'));
    annualRows.push(row('원천징수 합계', UI.won(r.withholdingAnnual), '급여에서 뗀 소득세 × 12'));
    var settle = r.settlement;
    annualRows.push(row(
      '정산 예상 (' + (settle >= 0 ? '환급' : '추납') + ')',
      (settle >= 0 ? '+' : '−') + UI.won(Math.abs(settle)),
      settle >= 0 ? '연말정산에서 돌려받을 것으로 예상' : '연말정산에서 더 낼 것으로 예상',
      'muted'
    ));
    UI.setHtml('annual-rows', annualRows.join(''));
    UI.setText('settle-note', (settle >= 0
      ? '매달 뗀 세금이 1년치 실제 세금보다 많아, 연말정산에서 약 ' + UI.won(settle) + '을 돌려받을 것으로 보입니다.'
      : '매달 뗀 세금이 1년치 실제 세금보다 적어, 연말정산에서 약 ' + UI.won(-settle) + '을 더 낼 것으로 보입니다.')
      + ' 신용카드·의료비·교육비·월세 공제는 반영하지 않았으므로, 실제로는 이만큼 차이가 줄거나 환급으로 바뀔 수 있습니다.');

    var compareHtml = COMPARE.map(function (salary) {
      var c = CalcCore.computeSalary({ annualSalary: salary, meal: input.meal, dependents: input.dependents, children: input.children });
      return '<tr><td>' + (salary / 10000).toLocaleString('ko-KR') + '만원</td><td>' + UI.won(c.net) + '</td><td>' + UI.won(c.totalDeduction) + '</td><td>' + (c.deductionRate * 100).toFixed(1) + '%</td></tr>';
    }).join('');
    UI.setHtml('compare-rows', compareHtml);
    UI.setText('compare-caption', '식대 ' + UI.won(input.meal || 0) + ' · 부양가족 ' + r.dependents + '명' + (r.children > 0 ? ' · 자녀 ' + r.children + '명' : '') + ' 기준');

    if (presets) {
      Array.prototype.forEach.call(presets.querySelectorAll('button'), function (btn) {
        btn.setAttribute('aria-pressed', Number(btn.getAttribute('data-value')) === UI.num(annualEl) ? 'true' : 'false');
      });
    }
  }

  if (presets) {
    presets.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-value]');
      if (!btn) return;
      annualEl.value = btn.getAttribute('data-value');
      render();
    });
  }

  UI.onInput(['annual', 'meal', 'dependents', 'children'], render);
  UI.year($('year'));
  render();
})();
