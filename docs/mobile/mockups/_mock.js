/* Mockup-only helper (not product code). One HTML file is both:
     - the gallery   (no ?v=)  : every <template data-v> of the page in its own phone-sized iframe,
                                 side by side, with its annotations;
     - a single screen (?v=x)  : that template alone, at the iframe's size, so the real mobile.css
                                 media queries, position:fixed and 100dvh behave as on a phone.
   Parameters: v=<variant>  dark=1  (gallery passes dark on to its frames). */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search), v = q.get('v'), dark = q.get('dark') === '1';
  var root = document.documentElement;

  var ICON = {
    today: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M4.5 12.5 14 4.5l9.5 8V23a1 1 0 0 1-1 1h-5.5v-6.5h-6V24H5.5a1 1 0 0 1-1-1z"/></svg>',
    pick: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="5.5" y="4.5" width="17" height="20" rx="3"/><path d="M10 3.5h8v3.5h-8zM9.5 15l3 3 6-6.5"/></svg>',
    pack: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M14 3.5 24 8.5v11L14 24.5 4 19.5v-11z"/><path d="M4 8.5l10 5 10-5M14 13.5v11M9 6l10 5"/></svg>',
    scanit: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M4 9V6.5A2.5 2.5 0 0 1 6.5 4H9M19 4h2.5A2.5 2.5 0 0 1 24 6.5V9M24 19v2.5a2.5 2.5 0 0 1-2.5 2.5H19M9 24H6.5A2.5 2.5 0 0 1 4 21.5V19M9 10v8M12.3 10v8M15.7 10v8M19 10v8"/></svg>',
    manage: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="14" cy="14" r="3.6"/><path d="M14 3.5v3M14 21.5v3M3.5 14h3M21.5 14h3M6.6 6.6l2.1 2.1M19.3 19.3l2.1 2.1M6.6 21.4l2.1-2.1M19.3 8.7l2.1-2.1"/></svg>',
    account: '<svg viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="14" cy="14" r="10.5"/><circle cx="14" cy="11.5" r="3.6"/><path d="M7.2 21.6c1.4-3 3.9-4.4 6.8-4.4s5.4 1.4 6.8 4.4"/></svg>'
  };
  var LABEL = { today: 'Today', pick: 'Pick', pack: 'Pack', scanit: 'Scanit', manage: 'Manage', account: 'Account' };
  var TABS = {
    worker: ['today', 'pick', 'pack', 'account'],
    manager: ['today', 'pick', 'pack', 'account'],
    cs: ['today', 'pick', 'pack', 'account'],
    host: ['today', 'scanit', 'account'],
    admin: ['today', 'pick', 'pack', 'manage', 'account']
  };
  window.MK = { ICON: ICON, LABEL: LABEL, TABS: TABS };
  MK.tabbar = function (role, on, cls) {
    return '<nav class="mk-tabbar' + (cls ? ' ' + cls : '') + '" aria-label="Native tab bar (mock)">' + TABS[role].map(function (id) {
      return '<div class="mk-tab' + (id === on ? ' on' : '') + '">' + ICON[id] + '<span>' + LABEL[id] + '</span></div>';
    }).join('') + '</nav>';
  };


  /* Small inline icons for the mock markup: <i data-ic="name"></i> is filled in screen mode. */
  var S = function (d, extra) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"' + (extra || '') + '>' + d + '</svg>'; };
  var IC = {
    chev: '<svg class="m-row__chev" viewBox="0 0 8 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 1l6 6-6 6"/></svg>',
    back: '<svg viewBox="0 0 13 21" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2 2.5 10.5 11 19"/></svg>',
    search: S('<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>'),
    barcode: S('<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 8v8M10.5 8v8M14 8v8M17 8v8"/>'),
    keyboard: S('<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><path d="M6 10h.01M9.5 10h.01M13 10h.01M16.5 10h.01M7 14h10"/>'),
    checklist: S('<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 3h6v3H9zM8.5 13l2.5 2.5 4.5-5"/>'),
    archive: S('<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 13h4"/>'),
    check: S('<path d="M5 12.5l4.5 4.5L19 7.5"/>', ' stroke-width="2.4"'),
    tag: S('<path d="M3.5 12.5V5a1.5 1.5 0 0 1 1.5-1.5h7.5L21 12l-9 9z"/><circle cx="8" cy="8" r="1.3"/>'),
    mail: S('<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m4 7.5 8 6 8-6"/>'),
    shield: S('<path d="M12 3 5 5.8v5.4c0 4.4 2.9 8 7 9.8 4.1-1.8 7-5.4 7-9.8V5.8z"/><path d="M9 12l2.2 2.2L15 10.4"/>'),
    eye: S('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>'),
    key: S('<rect x="6" y="3" width="12" height="18" rx="3"/><path d="M10 17.5h4"/>'),
    warn: S('<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.2v.01"/>')
  };
  MK.IC = IC;
  MK.fill = function (scope) {
    [].forEach.call(scope.querySelectorAll('[data-ic]'), function (el) { el.outerHTML = IC[el.getAttribute('data-ic')] || ''; });
  };

  if (dark) root.classList.add('theme-dark');
  root.classList.add(v ? 'mk-screen' : 'mk-gallery');

  document.addEventListener('DOMContentLoaded', function () {
    var tpls = [].slice.call(document.querySelectorAll('template[data-v]'));
    if (v) {
      var t = tpls.filter(function (x) { return x.getAttribute('data-v') === v; })[0];
      if (!t) { document.body.textContent = 'No such variant: ' + v; return; }
      document.body.innerHTML = '';
      document.body.appendChild(t.content.cloneNode(true));
      MK.fill(document.body);
      document.body.insertAdjacentHTML('beforeend',
        '<div class="mk-status"><span>9:41</span><i></i></div><div class="mk-island"></div>' +
        (t.getAttribute('data-role') ? MK.tabbar(t.getAttribute('data-role'), t.getAttribute('data-tab')) : '') + '<div class="mk-home"></div>');
      if (!t.getAttribute('data-role')) root.classList.add('mk-notabs');   // before sign-in there is no tab bar
      var nb = document.querySelector('.m-navbar');
      if (nb && t.hasAttribute('data-scrolled')) nb.classList.add('is-scrolled');
      return;
    }
    var wrap = document.createElement('div'); wrap.className = 'mk-wrap';
    tpls.forEach(function (t) {
      var name = t.getAttribute('data-v'), wide = t.hasAttribute('data-wide');
      var cell = document.createElement('section'); cell.className = 'mk-cell' + (wide ? ' mk-wide' : '');
      var notes = document.querySelector('ol[data-notes="' + name + '"]');
      cell.innerHTML = '<p class="mk-cap"></p><p class="mk-sub"></p>' +
        '<iframe class="mk-phone" title="" loading="eager"></iframe>';
      cell.querySelector('.mk-cap').textContent = t.getAttribute('data-title') || name;
      cell.querySelector('.mk-sub').textContent = t.getAttribute('data-sub') || '';
      var f = cell.querySelector('iframe');
      f.title = t.getAttribute('data-title') || name;
      f.style.height = (t.getAttribute('data-h') || (wide ? 768 : 844)) + 'px';
      f.src = location.pathname.split('/').pop() + '?v=' + encodeURIComponent(t.getAttribute('data-use') || name) + (dark ? '&dark=1' : '');
      if (notes) { notes.className = 'mk-notes'; cell.appendChild(notes); }
      wrap.appendChild(cell);
    });
    document.body.appendChild(wrap);
  });
})();
