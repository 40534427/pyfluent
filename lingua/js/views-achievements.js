/* Lingua · 成就激励 */
(function () {
  function render() {
    var s = Store.get();
    var list = DB.achievements;
    var unlocked = Store.unlockedCount();
    var pct = list.length ? Math.round(unlocked / list.length * 100) : 0;
    var lv = Store.levelInfo();

    var badges = list.map(function (a) {
      var raw = a.current(s);
      var cur = Math.min(raw, a.goal);
      var got = raw >= a.goal;
      var bpct = a.goal ? Math.round(cur / a.goal * 100) : 0;
      return '<div class="card badge-card ' + (got ? 'unlocked' : 'locked') + '">' +
        '<div class="badge-orb">' + Icon(a.icon, 24) + '</div>' +
        '<div class="badge-name">' + U.esc(a.name) + '</div>' +
        '<div class="badge-desc">' + U.esc(a.desc) + '</div>' +
        '<div class="badge-progress"><div class="bp-top"><span>' + (got ? '已解锁' : '进行中') + '</span><span>' + cur + ' / ' + a.goal + '</span></div>' +
          '<div class="progress"><span style="width:' + bpct + '%"></span></div></div>' +
      '</div>';
    }).join('');

    var challenges = DB.challenges.map(function (ch) {
      var raw = ch.current(s);
      var cur = Math.min(raw, ch.goal);
      var cpct = ch.goal ? Math.round(cur / ch.goal * 100) : 0;
      var claimed = Store.isClaimed(ch.id);
      var can = raw >= ch.goal && !claimed;
      var btn;
      if (claimed) btn = '<button class="btn btn-ghost btn-sm claim-btn claimed" type="button" disabled>已领取</button>';
      else if (can) btn = '<button class="btn btn-amber btn-sm claim-btn" type="button" data-claim="' + ch.id + '">领取 +' + ch.reward + '</button>';
      else btn = '<button class="btn btn-ghost btn-sm claim-btn" type="button" disabled>' + cur + ' / ' + ch.goal + '</button>';
      return '<div class="challenge">' +
        '<span class="ch-icon">' + Icon(ch.icon, 17) + '</span>' +
        '<div class="ch-body"><div class="ch-name">' + U.esc(ch.name) + '</div>' +
          '<div class="ch-meta">' + cur + ' / ' + ch.goal + ' ' + ch.unit + ' · 奖励 ' + ch.reward + ' XP</div>' +
          '<div class="progress"><span style="width:' + cpct + '%"></span></div></div>' +
        btn +
      '</div>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">ACHIEVEMENTS · 成就激励</div><h1>你的成就陈列架</h1>' +
          '<p class="sub">完成课程、保持连续、挑战口语与社区互动，解锁全部徽章</p></div>' +
        '<div class="head-actions"><span class="tag tag-amber">' + Icon('medal', 12) + 'LV ' + lv.level + ' · ' + U.fmt(s.xp) + ' XP</span></div>' +
      '</div>' +

      '<section class="ach-hero reveal" style="--d:50ms">' +
        '<div class="ah-main">' +
          '<div class="ah-eyebrow">ACHIEVEMENTS · 我的陈列架</div>' +
          '<h2>每一次练习，都算数。</h2>' +
          '<div class="ah-sub">已解锁 ' + unlocked + ' / ' + list.length + ' 枚徽章 · 今天还有 ' + DB.challenges.length + ' 个挑战可完成</div>' +
          '<div class="ah-nums">' +
            '<div class="ah-num"><div class="n">' + unlocked + '</div><div class="c">已解锁徽章</div></div>' +
            '<div class="ah-num"><div class="n">' + U.fmt(s.xp) + '</div><div class="c">累计经验值</div></div>' +
            '<div class="ah-num"><div class="n">' + s.streak + '</div><div class="c">连续学习天数</div></div>' +
          '</div>' +
        '</div>' +
        '<div class="ah-ring">' + Charts.ring(pct, { size: 118, stroke: 9, valueText: unlocked + '/' + list.length, label: '已解锁' }) + '</div>' +
      '</section>' +

      '<div class="ach-grid reveal" style="--d:90ms">' +
        '<div class="badge-grid">' + badges + '</div>' +
        '<aside class="rail">' +
          '<div class="card rail-card"><h3>' + Icon('target', 17) + '今日挑战</h3><div class="rail-sub">完成后可领取额外经验</div>' +
            '<div class="challenge-list">' + challenges + '</div></div>' +
          '<div class="card rail-card"><h3>' + Icon('lightbulb', 17) + '解锁小贴士</h3>' +
            '<ul class="guideline">' +
              '<li>' + Icon('check-circle', 13) + '<span>每天完成 1 节课程，连续 7 天解锁「七日之火」。</span></li>' +
              '<li>' + Icon('check-circle', 13) + '<span>口语跟读达到 80 分即可解锁「妙语连珠」，多练几次更稳。</span></li>' +
              '<li>' + Icon('check-circle', 13) + '<span>在社区发布动态，同时完成「社群之星」。</span></li>' +
              '<li>' + Icon('check-circle', 13) + '<span>三种语言都留下学习记录，可获得「三语通」。</span></li>' +
            '</ul></div>' +
        '</aside>' +
      '</div>';
  }

  function mount(root) {
    root.onclick = function (e) {
      var btn = e.target.closest('[data-claim]');
      if (!btn) return;
      var ok = Store.claimChallenge(btn.getAttribute('data-claim'));
      if (!ok) { APP.toast('挑战尚未完成，继续学习吧', 'error'); return; }
      APP.refreshChrome();
      APP.toast('挑战奖励已领取');
      APP.rerender();
    };
  }

  window.Views = window.Views || {};
  window.Views.achievements = { render: render, mount: mount };
})();
