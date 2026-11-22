/* 월세 세액공제 vs 현금영수증 소득공제 비교기 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var RENT_STEPS = [3000000, 4000000, 5000000, 6000000, 7000000, 8000000, 9000000, 10000000, 11000000, 12000000];

  function readInputs() {
    return {
      grossSalary: UI.num($('gross-salary')),
      annualRent: UI.num($('annual-rent')),
      otherCardSpend: UI.num($('other-card')),
      dependents: UI.num($('dependents')),
      meetsRequirement: UI.segValue($('require-seg'), 'yes') === 'yes'
    };
  }

  function render() {
    var input = readInputs();
    var r = CalcCore.computeRentCompare(input);

    var credit = UI.won(r.creditApplied);
    var cash = UI.won(r.cashTaxSaving);

    if (r.winner === 'credit') {
      UI.setText('winner', '월세 세액공제');
      UI.setText('winner-sub', '세액공제 ' + credit + ' vs 현금영수증 ' + cash + ' · ' + UI.won(r.gap) + ' 더 유리');
    } else if (r.winner === 'cash') {
      UI.setText('winner', '현금영수증 소득공제');
      UI.setText('winner-sub', '현금영수증 ' + cash + ' vs 세액공제 ' + credit + ' · ' + UI.won(r.gap) + ' 더 유리');
    } else {
      var bothZero = r.creditApplied === 0 && r.cashTaxSaving === 0;
      var parts = [];
      if (r.creditRate === 0) parts.push('총급여 8,000만 원 초과로 세액공제 대상이 아님');
      else if (!r.meetsRequirement) parts.push('세액공제 요건 미충족');
      if (r.rentDeduction === 0) parts.push('월세가 카드 공제 문턱을 넘지 못했거나 한도가 이미 참');
      UI.setText('winner', bothZero ? '챙길 공제 없음' : '차이 없음');
      UI.setText('winner-sub', parts.length ? parts.join(' · ') + ' — 이 조건에서는 두 방법 모두 ' + credit + '입니다.'
        : '두 방법의 세금 감소가 ' + credit + '로 같습니다.');
    }

    UI.setText('credit-saving', credit);
    UI.setText('cash-saving', cash);
    UI.setText('gap', (r.winner === 'credit' ? '+' : (r.winner === 'cash' ? '−' : '')) + UI.won(r.gap));
    UI.setText('marginal', (r.marginalRate * 100).toFixed(0) + '%');
    var creditNote;
    if (r.creditRate === 0) {
      creditNote = '총급여 ' + UI.won(r.grossSalary) + '로 8,000만 원을 넘어 월세 세액공제 대상이 아닙니다. 현금영수증 소득공제만 남습니다.';
    } else if (!r.meetsRequirement) {
      creditNote = '무주택 세대주·전입신고 등 요건을 충족하지 않으면 세액공제를 받을 수 없습니다. 계산상으로는 ' + UI.won(r.creditAmount) + '을 받을 수 있는 조건입니다.';
    } else if (r.creditLimitedByTax) {
      creditNote = '산출세액(' + UI.won(r.annualTax) + ')이 공제액보다 작아, 실제로는 산출세액까지(' + credit + ')만 줄어듭니다.';
    } else {
      creditNote = '총급여 ' + (r.creditRate === 0.17 ? '5,500만 원 이하' : '5,500만 원 초과~8,000만 원 이하') + ' 구간이라 월세액의 ' + (r.creditRate * 100).toFixed(0) + '%를 세액에서 뺍니다.';
    }
    UI.setText('credit-note', creditNote);

    /* ── 두 방법 상세 비교 ── */
    var rows = [
      '<tr><td>공제 방식</td><td>세금(산출세액)에서 직접 차감</td><td>과세표준에서 차감</td></tr>',
      '<tr><td>공제율</td><td>' + (r.creditRate > 0 ? (r.creditRate * 100).toFixed(0) + '%' : '대상 아님') +
        '<br><span class="subnote">총급여 5,500만 원 이하 17% · 8,000만 원 이하 15%</span></td><td>30%' +
        '<br><span class="subnote">총급여 25% 초과분에만</span></td></tr>',
      '<tr><td>공제 대상 월세</td><td>' + UI.won(r.creditBase) + (r.creditCapApplied ? '<br><span class="subnote">연 1,000만 원 한도 적용</span>' : '') +
        '</td><td>' + UI.won(r.rentExcess) + '<br><span class="subnote">문턱 ' + UI.won(r.threshold) + ' 초과분</span></td></tr>',
      '<tr><td>산출 공제액</td><td>' + UI.won(r.creditAmount) + '</td><td>' + UI.won(r.rentDeduction) + '<br><span class="subnote">소득공제 금액</span></td></tr>',
      '<tr><td>세금 감소 (소득세)</td><td>' + credit + (r.creditLimitedByTax ? '<br><span class="subnote">결정세액 한도</span>' : '') +
        '</td><td>' + cash + '<br><span class="subnote">한계세율 ' + (r.marginalRate * 100).toFixed(0) + '% 감안</span></td></tr>',
      '<tr class="total"><td>결론</td><td colspan="2">' + (r.winner === 'credit'
        ? '월세 세액공제가 ' + UI.won(r.gap) + ' 유리'
        : (r.winner === 'cash'
          ? '현금영수증 소득공제가 ' + UI.won(r.gap) + ' 유리 — 세액공제 요건 또는 세액 한도 확인'
          : '두 방법의 차이 없음')) + '</td></tr>'
    ];
    UI.setHtml('detail-rows', rows.join(''));

    /* ── 월세액별 비교 ── */
    var table = RENT_STEPS.map(function (rent) {
      var s = CalcCore.computeRentCompare({
        grossSalary: input.grossSalary,
        annualRent: rent,
        otherCardSpend: input.otherCardSpend,
        dependents: input.dependents,
        meetsRequirement: input.meetsRequirement
      });
      var label = s.winner === 'credit' ? '세액공제' : (s.winner === 'cash' ? '현금영수증' : '차이 없음');
      return '<tr><td>' + UI.int(rent) + '원</td><td>' + UI.won(s.creditApplied) + '</td><td>' +
        UI.won(s.cashTaxSaving) + '</td><td>' + label + '</td></tr>';
    }).join('');
    UI.setHtml('rent-rows', table);
    UI.setText('rent-caption', '총급여 ' + UI.won(input.grossSalary) + ' · 그 외 체크·현금 ' + UI.won(input.otherCardSpend) +
      ' · 부양가족 ' + r.dependents + '명 기준');

    UI.setText('stat-threshold-short', r.thresholdShort > 0
      ? '카드 사용액이 총급여 25%(' + UI.won(r.threshold) + ')에 ' + UI.won(r.thresholdShort) + ' 모자랍니다. 이 상태로는 월세를 현금영수증으로 넣어도 소득공제가 0원입니다.'
      : '카드 사용액이 총급여 25%(' + UI.won(r.threshold) + ')를 넘어, 월세 ' + UI.won(r.rentExcess) + '가 소득공제 대상에 들어갑니다.');
    var limitText;
    if (r.rentDeductionCapped) {
      limitText = '카드 소득공제 한도(' + UI.won(r.cardLimit) + ')가 이미 찼습니다. 그 외 사용액만으로 ' + UI.won(r.otherDeduction) + '을 공제해 월세 몫이 남지 않습니다.';
    } else if (r.otherDeduction === 0) {
      limitText = '그 외 사용액만으로는 카드 소득공제가 0원이라, 한도 ' + UI.won(r.cardLimit) + '이 그대로 남아 있습니다.';
    } else {
      limitText = '카드 소득공제 한도 ' + UI.won(r.cardLimit) + ' 중 ' + UI.won(r.remainingLimit) + '이 남아 있습니다.';
    }
    UI.setText('stat-limit', limitText);
    UI.setText('stat-break-even', r.breakEvenRate
      ? '현금영수증 쪽이 이기려면 한계세율이 ' + (r.breakEvenRate * 100).toFixed(1) + '%를 넘어야 합니다. 현행 최고세율이 45%라 계산상 불가능하고, 그래서 요건만 갖추면 세액공제가 사실상 정답입니다.'
      : '총급여 8,000만 원을 넘으면 세액공제가 없으므로, 현금영수증 소득공제만 남습니다.');
  }

  function bindPreset(container, input) {
    if (!container || !input) return;
    container.addEventListener('click', function (e) {
      var t = e.target;
      var value = t && t.getAttribute ? t.getAttribute('data-value') : null;
      if (!value) return;
      input.value = value;
      render();
    });
  }

  bindPreset($('gross-presets'), $('gross-salary'));
  bindPreset($('rent-presets'), $('annual-rent'));
  UI.bindSegmented($('require-seg'), render);
  UI.onInput(['gross-salary', 'annual-rent', 'other-card', 'dependents'], render);
  UI.year($('year'));
  render();
})();
