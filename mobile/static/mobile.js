/* Shared runtime for the /m/ mobile screens (plain ES5, no build step).
   window.M: api · toast · haptic · sheets · confirm · askCode · scanning · language.

   Scanning has three sources, all delivered to the ONE handler a screen registers
   with M.onScan(fn):
     1. A Bluetooth / USB scanner. It pairs as a keyboard: it "types" the barcode and
        presses Enter. We catch those keystrokes at document level, so a scan works at
        any moment without tapping a field first.
     2. The iPhone/iPad camera, through the native app (LOHubNative.scan()).
     3. Typing the code by hand (M.askCode sheet). */
(function () {
  'use strict';
  var M = window.M = {};
  var doc = document, root = doc.documentElement;

  M.native = window.LOHubNative || null;
  M.inApp = !!M.native || /LiveOpsHubiOS/.test(navigator.userAgent);
  if (M.inApp) root.classList.add('lohub-ios');

  // ── Theme: follows the device in the app; light in a browser unless chosen ──
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  M.ls = ls; M.lsSet = lsSet;
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function applyTheme() {
    var mode = ls('lohubMode') || (M.inApp ? 'system' : 'light');
    var dark = mode === 'dark' || (mode === 'system' && mq && mq.matches);
    root.classList.toggle('theme-dark', !!dark);
  }
  applyTheme();
  if (mq) { if (mq.addEventListener) mq.addEventListener('change', applyTheme); else if (mq.addListener) mq.addListener(applyTheme); }

  // ── Language (same localStorage key as the desktop screens) ──
  M.lang = ls('lang') === 'es' ? 'es' : 'en';
  root.lang = M.lang;
  M.setLang = function (l) { lsSet('lang', l); location.reload(); };
  M.strings = { en: {}, es: {} };
  M.t = function (k) {
    var s = (M.strings[M.lang] && M.strings[M.lang][k]);
    if (s == null) s = M.strings.en[k];
    return s == null ? k : s;
  };
  M.applyI18n = function (scope) {
    var els = (scope || doc).querySelectorAll('[data-t]');
    for (var i = 0; i < els.length; i++) els[i].textContent = M.t(els[i].getAttribute('data-t'));
    els = (scope || doc).querySelectorAll('[data-t-label]');
    for (i = 0; i < els.length; i++) els[i].setAttribute('aria-label', M.t(els[i].getAttribute('data-t-label')));
    els = (scope || doc).querySelectorAll('[data-t-ph]');
    for (i = 0; i < els.length; i++) els[i].setAttribute('placeholder', M.t(els[i].getAttribute('data-t-ph')));
  };

  M.esc = function (s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };

  // ── API ──
  // Same-origin JSON. The server's CSRF shim (injected into every HTML page) adds the
  // token header to POSTs. A lost session comes back as a redirect to the sign-in page
  // (HTML, not JSON): send the user there instead of showing a broken screen.
  M.api = function (path, opts) {
    opts = opts || {};
    var init = { method: opts.method || 'GET', credentials: 'same-origin', headers: { 'Accept': 'application/json' } };
    if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
    return fetch(path, init).then(function (r) {
      var ct = r.headers.get('Content-Type') || '';
      if (r.status === 401 || (r.ok && ct.indexOf('application/json') < 0)) {
        location.href = '/';
        throw new Error('signed_out');
      }
      if (ct.indexOf('application/json') < 0) throw new Error(r.status === 403 ? 'forbidden' : 'HTTP ' + r.status);
      return r.json().then(function (d) {
        if (r.status === 402 && d && d.error === 'billing') { location.href = '/billing'; throw new Error('billing'); }
        return d;
      });
    });
  };

  // ── Haptics (native app only; silent elsewhere) ──
  M.haptic = function (style) { try { if (M.native && M.native.haptic) M.native.haptic(style || 'tap'); } catch (e) {} };

  // ── Toast ──
  var toastEl, toastTimer;
  var ICON_OK = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  var ICON_ERR = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5.5M12 16.5v.01"/></svg>';
  M.toast = function (msg, kind) {
    if (!toastEl) { toastEl = doc.createElement('div'); toastEl.className = 'm-toast'; toastEl.setAttribute('role', 'status'); doc.body.appendChild(toastEl); }
    toastEl.className = 'm-toast' + (kind ? ' m-toast--' + kind : '');
    toastEl.innerHTML = (kind === 'success' ? ICON_OK : kind === 'error' ? ICON_ERR : '') + '<span>' + M.esc(msg) + '</span>';
    void toastEl.offsetWidth;
    toastEl.classList.add('is-shown');
    if (kind === 'success') M.haptic('success'); else if (kind === 'error') M.haptic('error');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('is-shown'); }, kind === 'error' ? 3500 : 2500);
  };

  M.hideToast = function () { clearTimeout(toastTimer); if (toastEl) toastEl.classList.remove('is-shown'); };

  // ── Sheets ──
  var backdrop, openSheet = null, onDismiss = null;
  function ensureBackdrop() {
    if (backdrop) return;
    backdrop = doc.createElement('div'); backdrop.className = 'm-sheet__backdrop';
    backdrop.addEventListener('click', function () { M.closeSheet(true); });
    doc.body.appendChild(backdrop);
  }
  M.openSheet = function (el, dismissed) {
    ensureBackdrop();
    if (openSheet && openSheet !== el) M.closeSheet(true);
    openSheet = el; onDismiss = dismissed || null;
    el.hidden = false; void el.offsetWidth;
    el.classList.add('is-open'); backdrop.classList.add('is-open'); doc.body.classList.add('m-locked');
  };
  M.closeSheet = function (dismissed) {
    if (!openSheet) return;
    var el = openSheet, cb = onDismiss; openSheet = null; onDismiss = null;
    el.classList.remove('is-open'); backdrop.classList.remove('is-open'); doc.body.classList.remove('m-locked');
    if (doc.activeElement && doc.activeElement.blur) doc.activeElement.blur();
    setTimeout(function () { if (openSheet !== el) el.hidden = true; }, 340);
    if (dismissed && cb) cb();
  };
  M.sheetIsOpen = function () { return !!openSheet; };

  // Confirm — replaces window.confirm() with a bottom sheet. Resolves true/false.
  var confirmEl;
  M.confirm = function (o) {
    if (!confirmEl) {
      confirmEl = doc.createElement('div'); confirmEl.className = 'm-sheet'; confirmEl.hidden = true;
      confirmEl.setAttribute('role', 'dialog'); confirmEl.setAttribute('aria-modal', 'true');
      confirmEl.innerHTML = '<div class="m-sheet__grabber"></div><div class="m-sheet__title"></div><div class="m-sheet__body"></div>' +
        '<div class="m-sheet__actions"><button type="button" class="m-btn m-btn--lg m-btn--secondary" data-a="no"></button>' +
        '<button type="button" class="m-btn m-btn--lg m-btn--primary" data-a="yes"></button></div>';
      doc.body.appendChild(confirmEl);
    }
    return new Promise(function (resolve) {
      confirmEl.querySelector('.m-sheet__title').textContent = o.title || '';
      var b = confirmEl.querySelector('.m-sheet__body'); b.textContent = o.body || ''; b.hidden = !o.body;
      var no = confirmEl.querySelector('[data-a=no]'), yes = confirmEl.querySelector('[data-a=yes]');
      no.textContent = o.cancel || M.t('cancel'); yes.textContent = o.ok || 'OK';
      yes.className = 'm-btn m-btn--lg ' + (o.destructive ? 'm-btn--destructive' : 'm-btn--primary');
      no.onclick = function () { M.closeSheet(); resolve(false); };
      yes.onclick = function () { M.closeSheet(); resolve(true); };
      M.openSheet(confirmEl, function () { resolve(false); });
    });
  };

  // Type a code by hand. Resolves the trimmed text, or null if dismissed.
  var codeEl;
  M.askCode = function (o) {
    o = o || {};
    if (!codeEl) {
      codeEl = doc.createElement('div'); codeEl.className = 'm-sheet'; codeEl.hidden = true;
      codeEl.setAttribute('role', 'dialog'); codeEl.setAttribute('aria-modal', 'true');
      codeEl.innerHTML = '<div class="m-sheet__grabber"></div><div class="m-sheet__title"></div>' +
        '<form><label class="m-field"><span class="m-field__label"></span><span class="m-field__control">' +
        '<input type="text" name="code" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false" enterkeyhint="go"></span></label>' +
        '<button type="submit" class="m-btn m-btn--lg m-btn--primary"></button></form>';
      doc.body.appendChild(codeEl);
    }
    return new Promise(function (resolve) {
      var input = codeEl.querySelector('input'), form = codeEl.querySelector('form');
      codeEl.querySelector('.m-sheet__title').textContent = o.title || '';
      codeEl.querySelector('.m-field__label').textContent = o.label || '';
      codeEl.querySelector('button[type=submit]').textContent = o.button || 'OK';
      input.value = '';
      form.onsubmit = function (e) {
        e.preventDefault();
        var v = input.value.trim(); if (!v) return;
        M.closeSheet(); resolve(v);
      };
      M.openSheet(codeEl, function () { resolve(null); });
      setTimeout(function () { try { input.focus(); } catch (e) {} }, 60);
    });
  };

  // ── Scanning ──
  var scanHandler = null;
  M.onScan = function (fn) { scanHandler = fn; };
  function deliver(code, source) {
    code = String(code || '').replace(/[\r\n\t]/g, '').trim();
    if (!code || !scanHandler) return;
    scanHandler(code, source);
  }
  /* Camera in the app; otherwise the type-it sheet. `ask` = options for M.askCode. */
  M.scan = function (ask) {
    if (M.native && M.native.scan) {
      M.native.scan().then(function (code) { if (code) deliver(code, 'camera'); });
    } else {
      M.askCode(ask).then(function (code) { if (code) deliver(code, 'typed'); });
    }
  };
  M.typeCode = function (ask) { M.askCode(ask).then(function (code) { if (code) deliver(code, 'typed'); }); };

  /* Bluetooth / USB scanner (keyboard wedge).
     While no text field is focused, every printable key is buffered and Enter (or Tab)
     ends the scan. A pause longer than SCAN_GAP_MS starts a new buffer, so a stray key
     can't glue itself onto the next barcode. When a field IS focused (the type-it
     sheet, the problem note) the keys belong to that field and are left alone. */
  var SCAN_GAP_MS = 600, SCAN_MIN_LEN = 4;
  var buf = '', lastKey = 0;
  M.scannerSeen = ls('lohubScanner') === '1';
  function isEditing() {
    var el = doc.activeElement;
    if (!el || el === doc.body) return false;
    var tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  }
  doc.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;
    if (isEditing()) { buf = ''; return; }
    var now = Date.now();
    if (now - lastKey > SCAN_GAP_MS) buf = '';
    lastKey = now;
    if (e.key === 'Enter' || e.key === 'Tab') {
      if (buf.length >= SCAN_MIN_LEN) {
        e.preventDefault(); e.stopPropagation();       // never "click" a focused button
        var code = buf; buf = '';
        if (!M.scannerSeen) { M.scannerSeen = true; lsSet('lohubScanner', '1'); }
        deliver(code, 'scanner');
      } else { buf = ''; }
      return;
    }
    if (e.key && e.key.length === 1) {
      buf += e.key;
      e.preventDefault();                              // no page scroll on Space, no button activation
    }
  }, true);
  // A tapped button keeps focus; drop it so a scanner's Enter can't re-press it.
  doc.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('button,a,[role=button]') : null;
    if (el && el.blur) setTimeout(function () { el.blur(); }, 0);
  }, true);

  // ── Nav bar: material background once the large title scrolls under it ──
  function onScroll() {
    var nb = doc.querySelectorAll('.m-navbar');
    for (var i = 0; i < nb.length; i++) nb[i].classList.toggle('is-scrolled', window.scrollY > 36);
  }
  window.addEventListener('scroll', onScroll, { passive: true });

  M.online = function () { return navigator.onLine !== false; };
})();
