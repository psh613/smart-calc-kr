/* smart-calc-kr — 화면 공용 유틸 (숫자 포맷, 환율, 입력 바인딩) */
(function (root) {
  'use strict';

  var FX_KEY = 'smartcalc.fx';
  var FX_DEFAULT = 1400;

  function $(id) { return document.getElementById(id); }

  function num(el) {
    if (el === null || el === undefined) return 0;
    var raw = typeof el === 'object' ? el.value : el;
    if (raw === null || raw === undefined) return 0;
    var n = Number(String(raw).replace(/[^0-9.\-]/g, ''));
    return isFinite(n) ? n : 0;
  }

  /** 1234567 → "1,234,567" (Intl 없이도 동일하게 동작) */
  function group(str) {
    var parts = String(str).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return parts.join('.');
  }

  function int(v) {
    var n = Number(v);
    if (!isFinite(n)) return '0';
    n = Math.round(n);
    return (n < 0 ? '-' : '') + group(Math.abs(n));
  }

  /** 소수 자릿수를 유지하면서 천 단위 구분 (decimals 생략 시 자동) */
  function dec(v, digits) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    var d = typeof digits === 'number' ? digits : (Math.abs(n) < 1 ? 4 : 2);
    var fixed = Math.abs(n).toFixed(d);
    return (n < 0 ? '-' : '') + group(fixed);
  }

  function won(v) { return int(v) + '원'; }

  function usd(v, digits) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    var d = typeof digits === 'number' ? digits : (Math.abs(n) < 1 ? 4 : 2);
    return '$' + dec(n, d);
  }

  function price(v, currency) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    if (currency === 'usd') return usd(n, Math.abs(n) < 1 ? 6 : 2);
    return int(n) + '원';
  }

  function pct(v, digits) {
    var n = Number(v);
    if (!isFinite(n)) n = 0;
    var d = typeof digits === 'number' ? digits : 2;
    return (n > 0 ? '+' : '') + (n * 100).toFixed(d) + '%';
  }

  function getFx() {
    try {
      var saved = parseFloat(localStorage.getItem(FX_KEY));
      return isFinite(saved) && saved > 0 ? saved : FX_DEFAULT;
    } catch (e) { return FX_DEFAULT; }
  }
  function setFx(v) {
    try { localStorage.setItem(FX_KEY, String(v)); } catch (e) {}
  }

  /** 입력 요소의 값이 바뀔 때마다 fn 실행 (input/change 모두) */
  function onInput(ids, fn) {
    ids.forEach(function (id) {
      var el = $(id);
      if (!el) return;
      el.addEventListener('input', fn);
      el.addEventListener('change', fn);
    });
  }

  /** 세그먼트 버튼(aria-pressed) 그룹 */
  function bindSegmented(container, onChange) {
    if (!container) return;
    var buttons = Array.prototype.slice.call(container.querySelectorAll('button'));
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        buttons.forEach(function (b) { b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
        if (typeof onChange === 'function') onChange(btn.getAttribute('data-value'));
      });
    });
  }

  function segValue(container, fallback) {
    if (!container) return fallback;
    var active = container.querySelector('button[aria-pressed="true"]');
    return active ? active.getAttribute('data-value') : fallback;
  }

  function setText(id, text) {
    var el = $(id);
    if (el) el.textContent = text;
  }

  function setHtml(id, html) {
    var el = $(id);
    if (el) el.innerHTML = html;
  }

  function setSignClass(id, value) {
    var el = $(id);
    if (!el) return;
    el.classList.remove('up', 'down');
    if (value > 0) el.classList.add('up');
    else if (value < 0) el.classList.add('down');
  }

  function year(el) {
    if (el) el.textContent = new Date().getFullYear();
  }

  /** 숫자 입력에 천 단위 콤마를 자동으로 넣는다(포커스 해제 시) */
  function commaOnBlur(el) {
    if (!el) return;
    el.addEventListener('blur', function () {
      var n = num(el);
      if (String(el.value).trim() !== '' && isFinite(n)) el.value = n.toLocaleString('en-US', { maximumFractionDigits: 2 });
    });
    el.addEventListener('focus', function () {
      el.value = String(el.value).replace(/,/g, '');
    });
  }

  root.UI = {
    $: $, num: num, int: int, dec: dec, won: won, usd: usd, price: price, pct: pct,
    getFx: getFx, setFx: setFx, onInput: onInput,
    bindSegmented: bindSegmented, segValue: segValue,
    setText: setText, setHtml: setHtml, setSignClass: setSignClass,
    year: year, commaOnBlur: commaOnBlur
  };
})(typeof window !== 'undefined' ? window : this);
