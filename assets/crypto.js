/* 코인 물타기·선물 청산가 계산기 — 화면 렌더링 */
(function () {
  'use strict';
  var $ = UI.$;
  var currency = 'krw';
  var fx = UI.getFx();

  var PRICE_IDS = ['avg-price', 'add-price', 'cur-price', 'target-price', 'entry', 'fut-target'];
  var MONEY_IDS = ['add-amount', 'margin'];
  var UNIT_IDS = { 'cur1': 'price', 'cur2': 'money', 'cur3': 'price', 'cur4': 'price', 'cur5': 'price', 'cur6': 'price', 'cur7': 'money', 'cur8': 'price' };

  function money(v) { return currency === 'krw' ? UI.int(v) + '원' : UI.usd(v, 2); }
  function priceText(v) { return UI.price(v, currency); }
  function otherMoney(v) { return currency === 'krw' ? UI.usd(v, 2) : UI.int(v) + '원'; }
  function otherPrice(v) { return currency === 'krw' ? UI.usd(v, Math.abs(v) < 1 ? 6 : 2) : UI.int(v) + '원'; }
  function qtyText(v) {
    var n = Number(v) || 0;
    if (n === 0) return '0';
    if (Math.abs(n) >= 1) return UI.dec(n, Math.abs(n) % 1 === 0 ? 0 : 4);
    return String(Number(n.toPrecision(6)));
  }

  function refreshUnits() {
    Object.keys(UNIT_IDS).forEach(function (id) {
      var el = $(id);
      if (!el) return;
      if (currency === 'krw') el.textContent = '원';
      else el.textContent = '$';
    });
  }

  function updateFx() {
    var v = UI.num($('fx'));
    if (v > 0) {
      fx = v;
      UI.setFx(v);
    } else {
      fx = UI.getFx();
    }
    render();
  }

  function switchCurrency(next) {
    if (next === currency) return;
    var factor = next === 'usd' ? 1 / fx : fx;
    PRICE_IDS.concat(MONEY_IDS).forEach(function (id) {
      var el = $(id);
      if (!el) return;
      var v = UI.num(el);
      if (v === 0) return;
      var converted = v * factor;
      var digits = next === 'usd' ? 2 : 0;
      el.value = String(Number(converted.toFixed(digits)));
    });
    currency = next;
    refreshUnits();
    render();
  }

  function renderAverage() {
    var mode = UI.segValue($('add-mode'), 'amount');
    $('add-amount-field').hidden = mode !== 'amount';
    $('add-qty-field').hidden = mode !== 'qty';
    $('add-amount-field').style.display = mode === 'amount' ? '' : 'none';
    $('add-qty-field').style.display = mode === 'qty' ? '' : 'none';

    var avgPrice = UI.num($('avg-price'));
    var qty = UI.num($('qty'));
    var addPrice = UI.num($('add-price'));
    var addQty = mode === 'qty' ? UI.num($('add-qty')) : (addPrice > 0 ? UI.num($('add-amount')) / addPrice : 0);
    var currentPrice = UI.num($('cur-price'));

    var r = CalcCore.computeAverage({
      qty: qty, avgPrice: avgPrice, addQty: addQty, addPrice: addPrice, currentPrice: currentPrice
    });

    if (!(r.totalQty > 0)) {
      UI.setText('avg-result', '—');
      UI.setText('avg-sub', '수량과 가격을 입력하세요');
      UI.setText('total-qty', '—');
      UI.setText('total-cost', '—');
      UI.setText('target-return', '—');
      UI.setText('unrealized', '—');
      UI.setHtml('avg-rows', '');
      return;
    }

    UI.setText('avg-result', priceText(r.newAvgPrice));
    var sub = '기존 평단가 대비 ' + UI.pct(r.avgChange);
    if (r.breakEvenFromCurrent !== null) sub += ' · 현재가에서 ' + UI.pct(r.breakEvenFromCurrent) + ' 오르면 본전';
    UI.setText('avg-sub', sub + ' · ' + otherPrice(r.newAvgPrice));

    UI.setText('total-qty', qtyText(r.totalQty) + '개');
    UI.setText('total-cost', money(r.totalCost) + ' / ' + otherMoney(r.totalCost));

    var target = UI.num($('target-price'));
    if (target > 0) {
      var tr = target / r.newAvgPrice - 1;
      var profit = (target - r.newAvgPrice) * r.totalQty;
      UI.setText('target-return', UI.pct(tr) + ' (' + money(profit) + ')');
    } else {
      UI.setText('target-return', '목표가 입력');
    }

    if (currentPrice > 0) {
      UI.setText('unrealized', UI.pct(r.unrealizedRate) + ' · ' + money(r.unrealizedPnl));
    } else {
      UI.setText('unrealized', '현재가 입력');
    }

    var rows = [
      ['기존 보유', money(r.oldCost), qtyText(r.oldQty) + '개'],
      ['추가 매수', money(r.addCost), qtyText(r.addQty) + '개'],
      ['합계 (새 평단)', money(r.totalCost), qtyText(r.totalQty) + '개']
    ];
    UI.setHtml('avg-rows', rows.map(function (row, i) {
      var cls = i === rows.length - 1 ? ' class="total"' : '';
      return '<tr' + cls + '><td>' + row[0] + '</td><td>' + row[1] + '</td><td>' + row[2] + '</td></tr>';
    }).join(''));
  }

  function renderFutures() {
    var side = UI.segValue($('side-seg'), 'long');
    var entry = UI.num($('entry'));
    var leverage = UI.num($('leverage'));
    var mmr = UI.num($('mmr'));
    var margin = UI.num($('margin'));
    var target = UI.num($('fut-target'));

    var f = CalcCore.computeFutures({
      side: side, entry: entry, leverage: leverage, maintenanceMarginPct: mmr, margin: margin, targetPrice: target
    });

    if (!(entry > 0)) {
      UI.setText('liq-result', '—');
      UI.setText('liq-sub', '진입가를 입력하세요');
      UI.setText('position-size', '—');
      UI.setText('fut-qty', '—');
      UI.setText('roi-target', '—');
      UI.setText('pnl-target', '—');
      UI.setHtml('lev-rows', '');
      return;
    }

    UI.setText('liq-result', priceText(f.liquidationPrice));
    UI.setText('liq-sub', (side === 'long' ? '롱' : '숏') + ' ' + f.leverage + '배 · 진입가 대비 ' + UI.pct(f.liquidationDistance) + ' · ' + otherPrice(f.liquidationPrice));

    UI.setText('position-size', margin > 0 ? money(f.positionSize) : '증거금 입력');
    UI.setText('fut-qty', f.qty > 0 ? qtyText(f.qty) + '개' : '—');

    if (target > 0) {
      UI.setText('roi-target', UI.pct(f.roiAtTarget));
      UI.setText('pnl-target', margin > 0 ? money(f.pnlAtTarget) : '증거금 입력');
    } else {
      UI.setText('roi-target', '목표가 입력');
      UI.setText('pnl-target', '—');
    }

    var levels = [2, 3, 5, 10, 20, 25, 50, 100];
    var rows = levels.map(function (l) {
      var item = CalcCore.computeFutures({ side: side, entry: entry, leverage: l, maintenanceMarginPct: mmr });
      var cls = l === f.leverage ? ' class="total"' : '';
      return '<tr' + cls + '><td>' + l + '배</td><td>' + priceText(item.liquidationPrice) + '</td><td>' + UI.pct(item.liquidationDistance) + '</td></tr>';
    }).join('');
    UI.setHtml('lev-rows', rows);
  }

  function render() { renderAverage(); renderFutures(); }

  // 환율 초기화
  var fxEl = $('fx');
  if (fxEl) fxEl.value = String(fx);

  UI.bindSegmented($('currency-seg'), switchCurrency);
  UI.bindSegmented($('add-mode'), render);
  UI.bindSegmented($('side-seg'), render);
  UI.onInput(['avg-price', 'qty', 'add-amount', 'add-qty', 'add-price', 'cur-price', 'target-price', 'entry', 'leverage', 'mmr', 'margin', 'fut-target'], render);
  if (fxEl) { fxEl.addEventListener('input', updateFx); fxEl.addEventListener('change', updateFx); }
  UI.year($('year'));
  refreshUnits();
  render();
})();
