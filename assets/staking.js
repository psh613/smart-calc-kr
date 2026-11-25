/* 업비트 스테이킹 실수령 수익 · 언스테이킹 손익분기 시뮬레이터 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var PERIODS = [1, 3, 6, 12, 24];
  var DROPS = [0, 5, 10, 15, 20, 30];

  function numOr(id, fallback) {
    var el = $(id);
    if (!el) return fallback;
    var raw = String(el.value === null || el.value === undefined ? '' : el.value).replace(/[^0-9.\-]/g, '');
    if (raw === '' || raw === '-' || raw === '.') return fallback;
    var n = Number(raw);
    return isFinite(n) ? n : fallback;
  }

  function currentAsset() {
    return CalcCore.stakingAsset(UI.segValue($('coin-chips'), 'ATOM'));
  }

  function readInputs() {
    var a = currentAsset();
    return {
      assetKey: a.key,
      amount: numOr('amount', 1000000),
      price: numOr('price', a.price),
      aprPct: numOr('apr', a.apr * 100),
      months: numOr('months', 12),
      unstakeDays: numOr('unstake-days', a.unstakeDays),
      expectedDropPct: numOr('drop', 10)
    };
  }

  function qtyText(v, ticker) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    var d = Math.abs(n) >= 1000 ? 2 : (Math.abs(n) >= 1 ? 4 : (Math.abs(n) >= 0.01 ? 6 : 8));
    return UI.dec(n, d) + ' ' + ticker;
  }

  function pctText(v, d) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    return (n * 100).toFixed(typeof d === 'number' ? d : 1) + '%';
  }

  function signWon(v) {
    var n = Number(v) || 0;
    return (n > 0 ? '+' : (n < 0 ? '−' : '')) + UI.won(Math.abs(n));
  }

  function coinLabel(a) { return a.name + '(' + a.ticker + ')'; }

  function waitText(days) {
    var d = Number(days);
    if (!isFinite(d) || d <= 0) return '즉시';
    if (d < 1) return Math.round(d * 24) + '시간';
    return UI.dec(d, d % 1 === 0 ? 0 : 1) + '일';
  }

  function perDayText(r) {
    if (!(r.unstakeDays >= 1)) return '—<span class="subnote">대기 ' + waitText(r.unstakeDays) + '</span>';
    return pctText(r.dailyAllowance, 2);
  }

  function render() {
    var input = readInputs();
    var a = currentAsset();
    var r = CalcCore.computeStaking(input);
    var ticker = r.ticker;

    /* ── 결과 카드 ── */
    var big = pctText(r.breakEvenDrop, 1);
    UI.setHtml('breakeven', big.replace('%', '<small>%</small>'));
    UI.setText('breakeven-sub', coinLabel(a) + ' ' + r.months + '개월 스테이킹 · 실수령 보상 ' +
      UI.won(r.netRewardKrw) + '(' + pctText(r.periodReturn, 2) + ') · 언스테이킹 ' +
      waitText(r.unstakeDays) + ' 대기 중 시세가 이보다 더 빠지면 보상이 상쇄됩니다');
    UI.setText('reward', UI.won(r.netRewardKrw));
    UI.setText('fee', UI.won(r.feeKrw));
    UI.setText('eff-annual', pctText(r.effAnnual, 2));
    UI.setText('net-pnl', signWon(r.netPnlKrw));

    /* ── 계산 상세 ── */
    var rows = [
      '<tr><td>스테이킹 수량</td><td>' + qtyText(r.qty, ticker) +
        '<span class="subnote">' + UI.won(r.amount) + ' ÷ ' + UI.won(r.price) + '</span></td></tr>',
      '<tr><td>연 추정 보상률</td><td>' + pctText(r.apr, 2) +
        '<span class="subnote">수수료 공제 후 · ' + r.cycleDays + '일마다 보상 분배(복리)</span></td></tr>',
      '<tr><td>보상이 붙는 기간</td><td>' + r.days + '일 중 ' + r.rewardDays + '일' +
        (r.firstRewardDelayDays > 0 ? '<span class="subnote">첫 보상까지 약 ' + r.firstRewardDelayDays + '일</span>' : '') +
        '</td></tr>',
      '<tr><td>수수료 전 보상</td><td>' + qtyText(r.grossRewardQty, ticker) +
        '<span class="subnote">' + UI.won(r.grossRewardKrw) + '</span></td></tr>',
      '<tr><td>검증 수수료 10%</td><td>' + qtyText(r.feeQty, ticker) +
        '<span class="subnote">' + UI.won(r.feeKrw) + '</span></td></tr>',
      '<tr><td>실수령 보상</td><td>' + qtyText(r.netRewardQty, ticker) +
        '<span class="subnote">' + UI.won(r.netRewardKrw) + ' · 보상 수량 기준</span></td></tr>',
      '<tr><td>복리 효과</td><td>' + qtyText(r.netRewardQty - r.simpleRewardQty, ticker) +
        '<span class="subnote">단리 ' + qtyText(r.simpleRewardQty, ticker) + ' 대비</span></td></tr>',
      '<tr><td>스테이킹 / 언스테이킹 대기</td><td>' + waitText(r.stakeWaitDays) + ' / ' +
        waitText(r.unstakeDays) +
        '<span class="subnote">대기 중에는 보상이 없고 취소도 안 됩니다</span></td></tr>',
      '<tr class="total"><td>손익분기 시세 하락률</td><td>' + pctText(r.breakEvenDrop, 2) +
        '<span class="subnote">해제 시점 시세 ' + UI.won(r.breakEvenPrice) + '까지 허용</span></td></tr>'
    ];
    UI.setHtml('detail-rows', rows.join(''));

    /* ── 종목별 비교 ── */
    var assetRows = CalcCore.STAKING2026.assets.map(function (asset) {
      var s = CalcCore.computeStaking({
        assetKey: asset.key,
        amount: r.amount,
        months: r.months,
        expectedDropPct: r.expectedDropPct
      });
      return '<tr><td>' + asset.name + '<span class="subnote">' + asset.ticker + ' · 최소 ' +
        (asset.minQty === null ? '화면 확인' : UI.dec(asset.minQty, asset.minQty < 1 ? 2 : 0)) + '</span></td>' +
        '<td>' + pctText(asset.apr, 2) + '</td>' +
        '<td>' + waitText(asset.unstakeDays) + '</td>' +
        '<td>' + UI.won(s.netRewardKrw) + '</td>' +
        '<td>' + pctText(s.breakEvenDrop, 2) + '</td>' +
        '<td>' + perDayText(s) + '</td></tr>';
    }).join('');
    UI.setHtml('asset-rows', assetRows);
    UI.setText('asset-caption', UI.won(r.amount) + ' · ' + r.months + '개월 · 시세는 바꾸지 않고 보상률만 각 종목 값으로 계산');

    /* ── 기간별 ── */
    var periodRows = PERIODS.map(function (m) {
      var s = CalcCore.computeStaking({
        assetKey: r.assetKey, amount: r.amount, price: r.price, aprPct: r.aprPct,
        months: m, unstakeDays: r.unstakeDays, expectedDropPct: r.expectedDropPct
      });
      return '<tr><td>' + m + '개월</td><td>' + UI.won(s.netRewardKrw) + '</td><td>' +
        pctText(s.periodReturn, 2) + '</td><td>' + pctText(s.breakEvenDrop, 2) + '</td><td>' +
        perDayText(s) + '</td></tr>';
    }).join('');
    UI.setHtml('period-rows', periodRows);
    UI.setText('period-caption', ticker + ' 연 ' + pctText(r.apr, 2) + ' · ' + waitText(r.unstakeDays) + ' 대기 기준');

    /* ── 시세 하락 시나리오 ── */
    var dropRows = DROPS.map(function (d) {
      var s = CalcCore.computeStaking({
        assetKey: r.assetKey, amount: r.amount, price: r.price, aprPct: r.aprPct,
        months: r.months, unstakeDays: r.unstakeDays, expectedDropPct: d
      });
      var verdict = s.netPnlKrw > 0 ? '보상이 방어' : (s.netPnlKrw < 0 ? '원금 손실' : '본전');
      return '<tr><td>−' + d + '%</td><td>' + UI.won(s.endPrice) + '</td><td>' + UI.won(s.valueAtExit) +
        '</td><td>' + signWon(s.netPnlKrw) + '<span class="subnote">' + pctText(s.netPnlRate, 2) +
        '</span></td><td>' + verdict + '</td></tr>';
    }).join('');
    UI.setHtml('drop-rows', dropRows);
    UI.setText('drop-caption', '대기 중 시세가 ' + pctText(r.breakEvenDrop, 1) + ' 넘게 빠지면 보상보다 시세 손실이 커집니다');

    /* ── 안내 문구 ── */
    var minNote;
    if (r.price <= 0) {
      minNote = '현재가를 1원 이상 입력해야 수량을 계산할 수 있습니다.';
    } else if (r.minQty === null) {
      minNote = '에이다는 공개된 1차 출처에서 최소 신청 수량을 확인하지 못했습니다. 신청 화면에서 최소 수량을 확인한 뒤 입력하세요.';
    } else if (r.minQtyOk) {
      minNote = '업비트 최소 신청 수량 ' + UI.dec(r.minQty, r.minQty < 1 ? 2 : 0) + ' ' + ticker +
        '(약 ' + UI.won(r.minAmount) + ') 이상이라 조건을 채웁니다.';
    } else {
      minNote = '업비트 최소 신청 수량 ' + UI.dec(r.minQty, r.minQty < 1 ? 2 : 0) + ' ' + ticker +
        '(약 ' + UI.won(r.minAmount) + ')보다 적습니다. 이 수량으로는 신청이 되지 않습니다.';
    }
    UI.setText('min-note', minNote);

    UI.setText('break-even-note', r.periodReturn > 0
      ? r.months + '개월 동안 수량이 ' + pctText(r.periodReturn, 2) + ' 늘어난다고 보고 계산했습니다. ' +
        '해제를 신청하고 ' + waitText(r.unstakeDays) + '을 기다리는 사이 시세가 ' +
        pctText(r.breakEvenDrop, 2) + '(' + UI.won(r.price - r.breakEvenPrice) + ') 넘게 빠지면, ' +
        '스테이킹 보상으로 번 것보다 코인 가격이 떨어진 손실이 커집니다.'
      : '보상률이 0이라 손익분기 하락률도 0입니다. 연 추정 보상률을 입력하세요.');

    UI.setText('eff-note', '1년 중 보상이 붙는 날은 ' + UI.dec(r.effDays, 0) + '일(365 − 스테이킹 대기 ' +
      waitText(r.stakeWaitDays) + ' − 언스테이킹 대기 ' +
      waitText(r.unstakeDays) + ')입니다. 이걸 반영한 1년 실효 보상률이 ' +
      pctText(r.effAnnual, 2) + '이고, 표시된 ' + pctText(r.apr, 2) + '는 대기를 빼지 않은 값입니다.');

    UI.setText('fee-note', '업비트가 화면에 보여 주는 연 추정 보상률은 이미 수수료를 뗀 뒤의 값입니다. ' +
      '그래서 수수료 전 보상은 실수령 보상의 10/9배(위 표의 ' + UI.won(r.feeKrw) + '만큼 더)이며, ' +
      '수수료를 뗀 뒤 실제로 쌓이는 양이 실수령 보상입니다.');
  }

  function applyAssetDefaults() {
    var a = currentAsset();
    var price = $('price');
    var apr = $('apr');
    var days = $('unstake-days');
    if (price) price.value = a.price;
    if (apr) apr.value = a.apr * 100;
    if (days) days.value = a.unstakeDays < 1 ? Number(a.unstakeDays.toFixed(3)) : a.unstakeDays;
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

  var chips = $('coin-chips');
  if (chips) {
    UI.bindSegmented(chips, function () {
      applyAssetDefaults();
      render();
    });
  }
  bindPreset($('amount-presets'), $('amount'));
  UI.onInput(['amount', 'price', 'apr', 'months', 'unstake-days', 'drop'], render);
  UI.year($('year'));
  render();
})();
