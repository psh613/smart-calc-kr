/* 적립식 투자·복리 계산기 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var initialEl = $('initial');
  var monthlyEl = $('monthly');
  var rateEl = $('rate');
  var yearsEl = $('years');

  function render() {
    var r = CalcCore.computeCompound({
      initial: UI.num(initialEl),
      monthly: UI.num(monthlyEl),
      annualRatePct: UI.num(rateEl),
      years: UI.num(yearsEl),
      contributionTiming: UI.segValue($('timing-seg'), 'start')
    });

    UI.setText('final', UI.won(r.finalBalance));
    UI.setText('final-sub', r.years + '년 뒤 · 납입 ' + UI.won(r.totalPrincipal) + ' 대비 ' + UI.pct(r.returnRate));
    UI.setText('principal', UI.won(r.totalPrincipal));
    UI.setText('profit', UI.won(r.totalProfit));
    UI.setText('return-rate', UI.pct(r.returnRate));
    UI.setText('multiple', (r.totalPrincipal > 0 ? (r.finalBalance / r.totalPrincipal).toFixed(2) : '0.00') + '배');

    var rows = r.rows.map(function (row) {
      return '<tr><td>' + row.year + '년</td><td>' + UI.won(row.principal) + '</td><td>' + UI.won(row.balance) + '</td><td>' + UI.won(row.gain) + '</td></tr>';
    }).join('');
    UI.setHtml('year-rows', rows);

    markPresets($('monthly-presets'), UI.num(monthlyEl));
    markPresets($('years-presets'), UI.num(yearsEl));
  }

  function markPresets(container, value) {
    if (!container) return;
    Array.prototype.forEach.call(container.querySelectorAll('button'), function (btn) {
      btn.setAttribute('aria-pressed', Number(btn.getAttribute('data-value')) === value ? 'true' : 'false');
    });
  }

  function bindPresets(container, input) {
    if (!container) return;
    container.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-value]');
      if (!btn) return;
      input.value = btn.getAttribute('data-value');
      render();
    });
  }

  bindPresets($('monthly-presets'), monthlyEl);
  bindPresets($('years-presets'), yearsEl);
  UI.bindSegmented($('timing-seg'), render);
  UI.onInput(['initial', 'monthly', 'rate', 'years'], render);
  UI.year($('year'));
  render();
})();
