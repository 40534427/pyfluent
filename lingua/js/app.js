/* Lingua · App Shell：路由、侧栏、顶栏、Toast、Modal、全局委托 */
(function () {
  if (!Store.init()) { location.replace('index.html'); return; }

  var NAV = [
    { route: 'dashboard', label: '学习主页', en: 'DASHBOARD', icon: 'home' },
    { route: 'courses', label: '分级课程', en: 'CURRICULUM', icon: 'book-open' },
    { route: 'learn', label: '互动学习', en: 'PRACTICE', icon: 'target' },
    { route: 'progress', label: '学习进度', en: 'PROGRESS', icon: 'bar-chart-3' },
    { route: 'path', label: '学习路径', en: 'PATHFINDER', icon: 'compass', badge: 'AI' },
    { route: 'community', label: '社区交流', en: 'COMMUNITY', icon: 'users' },
    { route: 'achievements', label: '成就激励', en: 'ACHIEVEMENTS', icon: 'trophy' }
  ];

  function $(sel, root) { return (root || document).querySelector(sel); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function initial(name) {
    var t = String(name || 'L').trim();
    return (t.charAt(0) || 'L').toUpperCase();
  }
  function toneOf(lang) { return lang === 'ja' ? 'red' : lang === 'ko' ? 'amber' : ''; }
  function avatar(name, lang) {
    return '<span class="avatar ' + toneOf(lang) + '">' + esc(initial(name)) + '</span>';
  }
  function fmt(n) { return Number(n || 0).toLocaleString('en-US'); }

  window.U = { $: $, esc: esc, initial: initial, avatar: avatar, tone: toneOf, fmt: fmt };

  var APP = window.APP = {
    route: 'dashboard',
    sub: '',
    params: {},
    toast: toast,
    go: go,
    rerender: render,
    refreshChrome: refreshChrome,
    speak: speak,
    modal: modal
  };

  function toast(message, type) {
    var root = $('#toastRoot');
    if (!root) return;
    var el = document.createElement('div');
    el.className = 'toast' + (type === 'error' ? ' error' : '');
    el.innerHTML = Icon(type === 'error' ? 'x' : 'check-circle', 16) + '<span>' + esc(message) + '</span>';
    root.appendChild(el);
    setTimeout(function () {
      el.classList.add('out');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 280);
    }, 2400);
  }

  function speak(text, langId) {
    if (!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance) return false;
    try {
      var meta = DB.langMeta(langId || Store.get().lang);
      var u = new SpeechSynthesisUtterance(text);
      u.lang = meta.speech;
      u.rate = 0.9;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
      return true;
    } catch (e) { return false; }
  }

  function modal(opts) {
    var wrap = document.createElement('div');
    wrap.className = 'modal-backdrop';
    wrap.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true" aria-label="' + esc(opts.title) + '">' +
        '<h3>' + esc(opts.title) + '</h3>' +
        (opts.text ? '<p>' + esc(opts.text) + '</p>' : '') +
        '<div class="modal-foot">' +
          '<button class="btn btn-ghost btn-sm" type="button" data-modal-cancel>取消</button>' +
          '<button class="btn ' + (opts.danger ? 'btn-accent' : 'btn-primary') + ' btn-sm" type="button" data-modal-ok>' + esc(opts.okText || '确定') + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(wrap);
    function close() { if (wrap.parentNode) wrap.parentNode.removeChild(wrap); }
    wrap.addEventListener('click', function (e) {
      if (e.target === wrap || e.target.closest('[data-modal-cancel]')) { close(); return; }
      if (e.target.closest('[data-modal-ok]')) {
        close();
        if (typeof opts.onOk === 'function') opts.onOk();
      }
    });
    var ok = wrap.querySelector('[data-modal-ok]');
    if (ok) ok.focus();
  }

  function go(hash) {
    if (!hash) return;
    var before = location.hash;
    location.hash = hash;
    if (location.hash === before) render();
  }

  function parseHash() {
    var raw = (location.hash || '#/dashboard').replace(/^#\/?/, '');
    var qi = raw.indexOf('?');
    var path = qi >= 0 ? raw.slice(0, qi) : raw;
    var query = qi >= 0 ? raw.slice(qi + 1) : '';
    var parts = path.split('/').filter(Boolean);
    var params = {};
    query.split('&').filter(Boolean).forEach(function (kv) {
      var i = kv.indexOf('=');
      var k = i >= 0 ? kv.slice(0, i) : kv;
      var v = i >= 0 ? kv.slice(i + 1) : '';
      try { params[decodeURIComponent(k)] = decodeURIComponent(v); }
      catch (e) { params[k] = v; }
    });
    return { route: parts[0] || 'dashboard', sub: parts[1] || '', params: params };
  }

  function renderNav(active) {
    var nav = $('#sideNav');
    if (!nav) return;
    nav.innerHTML = NAV.map(function (n) {
      var on = n.route === active;
      return '<a class="side-link' + (on ? ' active' : '') + '" href="#/' + n.route + '" data-route="' + n.route + '"' +
        (on ? ' aria-current="page"' : '') + '>' +
        Icon(n.icon, 18) + '<span>' + n.label + '</span>' +
        (n.badge ? '<span class="nav-badge">' + n.badge + '</span>' : '') +
        '</a>';
    }).join('');
  }

  function renderTopbar(route) {
    var s = Store.get();
    var meta = null;
    NAV.forEach(function (n) { if (n.route === route) meta = n; });
    if (!meta) meta = NAV[0];
    var crumb = $('#topbarCrumb');
    if (crumb) {
      crumb.innerHTML = '<span>LINGUA</span><span>/</span><strong>' + meta.en + ' · ' + meta.label + '</strong>';
    }
    var right = $('#topbarRight');
    if (!right) return;
    right.innerHTML =
      '<div class="lang-switch" role="tablist" aria-label="切换学习语言">' +
        DB.langs.map(function (l) {
          return '<button class="lang-btn' + (l.id === s.lang ? ' active' : '') + '" type="button" data-lang="' + l.id + '" role="tab" aria-selected="' + (l.id === s.lang) + '">' + l.badge + '</button>';
        }).join('') +
      '</div>' +
      '<span class="chip chip-streak" title="连续打卡">' + Icon('flame', 14) + s.streak + ' 天</span>' +
      '<span class="chip chip-xp" title="累计经验值">' + Icon('zap', 14) + fmt(s.xp) + ' XP</span>' +
      '<div class="user-wrap">' +
        '<button class="user-btn" type="button" id="userBtn" aria-label="账户菜单" aria-haspopup="true" aria-expanded="false">' +
          avatar(s.user.name, s.lang) +
        '</button>' +
        '<div class="user-menu" id="userMenu" role="menu">' +
          '<div class="um-head"><div class="um-name">' + esc(s.user.name) + '</div><div class="um-mail">' + esc(s.user.email) + '</div></div>' +
          '<button class="menu-item" type="button" role="menuitem" data-go="#/progress">' + Icon('bar-chart-3', 15) + '我的进度</button>' +
          '<button class="menu-item" type="button" role="menuitem" data-go="#/achievements">' + Icon('award', 15) + '我的成就</button>' +
          '<button class="menu-item" type="button" role="menuitem" data-go="#/path">' + Icon('compass', 15) + '学习路径</button>' +
          '<button class="menu-item danger" type="button" role="menuitem" id="logoutBtn">' + Icon('log-out', 15) + '退出登录</button>' +
        '</div>' +
      '</div>';
  }

  function renderSide() {
    var s = Store.get();
    var pct = s.dailyGoalMin ? Math.min(100, Math.round(s.minutesToday / s.dailyGoalMin * 100)) : 0;
    var remain = Math.max(0, s.dailyGoalMin - s.minutesToday);
    var note = $('#sideNote');
    if (note) {
      note.innerHTML =
        '<div class="note-top"><span>今日目标</span><span>' + pct + '%</span></div>' +
        '<div class="note-val">' + s.minutesToday + '<small> / ' + s.dailyGoalMin + ' 分钟</small></div>' +
        '<div class="progress"><span style="width:' + pct + '%"></span></div>' +
        '<div class="note-foot">' + (remain > 0 ? '再学 ' + remain + ' 分钟达成今日目标' : '今日目标已达成，继续保持') + '</div>';
    }
    var user = $('#sideUser');
    var lv = Store.levelInfo();
    if (user) {
      user.innerHTML =
        '<span class="avatar">' + esc(initial(s.user.name)) + '</span>' +
        '<div><div class="su-name">' + esc(s.user.name) + '</div><div class="su-meta">LV ' + lv.level + ' · ' + fmt(s.xp) + ' XP</div></div>' +
        '<button class="icon-btn logout" type="button" id="sideLogout" aria-label="退出登录">' + Icon('log-out', 15) + '</button>';
    }
  }

  function refreshChrome() {
    renderNav(APP.route);
    renderTopbar(APP.route);
    renderSide();
  }

  function render() {
    var parsed = parseHash();
    APP.route = Views[parsed.route] ? parsed.route : 'dashboard';
    APP.sub = parsed.sub;
    APP.params = parsed.params;
    var view = $('#view');
    if (!view) return;
    var mod = Views[APP.route];
    view.onclick = null;
    view.oninput = null;
    view.onsubmit = null;
    view.innerHTML = '<div class="view-enter">' + mod.render() + '</div>';
    refreshChrome();
    if (typeof mod.mount === 'function') mod.mount(view);
    window.scrollTo(0, 0);
  }

  function switchLang(id) {
    var s = Store.get();
    if (s.lang === id) return;
    Store.setLang(id);
    var meta = DB.langMeta(id);
    toast('已切换到 ' + meta.name + ' · ' + meta.native);
    render();
  }

  function confirmLogout() {
    modal({
      title: '退出登录？',
      text: '学习进度会保存在本机，下次登录可以继续。',
      okText: '退出登录',
      danger: true,
      onOk: function () {
        Store.clearSession();
        location.replace('index.html');
      }
    });
  }

  document.addEventListener('click', function (e) {
    var goEl = e.target.closest('[data-go]');
    if (goEl) {
      e.preventDefault();
      go(goEl.getAttribute('data-go'));
      return;
    }
    var langEl = e.target.closest('[data-lang]');
    if (langEl) { switchLang(langEl.getAttribute('data-lang')); return; }
    if (e.target.closest('#userBtn')) {
      var menu = $('#userMenu');
      if (menu) {
        var opened = menu.classList.toggle('open');
        var btn = $('#userBtn');
        if (btn) btn.setAttribute('aria-expanded', opened ? 'true' : 'false');
      }
      return;
    }
    if (e.target.closest('#logoutBtn') || e.target.closest('#sideLogout')) { confirmLogout(); return; }
    if (!e.target.closest('.user-wrap')) {
      var m = $('#userMenu');
      if (m) m.classList.remove('open');
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var m = $('#userMenu');
      if (m) m.classList.remove('open');
    }
  });

  if (!location.hash) {
    try { history.replaceState(null, '', '#/dashboard'); } catch (e) { location.hash = '#/dashboard'; }
  }
  window.addEventListener('hashchange', render);
  render();
})();
