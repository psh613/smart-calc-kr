/* 연말정산 신용카드·체크카드·현금영수증 소득공제 시뮬레이터 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var MIX = [
    { label: '신용 100%', credit: 1 },
    { label: '신용 70 : 체크 30', credit: 0.7 },
    { label: '신용 50 : 체크 50', credit: 0.5 },
    { label: '신용 30 : 체크 70', credit: 0.3 },
    { label: '체크 100%', credit: 0 }
  ];

  function readInputs() {
    return {
      grossSalary: UI.num($('gross-salary')),
      creditCard: UI.num($('credit-card')),
      debitCash: UI.num($('debit-cash')),
      dependents: UI.num($('dependents')),
      children: UI.num($('children'))
    };
  }

  function render() {
    var input = readInputs();
    var r = CalcCore.computeCardDeduction(input);

    UI.setText('deduction', UI.won(r.deduction));
    UI.setText('deduction-sub', '예상 절세액 ' + UI.won(r.taxSaving) + ' (지방소득세 포함 ' + UI.won(r.totalSaving) + ')');
    UI.setText('tax-saving', UI.won(r.taxSaving));
    UI.setText('total-saving', UI.won(r.totalSaving));
    UI.setText('threshold', UI.won(r.threshold));
    UI.setText('limit-left', UI.won(r.limitLeft));

    var statusText;
    if (r.totalSpend <= 0) {
      statusText = '카드·현금영수증 사용액을 넣으면 예상 소득공제액이 계산됩니다.';
    } else if (r.thresholdShort > 0) {
      statusText = '총급여의 25%(' + UI.won(r.threshold) + ')까지 ' + UI.won(r.thresholdShort) + ' 모자랍니다. 지금은 공제액이 0원이에요.';
    } else if (r.limitApplied) {
      statusText = '산출 공제액이 한도(' + UI.won(r.limit) + ')를 넘어 ' + UI.won(r.lostDeduction) + '은 잘려 나갔습니다. 한도가 이미 꽉 찼습니다.';
    } else {
      statusText = '한도 ' + UI.won(r.limit) + ' 중 ' + UI.won(r.limitLeft) + '이 남아 있습니다. 남은 기간 체크카드·현금영수증을 쓰면 공제가 더 늘어납니다.';
    }
    UI.setText('status', statusText);

    /* ── 상세 계산 ── */
    var rows = [
      '<tr><td>총급여</td><td>' + UI.won(r.grossSalary) + '</td><td>근로소득 기준</td></tr>',
      '<tr><td>최저사용금액 (25%)</td><td>' + UI.won(r.threshold) + '</td><td>이 금액을 넘어야 공제 시작</td></tr>',
      '<tr><td>총 사용액</td><td>' + UI.won(r.totalSpend) + '</td><td>신용 + 체크·현금</td></tr>',
      '<tr><td>25% 초과분</td><td>' + UI.won(r.excessSpend) + '</td><td>공제 계산 대상</td></tr>',
      '<tr><td>신용카드 15%</td><td>' + UI.won(r.creditPart) + '</td><td>' + UI.won(r.excessCredit) + ' × 15%</td></tr>',
      '<tr><td>체크·현금영수증 30%</td><td>' + UI.won(r.debitPart) + '</td><td>' + UI.won(r.excessDebit) + ' × 30%</td></tr>',
      '<tr><td>산출 공제액</td><td>' + UI.won(r.rawDeduction) + '</td><td>15% + 30% 합계</td></tr>',
      '<tr><td>공제 한도</td><td>' + UI.won(r.limit) + '</td><td>총급여 ' + (r.grossSalary <= 70000000 ? '7,000만 원 이하' : '7,000만 원 초과') +
        (r.children >= 2 ? ' · 자녀 2명 이상 가산' : (r.children === 1 ? ' · 자녀 1명 가산' : '')) + '</td></tr>',
      '<tr class="total"><td>적용 소득공제액</td><td>' + UI.won(r.deduction) + '</td><td>' + (r.limitApplied ? '한도 적용' : '한도 이내') + '</td></tr>',
      '<tr><td>공제 전 추정 과세표준</td><td>' + UI.won(r.taxBase) + '</td><td>근로소득공제·기본공제·보험료 공제 반영</td></tr>',
      '<tr><td>한계세율</td><td>' + (r.marginalRate * 100).toFixed(0) + '%</td><td>공제액에 적용되는 구간 세율</td></tr>',
      '<tr class="total"><td>예상 절세액 (소득세)</td><td>' + UI.won(r.taxSaving) + '</td><td>근로소득세액공제 조정 반영</td></tr>'
    ];
    UI.setHtml('detail-rows', rows.join(''));

    /* ── 같은 지출, 결제수단만 바꾸면 ── */
    var total = r.totalSpend;
    var mixRows = MIX.map(function (m) {
      var s = CalcCore.computeCardDeduction({
        grossSalary: input.grossSalary,
        creditCard: Math.round(total * m.credit),
        debitCash: Math.round(total * (1 - m.credit)),
        dependents: input.dependents,
        children: input.children
      });
      return '<tr' + (Math.abs(m.credit * total - input.creditCard) < 1 ? ' class="total"' : '') + '><td>' + m.label +
        '</td><td>' + UI.won(s.deduction) + '</td><td>' + UI.won(s.taxSaving) + '</td></tr>';
    }).join('');
    UI.setHtml('mix-rows', mixRows);
    UI.setText('mix-caption', '총 사용액 ' + UI.won(total) + '을 그대로 두고 신용카드와 체크카드 비율만 바꾼 경우');

    UI.setText('saving-rate-note', '적용 공제액 ' + UI.won(r.deduction) + '의 ' + (r.effectiveSavingRate * 100).toFixed(1) +
      '%가 실제 세금 감소로 이어집니다. 한계세율 ' + (r.marginalRate * 100).toFixed(0) + '%보다 낮은 이유는, 산출세액이 줄면 근로소득세액공제(산출세액의 55%·30%)도 함께 줄기 때문입니다.');
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
  bindPreset($('credit-presets'), $('credit-card'));
  UI.onInput(['gross-salary', 'credit-card', 'debit-cash', 'dependents', 'children'], render);
  UI.year($('year'));
  render();
})();
