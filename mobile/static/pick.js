/* /m/pick — mobile Pick screen.
   Same flow and the same server calls as the desktop /pick screen (templates.py
   PICK_HTML): choose a show -> scan a packing label -> tick items -> done.
   Every rule (cancelled order, cancelled items still on the table, new-show table
   clean-out, already picked) is decided by the server and only displayed here. */
(function () {
  'use strict';
  var M = window.M, $ = function (id) { return document.getElementById(id); };
  var esc = M.esc;

  M.strings.en = {
    pick: 'Pick', home: 'Home', myprofile: 'My profile', cancel: 'Cancel', retry: 'Retry',
    offline: "You're offline. Reconnect to keep picking.", loaderr: "Couldn't load shows",
    orderswaiting: 'orders waiting', orderwaiting: 'order waiting',
    yourepicking: "You're picking", lefttopick: 'left to pick', picked: 'picked', issue: 'issue', issues: 'issues',
    topick: 'To pick', donetoday: 'Done today', shows: 'Shows', taptoswitch: 'Tap to switch',
    orders: 'orders', order: 'order', you: 'You', noone: 'No one yet', cancelled: 'cancelled', left: 'left', done: 'done',
    toclear: 'to clear', cleantable: 'Clean table first', mixed: 'Mixed',
    st_session: 'This session', st_today: 'Today', st_week: 'Last 7 days',
    scanlabel: 'Scan packing label', typeinstead: 'Type order number instead',
    scannerready: 'Scanner ready — scan a label any time',
    choosefirst: 'Choose a show first', picking: 'Picking',
    typetitle: 'Find an order', typelabel: 'Tracking or order #', findorder: 'Find order',
    nothing: 'Nothing to pick right now', nothingsub: 'New orders show up here after the next live is imported.', refresh: 'Refresh',
    nodone: 'No finished shows yet today.',
    noshipment: 'No order for', lookupfailed: "Couldn't look that up. Try again.",
    alreadypicked: 'Already picked by', someone: 'someone',
    clearcancelled: 'Clear cancelled items off the table first', cleanoutfirst: 'Clean out the table first',
    finishfirst: 'Finish this order first',
    orderw: 'Order', items: 'items', item: 'item', of: 'of',
    combined: 'Combined order', combinedsub: 'Items come from different shows. Pick each table set in order.',
    tableset: 'Table set', giveaway: 'Giveaway', gotomanager: 'Get it from your manager',
    cancelleditem: 'Cancelled', moretopick: 'more to pick', donenext: 'Done — scan next',
    notall: 'Not everything is ticked', markanyway: 'Mark picked anyway', keeppicking: 'Keep picking',
    orderpicked: 'Order picked — bring it to the packer',
    leavetitle: 'Leave this order?', leavebody: 'Items you ticked stay ticked.', leave: 'Leave', stay: 'Stay',
    reportproblem: 'Report a problem', whatswrong: "What's wrong?", issuehelp: 'Your manager gets it in Issues. You can keep picking.',
    p_missing: 'Item missing', p_damaged: 'Damaged', p_wrongsku: 'Wrong SKU on table', p_cantfind: "Can't find the table",
    note: 'Note (optional)', describe: 'Describe the problem…', reportskip: 'Report & skip',
    pickreason: 'Choose what is wrong, or write a note', reported: 'Reported to your manager',
    dontpick: "Don't pick this order", cancelledsub: 'The customer cancelled it. Put any items back and scan the next label.', scannext: 'Scan next label',
    customer: 'Customer', error: 'Something went wrong. Try again.',
    tab_today: 'Today', tab_pack: 'Pack', tab_track: 'Track', tab_more: 'More', switchlang: 'Cambiar a español'
  };
  M.strings.es = {
    pick: 'Recoger', home: 'Inicio', myprofile: 'Mi perfil', cancel: 'Cancelar', retry: 'Reintentar',
    offline: 'Sin conexión. Reconéctate para seguir recogiendo.', loaderr: 'No se pudieron cargar los shows',
    orderswaiting: 'pedidos pendientes', orderwaiting: 'pedido pendiente',
    yourepicking: 'Estás recogiendo', lefttopick: 'por recoger', picked: 'recogidos', issue: 'problema', issues: 'problemas',
    topick: 'Por recoger', donetoday: 'Listos hoy', shows: 'Shows', taptoswitch: 'Toca para cambiar',
    orders: 'pedidos', order: 'pedido', you: 'Tú', noone: 'Nadie aún', cancelled: 'cancelados', left: 'faltan', done: 'listo',
    toclear: 'por retirar', cleantable: 'Limpia la mesa primero', mixed: 'Mixto',
    st_session: 'Esta sesión', st_today: 'Hoy', st_week: 'Últimos 7 días',
    scanlabel: 'Escanear etiqueta', typeinstead: 'Escribir el número de pedido',
    scannerready: 'Escáner listo — escanea una etiqueta cuando quieras',
    choosefirst: 'Primero elige un show', picking: 'Recogiendo',
    typetitle: 'Buscar un pedido', typelabel: 'Rastreo o # de pedido', findorder: 'Buscar pedido',
    nothing: 'Nada por recoger ahora', nothingsub: 'Los pedidos nuevos aparecen aquí cuando se importa el próximo live.', refresh: 'Actualizar',
    nodone: 'Aún no hay shows terminados hoy.',
    noshipment: 'No hay pedido para', lookupfailed: 'No se pudo buscar. Intenta de nuevo.',
    alreadypicked: 'Ya recogido por', someone: 'alguien',
    clearcancelled: 'Primero retira los artículos cancelados de la mesa', cleanoutfirst: 'Primero limpia la mesa',
    finishfirst: 'Termina este pedido primero',
    orderw: 'Pedido', items: 'artículos', item: 'artículo', of: 'de',
    combined: 'Pedido combinado', combinedsub: 'Los artículos son de shows distintos. Recoge cada set de mesas en orden.',
    tableset: 'Set de mesas', giveaway: 'Regalo', gotomanager: 'Pídelo a tu gerente',
    cancelleditem: 'Cancelado', moretopick: 'por recoger', donenext: 'Listo — siguiente',
    notall: 'No todo está marcado', markanyway: 'Marcar como recogido', keeppicking: 'Seguir recogiendo',
    orderpicked: 'Pedido recogido — llévalo al empacador',
    leavetitle: '¿Salir de este pedido?', leavebody: 'Los artículos marcados siguen marcados.', leave: 'Salir', stay: 'Quedarme',
    reportproblem: 'Reportar un problema', whatswrong: '¿Qué pasa?', issuehelp: 'Tu gerente lo recibe en Problemas. Puedes seguir recogiendo.',
    p_missing: 'Falta artículo', p_damaged: 'Dañado', p_wrongsku: 'SKU incorrecto en la mesa', p_cantfind: 'No encuentro la mesa',
    note: 'Nota (opcional)', describe: 'Describe el problema…', reportskip: 'Reportar y saltar',
    pickreason: 'Elige qué pasa o escribe una nota', reported: 'Reportado a tu gerente',
    dontpick: 'No recojas este pedido', cancelledsub: 'El cliente lo canceló. Devuelve los artículos y escanea la siguiente etiqueta.', scannext: 'Escanear siguiente',
    customer: 'Cliente', error: 'Algo salió mal. Intenta de nuevo.',
    tab_today: 'Hoy', tab_pack: 'Empacar', tab_track: 'Rastrear', tab_more: 'Más', switchlang: 'Switch to English'
  };
  var t = M.t;
  M.applyI18n();
  $('langBtn').querySelector('.m-lang').textContent = M.lang === 'en' ? 'ES' : 'EN';
  $('langBtn').setAttribute('aria-label', t('switchlang'));
  $('langBtn').addEventListener('click', function () { M.setLang(M.lang === 'en' ? 'es' : 'en'); });

  var CHEV = '<svg class="m-row__chev" viewBox="0 0 8 14" aria-hidden="true"><path d="M1 1l6 6-6 6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

  // ── State ────────────────────────────────────────────────────────────────
  var qs = new URLSearchParams(location.search);
  var shows = null, extras = { shows: {}, me: document.body.getAttribute('data-name') || '', today: '' };
  var seg = 'todo';
  var currentShow = qs.get('show') || M.ls('pickShow') || '';
  if (qs.get('show')) M.lsSet('pickShow', currentShow);
  var order = null;                       // {sid, shipment, items, giveaways}
  var busy = false, pushed = false;
  var sessionCount = 0;
  try { sessionCount = parseInt(sessionStorage.getItem('pickSession') || '0', 10) || 0; } catch (e) {}
  $('stSession').textContent = sessionCount;

  function setCurrentShow(name) {
    currentShow = name || '';
    try { if (currentShow) localStorage.setItem('pickShow', currentShow); else localStorage.removeItem('pickShow'); } catch (e) {}
  }
  function platformLabel(sh) {
    if ((sh.platform_count || 0) > 1) return t('mixed');
    var p = String(sh.platform || '').toLowerCase();
    if (p === 'tiktok') return 'TikTok';
    if (p === 'whatnot') return 'Whatnot';
    return p ? p.charAt(0).toUpperCase() + p.slice(1) : '';
  }
  function num(v) { return parseInt(v, 10) || 0; }
  function showNums(sh) {
    var ex = extras.shows[sh.name] || {};
    var total = num(sh.shipments), pend = num(sh.pending), canc = num(sh.cancelled), iss = num(ex.issues);
    var active = Math.max(0, total - canc);
    var pickedN = Math.max(0, active - pend - iss);
    return { total: total, active: active, pending: pend, cancelled: canc, issues: iss, picked: pickedN,
             pct: active ? Math.round(100 * (active - pend) / active) : 0 };
  }
  function whoLabel(sh) {
    var p = (extras.shows[sh.name] || {}).pickers || [];
    if (!p.length) return t('noone');
    if (extras.me && p.indexOf(extras.me) >= 0) return t('you');
    return String(p[0]).split(/\s+/)[0];
  }
  function isDirty(sh) { return !!(sh.cleanup && !sh.cleanup.is_clean && sh.cleanup.groups_total > 0); }

  // ── Queue ────────────────────────────────────────────────────────────────
  function loadQueue() {
    $('loadErr').hidden = true;
    return Promise.all([M.api('/api/shows'), M.api('/m/api/pick/extras').catch(function () { return null; })])
      .then(function (res) {
        shows = Array.isArray(res[0]) ? res[0] : [];
        if (res[1] && res[1].ok) extras = res[1];
        renderQueue();
      })
      .catch(function (e) {
        if (e && (e.message === 'signed_out' || e.message === 'billing')) return;
        if (shows === null) { $('heroSlot').innerHTML = ''; $('showList').innerHTML = ''; }
        $('loadErr').hidden = false;
      });
  }
  function loadStats() {
    M.api('/api/pick/my-stats').then(function (d) {
      $('stToday').textContent = num(d.today); $('stWeek').textContent = num(d.week);
    }).catch(function () {});
  }

  function renderQueue() {
    var todo = shows.filter(function (s) { return num(s.pending) > 0; });
    var done = shows.filter(function (s) {
      if (num(s.pending) > 0) return false;
      return !s.done_at || !extras.today || String(s.done_at).slice(0, 10) === extras.today;
    });
    var waiting = todo.reduce(function (a, s) { return a + num(s.pending); }, 0);
    var d = new Date();
    var dateStr = d.toLocaleDateString(M.lang === 'es' ? 'es' : 'en-US', { weekday: 'long', month: 'short', day: 'numeric' });
    $('qSub').textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1) + ' · ' + waiting + ' ' + (waiting === 1 ? t('orderwaiting') : t('orderswaiting'));
    $('segTodo').textContent = todo.length; $('segDone').textContent = done.length;

    // The saved show may have finished, or belong to another day's list.
    var cur = null;
    for (var i = 0; i < todo.length; i++) if (todo[i].name === currentShow) cur = todo[i];
    if (currentShow && !cur) setCurrentShow('');

    // Hero
    if (cur) {
      var n = showNums(cur), plat = platformLabel(cur);
      var meta = [];
      if (cur.time_range) meta.push(cur.time_range);
      meta.push(n.active + ' ' + (n.active === 1 ? t('order') : t('orders')));
      $('heroSlot').innerHTML =
        '<button type="button" class="m-card m-card--hero m-card--tap pk-now" id="hero">' +
          '<div class="pk-now__top"><span class="pk-now__eyebrow">' + esc(t('yourepicking')) + '</span>' +
            (plat ? '<span class="pk-now__chip">' + esc(plat) + '</span>' : '') + '</div>' +
          '<div class="pk-now__title">' + esc(cur.name) + '</div>' +
          '<div class="pk-now__meta">' + esc(meta.join(' · ')) + '</div>' +
          '<div class="pk-now__nums">' +
            '<div class="pk-now__num"><b>' + n.pending + '</b><span>' + esc(t('lefttopick')) + '</span></div>' +
            '<div class="pk-now__num"><b>' + n.picked + '</b><span>' + esc(t('picked')) + '</span></div>' +
            (n.issues ? '<div class="pk-now__num"><b>' + n.issues + '</b><span>' + esc(n.issues === 1 ? t('issue') : t('issues')) + '</span></div>' : '') +
          '</div>' +
          '<div class="m-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + n.pct + '"><span style="width:' + n.pct + '%"></span></div>' +
        '</button>';
      $('hero').addEventListener('click', startScan);
    } else {
      $('heroSlot').innerHTML = '';
    }
    $('scannerOk').hidden = !(cur && M.scannerSeen);

    // List
    var list = seg === 'todo' ? todo.slice() : done.slice();
    if (seg === 'todo') list.sort(function (a, b) {
      return ((b.name === currentShow) - (a.name === currentShow)) || (num(b.pending) - num(a.pending));
    });
    $('showsHint').hidden = seg !== 'todo' || list.length < 2;
    if (!list.length) {
      $('showList').innerHTML = seg === 'todo'
        ? '<div class="m-empty"><div class="m-empty__icon"><svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4" width="18" height="21" rx="3.5"/><path d="m9.5 15 3 3 6-6.5"/></svg></div>' +
          '<div class="m-empty__title">' + esc(t('nothing')) + '</div><div class="m-empty__body">' + esc(t('nothingsub')) + '</div>' +
          '<button type="button" class="m-btn m-btn--secondary" id="emptyRefresh">' + esc(t('refresh')) + '</button></div>'
        : '<div class="m-empty"><div class="m-empty__body">' + esc(t('nodone')) + '</div></div>';
      var er = $('emptyRefresh'); if (er) er.addEventListener('click', refresh);
      return;
    }
    var html = '<div class="m-list">';
    list.forEach(function (sh, idx) {
      var n = showNums(sh), plat = platformLabel(sh), isDone = seg === 'done';
      var sub = (plat ? '<span class="m-pill m-pill--brand m-pill--plain">' + esc(plat) + '</span>' : '');
      if (!isDone && isDirty(sh)) sub += '<span class="m-pill m-pill--pending m-pill--plain">' + num(sh.cleanup.groups_pending) + ' ' + esc(t('toclear')) + '</span>';
      else if (!isDone && sh.needs_cleanout) sub += '<span class="m-pill m-pill--packed m-pill--plain">' + esc(t('cleantable')) + '</span>';
      var bits = [n.active + ' ' + (n.active === 1 ? t('order') : t('orders'))];
      if (!isDone) bits.push(whoLabel(sh));
      if (n.cancelled) bits.push(n.cancelled + ' ' + t('cancelled'));
      sub += '<span>' + esc(bits.join(' · ')) + '</span>';
      var inner =
        '<div class="m-row__body"><div class="m-row__title">' + esc(sh.name) + '</div>' +
          '<div class="m-row__sub">' + sub + '</div>' +
          '<div class="m-progress"><span class="' + (isDone ? 'm-progress__c' : 'm-progress__a') + '" style="width:' + n.pct + '%"></span></div></div>';
      if (isDone) {
        html += '<div class="m-row pk-row">' + inner + '<div class="m-row__trail"><span class="m-pill m-pill--shipped">' + esc(t('done')) + '</span></div></div>';
      } else {
        html += '<button type="button" class="m-row pk-row' + (sh.name === currentShow ? ' is-current' : '') + '" data-i="' + idx + '"' +
          (sh.name === currentShow ? ' aria-current="true"' : '') + '>' + inner +
          '<div class="m-row__trail"><div class="pk-left"><b>' + n.pending + '</b><span>' + esc(t('left')) + '</span></div>' + CHEV + '</div></button>';
      }
    });
    html += '</div>';
    $('showList').innerHTML = html;
    if (seg === 'todo') {
      var rows = $('showList').querySelectorAll('button.pk-row');
      for (var r = 0; r < rows.length; r++) rows[r].addEventListener('click', onShowTap.bind(null, list));
    }
  }

  function onShowTap(list, e) {
    var sh = list[num(e.currentTarget.getAttribute('data-i'))];
    if (!sh) return;
    // Same two gates as the desktop screen, same destination.
    if (isDirty(sh)) { location.href = '/admin/cleanup?show=' + encodeURIComponent(sh.name); return; }
    if (sh.needs_cleanout) { location.href = '/admin/cleanup?show=' + encodeURIComponent(sh.name) + '&prepick=1'; return; }
    if (sh.name !== currentShow) {
      setCurrentShow(sh.name);
      M.haptic('tap');
      M.toast(t('picking') + ' ' + sh.name);
      renderQueue();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      startScan();
    }
  }

  var segBtns = document.querySelectorAll('.m-seg__btn');
  for (var sb = 0; sb < segBtns.length; sb++) segBtns[sb].addEventListener('click', function (e) {
    seg = e.currentTarget.getAttribute('data-seg');
    for (var k = 0; k < segBtns.length; k++) segBtns[k].setAttribute('aria-selected', segBtns[k] === e.currentTarget ? 'true' : 'false');
    if (shows) renderQueue();
  });

  function refresh() { loadQueue(); loadStats(); }
  $('retryBtn').addEventListener('click', refresh);

  // ── Scanning ─────────────────────────────────────────────────────────────
  var ASK = function () { return { title: t('typetitle'), label: t('typelabel'), button: t('findorder') }; };
  function needShow() {
    if (currentShow) return false;
    M.toast(t('choosefirst'), 'error');
    return true;
  }
  function startScan() { if (!needShow()) M.scan(ASK()); }
  $('scanBtn').addEventListener('click', startScan);
  $('typeBtn').addEventListener('click', function () { if (!needShow()) M.typeCode(ASK()); });

  // USPS IMpb barcodes carry routing digits before the 22-digit tracking number.
  function normalizeTracking(s) {
    s = String(s || '').trim();
    if (/^\d{23,40}$/.test(s)) return s.slice(-22);
    return s;
  }

  M.onScan(function (raw, source) {
    if (!$('stop').hidden) closeStop();
    if (order) { M.toast(t('finishfirst'), 'error'); return; }
    if (source === 'scanner' && shows) $('scannerOk').hidden = !currentShow;
    if (needShow()) return;
    lookup(normalizeTracking(raw));
  });

  /* A label carries the tracking number; /api/pick/<id> takes the shipment id. Try it
     as an id first, then resolve it through the general lookup — as the desktop does. */
  function lookup(code) {
    if (busy || !code) return;
    busy = true;
    M.api('/api/pick/' + encodeURIComponent(code)).then(function (d) {
      if (d && d.ok) return d;
      return M.api('/api/shipment/' + encodeURIComponent(code)).then(function (d2) {
        if (!d2 || !d2.ok || !d2.shipment) { M.toast(t('noshipment') + ' ' + code, 'error'); return null; }
        return M.api('/api/pick/' + encodeURIComponent(d2.shipment.shipment_id));
      });
    }).then(function (d) {
      busy = false;
      if (d) openOrder(d);
    }).catch(function (e) {
      busy = false;
      if (e && e.message === 'signed_out') return;
      M.toast(t('lookupfailed'), 'error');
    });
  }

  // ── Order ────────────────────────────────────────────────────────────────
  function openOrder(d) {
    if (!d.ok) { M.toast(d.error || t('lookupfailed'), 'error'); return; }
    var s = d.shipment || {};
    if (d.cleanup_blocked) {
      M.toast(t('clearcancelled'), 'error');
      setTimeout(function () { location.href = '/admin/cleanup?show=' + encodeURIComponent(s.import_label || ''); }, 900);
      return;
    }
    if (d.cleanout_required) {
      M.toast(t('cleanoutfirst'), 'error');
      setTimeout(function () { location.href = '/admin/cleanup?show=' + encodeURIComponent(s.import_label || '') + '&prepick=1'; }, 900);
      return;
    }
    if (s.status === 'cancelled') { M.haptic('error'); $('stop').hidden = false; return; }
    if (d.already_picked || s.status === 'picked') {
      var who = d.picked_by || s.picked_by || t('someone');
      var when = String(d.picked_at || s.picked_at || '').replace('T', ' ').slice(0, 16);
      M.toast(t('alreadypicked') + ' ' + who + (when ? ' · ' + when : ''), 'error');
      return;
    }
    order = {
      sid: s.shipment_id, shipment: s, items: d.items || [],
      giveaways: (d.giveaways || []).map(function (g) {
        return { id: g.id, prize_name: g.prize_name, winner_username: g.winner_username, added: g.attach_status === 'added' };
      })
    };
    var buyer = s.buyer_name || s.buyer_username || t('customer');
    $('oBuyer').textContent = buyer; $('oNavTitle').textContent = buyer;
    var active = order.items.filter(function (i) { return !i.cancelled; }).length + order.giveaways.length;
    var sid = String(s.shipment_id || '');
    var bits = [t('orderw') + ' ' + (sid.length > 12 ? '…' + sid.slice(-10) : sid), active + ' ' + (active === 1 ? t('item') : t('items'))];
    if (s.import_label) bits.push(s.import_label);
    $('oSub').textContent = bits.join(' · ');
    $('oTags').innerHTML = s.tracking_code ? '<span class="m-pill m-pill--plain">' + esc(s.tracking_code) + '</span>' : '';
    renderItems();
    M.hideToast();                         // a message about the previous label no longer applies
    showView('order');
    M.haptic('success');
    try { history.pushState({ order: order.sid }, '', '?order=' + encodeURIComponent(order.sid)); pushed = true; } catch (e) {}
  }

  function showView(which) {
    var isOrder = which === 'order';
    $('queue').hidden = isOrder; $('queueBar').hidden = isOrder;
    $('order').hidden = !isOrder; $('orderBar').hidden = !isOrder;
    window.scrollTo(0, 0);
  }

  // Warehouse order: show by date -> Part 1,2,3 -> SKU ascending (same as desktop).
  function showOf(name) {
    name = name || '';
    var base = name.replace(/\s*Part\s*\d+.*$/i, '').trim();
    var dm = name.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
    var dnum = dm ? (parseInt(dm[3].length === 2 ? '20' + dm[3] : dm[3], 10) * 10000 + parseInt(dm[1], 10) * 100 + parseInt(dm[2], 10)) : 99999999;
    return { base: base || 'Show', date: dnum };
  }
  function partOf(name) { var m = (name || '').match(/Part\s*(\d+)/i); return m ? parseInt(m[1], 10) : 9999; }
  function skuNum(s) { var m = String(s || '').match(/\d+/); return m ? parseInt(m[0], 10) : 999999; }
  function productName(s) {
    var safe = esc(s || '');
    var m = safe.match(/(Part\s*\d+)/i);
    if (!m) return safe;
    var stripped = safe.replace(/[\s·,—–-]*Part\s*\d+[\s·,—–-]*/i, ' ').replace(/\s{2,}/g, ' ').trim();
    return '<span class="pk-part">' + m[1].toUpperCase() + '</span>' + stripped;
  }
  function counts() {
    var active = order.items.filter(function (i) { return !i.cancelled; });
    var gvAdded = order.giveaways.filter(function (g) { return g.added; }).length;
    return { picked: active.filter(function (i) { return i.picked; }).length + gvAdded, total: active.length + order.giveaways.length,
             itemsPicked: active.filter(function (i) { return i.picked; }).length, itemsTotal: active.length };
  }

  function renderItems() {
    var c = counts(), pct = c.total ? Math.round(100 * c.picked / c.total) : 0;
    $('oProgText').textContent = c.picked + ' ' + t('of') + ' ' + c.total + ' ' + t('picked');
    $('oProgPct').textContent = pct + '%';
    $('oProg').setAttribute('aria-valuenow', pct);
    $('oProg').firstElementChild.style.width = pct + '%';

    var arr = order.items.map(function (it) {
      var si = showOf(it.product_name);
      return { it: it, base: si.base, date: si.date, part: partOf(it.product_name), sku: skuNum(it.sku) };
    });
    arr.sort(function (a, b) { return (a.date - b.date) || (a.part - b.part) || (a.sku - b.sku) || 0; });
    var bases = []; arr.forEach(function (x) { if (bases.indexOf(x.base) < 0) bases.push(x.base); });
    var multi = bases.length > 1, last = null, setIdx = 0, open = false, html = '';
    if (multi) html += '<div class="m-banner m-banner--warn" style="margin:0 0 var(--m-4)"><div><b>' + esc(t('combined')) + ' · ' + bases.length + ' ' + esc(t('shows').toLowerCase()) + '</b><br>' + esc(t('combinedsub')) + '</div></div>';
    arr.forEach(function (x) {
      if (multi && x.base !== last) {
        if (open) html += '</div>';
        setIdx++; last = x.base;
        html += '<div class="pk-set"><span>' + esc(t('tableset')) + ' ' + setIdx + '</span><span>' + esc(x.base) + '</span></div><div class="m-list">';
        open = true;
      } else if (!open) { html += '<div class="m-list">'; open = true; }
      var it = x.it, q = num(it.quantity) || 1;
      var cls = 'm-row pk-item' + (it.cancelled ? ' is-cancelled' : (it.picked ? ' is-picked' : ''));
      html += '<div class="' + cls + '" role="checkbox" tabindex="-1" aria-checked="' + (it.picked ? 'true' : 'false') + '"' + (it.cancelled ? ' aria-disabled="true"' : ' data-id="' + it.id + '"') + '>' +
        '<div class="pk-check">' + CHECK + '</div>' +
        '<div class="m-row__body"><div class="m-row__title">' + productName(it.product_name) + '</div>' +
          '<div class="m-row__sub"><span class="pk-sku">' + esc(it.sku || '?') + '</span>' +
          (it.cancelled ? '<span class="m-pill m-pill--cancelled">' + esc(t('cancelleditem')) + '</span>' : '') + '</div></div>' +
        '<div class="m-row__trail"><span class="pk-qty' + (q > 1 ? ' pk-qty--multi' : '') + '">×' + q + '</span></div></div>';
    });
    if (open) html += '</div>';
    if (order.giveaways.length) {
      html += '<div class="pk-set"><span>' + esc(t('giveaway')) + '</span><span>' + esc(t('gotomanager')) + '</span></div><div class="m-list">';
      order.giveaways.forEach(function (g) {
        html += '<div class="m-row pk-item' + (g.added ? ' is-picked' : '') + '" role="checkbox" tabindex="-1" aria-checked="' + (g.added ? 'true' : 'false') + '" data-gid="' + g.id + '">' +
          '<div class="pk-check">' + CHECK + '</div>' +
          '<div class="m-row__body"><div class="m-row__title">' + esc(g.prize_name || '') + '</div>' +
          '<div class="m-row__sub"><span class="m-pill m-pill--brand m-pill--plain">' + esc(t('giveaway')) + '</span>' +
          (g.winner_username ? '<span>@' + esc(g.winner_username) + '</span>' : '') + '</div></div>' +
          '<div class="m-row__trail"><span class="pk-qty">×1</span></div></div>';
      });
      html += '</div>';
    }
    $('oItems').innerHTML = html;

    var btn = $('doneBtn');
    if (c.total > 0 && c.picked === c.total) {
      btn.className = 'm-btn m-btn--lg m-btn--primary';
      btn.textContent = t('donenext');
    } else {
      btn.className = 'm-btn m-btn--lg m-btn--secondary';
      btn.textContent = (c.total - c.picked) + ' ' + t('moretopick');
    }
  }

  $('oItems').addEventListener('click', function (e) {
    var row = e.target.closest ? e.target.closest('.pk-item') : null;
    if (!row || !order || row.classList.contains('is-cancelled')) return;
    if (row.hasAttribute('data-gid')) toggleGiveaway(num(row.getAttribute('data-gid')));
    else if (row.hasAttribute('data-id')) toggleItem(num(row.getAttribute('data-id')));
  });

  function toggleItem(id) {
    var it = null;
    order.items.forEach(function (x) { if (x.id === id) it = x; });
    if (!it || it._busy) return;
    it._busy = true;
    var sid = order.sid;
    M.haptic('tap');
    M.api('/api/pick/item/' + id + '/toggle', { method: 'POST' }).then(function (d) {
      it._busy = false;
      if (!d.ok) { M.toast(d.error || t('error'), 'error'); return; }
      it.picked = d.picked;
      if (order && order.sid === sid) renderItems();
    }).catch(function () { it._busy = false; M.toast(t('error'), 'error'); });
  }
  function toggleGiveaway(gid) {
    var g = null;
    order.giveaways.forEach(function (x) { if (x.id === gid) g = x; });
    if (!g) return;
    var sid = order.sid, next = !g.added;
    g.added = next; M.haptic('tap'); renderItems();          // optimistic, like desktop
    function undo() { g.added = !next; if (order && order.sid === sid) renderItems(); M.toast(t('error'), 'error'); }
    M.api('/api/giveaway/' + gid + '/mark-added', { method: 'POST', body: { added: next } })
      .then(function (d) { if (!d.ok) undo(); }).catch(undo);
  }

  function leaveOrder() {
    order = null;
    showView('queue');
    if (pushed) { pushed = false; try { history.replaceState({}, '', location.pathname); } catch (e) {} }
    refresh();
  }

  $('doneBtn').addEventListener('click', function () {
    if (!order || busy) return;
    var c = counts();
    var go = (c.itemsPicked < c.itemsTotal)
      ? M.confirm({ title: t('notall'), body: c.itemsPicked + ' ' + t('of') + ' ' + c.itemsTotal + ' ' + t('picked') + '.', ok: t('markanyway'), cancel: t('keeppicking') })
      : Promise.resolve(true);
    go.then(function (yes) {
      if (!yes || !order) return;
      busy = true;
      M.api('/api/pick/complete/' + encodeURIComponent(order.sid), { method: 'POST' }).then(function (d) {
        busy = false;
        if (!d.ok) {
          M.toast(d.error || t('error'), 'error');
          if (d.already_picked) leaveOrder();
          return;
        }
        sessionCount++;
        try { sessionStorage.setItem('pickSession', String(sessionCount)); } catch (e) {}
        $('stSession').textContent = sessionCount;
        M.toast(t('orderpicked'), 'success');
        leaveOrder();
      }).catch(function () { busy = false; M.toast(t('error'), 'error'); });
    });
  });

  $('backBtn').addEventListener('click', function () {
    if (!order) { showView('queue'); return; }
    var c = counts();
    var go = (c.picked > 0 && c.picked < c.total)
      ? M.confirm({ title: t('leavetitle'), body: t('leavebody'), ok: t('leave'), cancel: t('stay') })
      : Promise.resolve(true);
    go.then(function (yes) { if (yes) leaveOrder(); });
  });
  // Swipe-back / browser back from the order returns to the queue.
  window.addEventListener('popstate', function () {
    if (order) { pushed = false; order = null; showView('queue'); refresh(); }
  });

  // ── Report a problem ─────────────────────────────────────────────────────
  var radios = document.querySelectorAll('#issueSheet .m-radio'), issueReason = '';
  function pickRadio(el) {
    issueReason = el ? el.getAttribute('data-r') : '';
    for (var i = 0; i < radios.length; i++) radios[i].setAttribute('aria-checked', radios[i] === el ? 'true' : 'false');
  }
  for (var ri = 0; ri < radios.length; ri++) radios[ri].addEventListener('click', function (e) { pickRadio(e.currentTarget); });
  $('issueBtn').addEventListener('click', function () {
    if (!order) return;
    pickRadio(null); $('issueNote').value = '';
    M.openSheet($('issueSheet'));
  });
  $('issueCancel').addEventListener('click', function () { M.closeSheet(); });
  $('issueSubmit').addEventListener('click', function () {
    if (!order || busy) return;
    var note = $('issueNote').value.trim();
    var reason = issueReason && note ? issueReason + ' — ' + note : (issueReason || note);
    if (!reason) { M.toast(t('pickreason'), 'error'); return; }
    busy = true;
    M.api('/api/pick/issue/' + encodeURIComponent(order.sid), { method: 'POST', body: { reason: reason } }).then(function (d) {
      busy = false;
      if (!d.ok) { M.toast(d.error || t('error'), 'error'); return; }
      M.closeSheet();
      M.toast(t('reported'), 'success');
      leaveOrder();
    }).catch(function () { busy = false; M.toast(t('error'), 'error'); });
  });

  // ── Cancelled-order stop screen ──────────────────────────────────────────
  function closeStop() { $('stop').hidden = true; }
  $('stopBtn').addEventListener('click', function () { closeStop(); startScan(); });

  // ── Connectivity + refresh ───────────────────────────────────────────────
  function netState() { $('offline').hidden = M.online(); }
  window.addEventListener('online', function () { netState(); if (!order) refresh(); });
  window.addEventListener('offline', netState);
  netState();
  document.addEventListener('visibilitychange', function () { if (!document.hidden && !order && !M.sheetIsOpen()) refresh(); });
  setInterval(function () { if (!document.hidden && !order && !M.sheetIsOpen() && M.online()) loadQueue(); }, 30000);

  // ── Start ────────────────────────────────────────────────────────────────
  loadStats();
  loadQueue().then(function () {
    var oid = qs.get('order');
    if (oid && /^[A-Za-z0-9_\-]{1,64}$/.test(oid)) {
      try { history.replaceState({}, '', location.pathname); } catch (e) {}
      M.api('/api/pick/' + encodeURIComponent(oid)).then(function (d) { if (d && d.ok) openOrder(d); }).catch(function () {});
    }
  });
})();
