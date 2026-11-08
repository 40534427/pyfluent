/* Lingua · 个性化学习路径 */
(function () {
  var sel = null;
  var loading = false;

  function ensureSel() {
    if (sel) return;
    var s = Store.get();
    sel = { lang: s.lang, goal: 'travel', levelIndex: 0, minutes: 20 };
  }

  function modeOf(icon) {
    if (icon === 'mic') return 'speaking';
    if (icon === 'headphones') return 'listening';
    return 'word';
  }

  function builderView() {
    ensureSel();
    var s = Store.get();
    var course = DB.courses[sel.lang];
    var goalKeys = Object.keys(API.GOALS);

    var langChips = DB.langs.map(function (l) {
      return '<button class="choice-chip' + (sel.lang === l.id ? ' active' : '') + '" type="button" data-sel="lang" data-val="' + l.id + '">' +
        Icon('languages', 15) + l.name + ' · ' + l.native + '</button>';
    }).join('');

    var goalChips = goalKeys.map(function (k) {
      var g = API.GOALS[k];
      return '<button class="choice-chip' + (sel.goal === k ? ' active' : '') + '" type="button" data-sel="goal" data-val="' + k + '">' +
        Icon(g.icon, 15) + g.label + '</button>';
    }).join('');

    var levelChips = course.levels.map(function (lv, i) {
      return '<button class="choice-chip' + (sel.levelIndex === i ? ' active' : '') + '" type="button" data-sel="levelIndex" data-val="' + i + '">' +
        Icon('layers', 15) + lv.code + ' · ' + lv.title + '</button>';
    }).join('');

    var minuteChips = [15, 20, 30, 45].map(function (m) {
      return '<button class="choice-chip' + (sel.minutes === m ? ' active' : '') + '" type="button" data-sel="minutes" data-val="' + m + '">' +
        Icon('clock', 15) + m + ' 分钟 / 天</button>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">PATHFINDER · 学习路径</div><h1>个性化学习路径</h1>' +
          '<p class="sub">根据目标、现有水平与每日可投入时间，生成 4 周可执行计划</p></div>' +
        '<div class="head-actions"><a class="btn btn-ghost" href="#/progress">' + Icon('bar-chart-3', 16) + '查看能力数据</a></div>' +
      '</div>' +

      '<section class="card builder-card reveal" style="--d:60ms">' +
        '<h2>四步生成你的学习路线</h2>' +
        '<div class="bc-sub">当前账户：' + U.esc(s.user.name) + ' · 已有 ' + s.xp + ' XP 学习积累</div>' +

        '<div class="builder-section"><div class="builder-label">' + Icon('languages', 12) + '目标语言</div>' +
          '<div class="choice-group">' + langChips + '</div></div>' +

        '<div class="builder-section"><div class="builder-label">' + Icon('target', 12) + '学习目标</div>' +
          '<div class="choice-group">' + goalChips + '</div></div>' +

        '<div class="builder-section"><div class="builder-label">' + Icon('layers', 12) + '当前水平</div>' +
          '<div class="choice-group">' + levelChips + '</div></div>' +

        '<div class="builder-section"><div class="builder-label">' + Icon('clock', 12) + '每日可投入时间</div>' +
          '<div class="choice-group">' + minuteChips + '</div></div>' +

        '<div class="builder-foot">' +
          '<div class="builder-hint">' + Icon('lightbulb', 14) + '结合能力测评与学习记录，自动安排每周 3 次练习与里程碑</div>' +
          (loading
            ? '<button class="btn btn-primary btn-lg" type="button" disabled><span class="spinner"></span> 正在规划…</button>'
            : '<button class="btn btn-primary btn-lg" type="button" data-generate>' + Icon('sparkles', 17) + '生成学习路径</button>') +
        '</div>' +
      '</section>' +

      (loading
        ? '<div class="card card-pad reveal"><div class="skeleton-box"><div class="skeleton lg"></div><div class="skeleton"></div><div class="skeleton sm"></div><div class="skeleton"></div><div class="skeleton sm"></div></div></div>'
        : '') +

      '<div class="strip-grid reveal" style="--d:110ms">' +
        '<div class="card card-pad"><div class="section-head"><div><div class="section-title">为什么需要路径</div><div class="section-sub">避免随机学习</div></div></div>' +
          '<div class="rec-list"><div class="rec-item" style="cursor:default"><span class="rec-icon">' + Icon('map', 17) + '</span><div class="rec-text"><div class="rec-title">目标对齐</div><div class="rec-desc">所有任务围绕你的真实目标组织</div></div></div>' +
          '<div class="rec-item" style="cursor:default"><span class="rec-icon">' + Icon('calendar', 17) + '</span><div class="rec-text"><div class="rec-title">节奏可控</div><div class="rec-desc">按每日时长拆分，不堆积任务</div></div></div></div></div>' +
        '<div class="card card-pad"><div class="section-head"><div><div class="section-title">路径如何调整</div><div class="section-sub">数据驱动</div></div></div>' +
          '<div class="rec-list"><div class="rec-item" style="cursor:default"><span class="rec-icon">' + Icon('trending-up', 17) + '</span><div class="rec-text"><div class="rec-title">优先补弱</div><div class="rec-desc">薄弱能力会获得更多练习任务</div></div></div>' +
          '<div class="rec-item" style="cursor:default"><span class="rec-icon">' + Icon('rotate-ccw', 17) + '</span><div class="rec-text"><div class="rec-title">随时重规划</div><div class="rec-desc">目标或时间变化后可重新生成</div></div></div></div></div>' +
      '</div>';
  }

  function pathView(path) {
    var meta = DB.langMeta(path.lang);
    var weak = Store.weakestSkill(path.lang);
    var first = path.weeks[0];
    var created = new Date(path.createdAt || Date.now()).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
    var goals = Object.keys(API.GOALS);
    var themeCount = path.weeks.length;

    var rationale =
      '<li>' + Icon('check-circle', 13) + '<span>' + meta.name + '当前最需要补强的是 <strong>' + U.esc(weak.label) + '</strong>（' + weak.value + ' 分），路径已提高该能力的练习占比。</span></li>' +
      '<li>' + Icon('check-circle', 13) + '<span>围绕「' + U.esc(path.goalLabel) + '」目标，任务全部来自 ' + path.level + ' 等级的真实场景课程。</span></li>' +
      '<li>' + Icon('check-circle', 13) + '<span>每天 ' + path.minutes + ' 分钟、每周 3 次练习，' + themeCount + ' 周形成稳定学习节奏。</span></li>' +
      '<li>' + Icon('check-circle', 13) + '<span>每周设置一个里程碑，完成后回到进度页查看能力变化。</span></li>';

    var weeks = path.weeks.map(function (w, wi) {
      var tasks = w.tasks.map(function (t) {
        return '<a class="week-task" href="#/learn?lesson=' + t.lessonId + '&mode=' + modeOf(t.icon) + '">' +
          Icon(t.icon, 15) + '<span class="wt-title">' + U.esc(t.title) + '</span>' +
          '<span class="wt-meta">' + U.esc(t.meta) + '</span><span class="chev">' + Icon('chevron-right', 14) + '</span></a>';
      }).join('');
      return '<div class="card week-card' + (wi === 0 ? ' current' : '') + '">' +
        '<div class="week-top"><span class="week-no">WEEK ' + String(w.no).padStart(2, '0') + '</span>' +
          '<span class="week-theme">' + U.esc(w.theme) + '</span><span class="tag tag-mono">' + w.tasks.length + ' 次练习</span></div>' +
        '<div class="week-tasks">' + tasks + '</div>' +
        '<div class="milestone">' + Icon('sparkles', 14) + '<span>' + U.esc(w.milestone) + '</span></div>' +
      '</div>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">PATHFINDER · 学习路径</div><h1>你的 4 周学习路线</h1>' +
          '<p class="sub">生成于 ' + created + ' · 每日 ' + path.minutes + ' 分钟 · 可随时重新规划</p></div>' +
      '</div>' +

      '<section class="path-header reveal" style="--d:50ms">' +
        '<div class="ph-icon">' + Icon(path.goalIcon, 26) + '</div>' +
        '<div><h2>' + meta.name + ' · ' + U.esc(path.goalLabel) + '</h2>' +
          '<div class="ph-sub">' + meta.native + ' · ' + path.level + ' 起点 · 每周 3 次 · ' + path.minutes + ' 分钟 / 天</div></div>' +
        '<div class="ph-actions">' +
          '<button class="btn btn-ghost btn-sm" type="button" data-reset>' + Icon('rotate-ccw', 14) + '重新规划</button>' +
          '<a class="btn btn-amber btn-sm" href="#/learn?lesson=' + first.tasks[0].lessonId + '">' + Icon('play', 14) + '开始第一周</a>' +
        '</div>' +
      '</section>' +

      '<div class="rationale reveal" style="--d:80ms"><h3>' + Icon('sparkles', 14) + '这条路径为什么适合你</h3><ul>' + rationale + '</ul></div>' +

      '<div class="timeline reveal" style="--d:110ms">' + weeks + '</div>' +

      (goals ? '<div class="learn-foot"><span>目标或时间变化后，可以随时重新生成一条新路径</span>' +
        '<button class="link-more" type="button" data-reset style="background:none;border:0;cursor:pointer">重新规划' + Icon('chevron-right', 14) + '</button></div>' : '');
  }

  function render() {
    var path = Store.getPath();
    if (path) return pathView(path);
    return builderView();
  }

  function generate() {
    if (loading) return;
    ensureSel();
    var course = DB.courses[sel.lang];
    var level = course.levels[sel.levelIndex] || course.levels[0];
    loading = true;
    APP.rerender();
    API.generatePath({
      lang: sel.lang,
      goal: sel.goal,
      level: level.code,
      levelIndex: sel.levelIndex,
      minutes: sel.minutes
    }).then(function (res) {
      loading = false;
      if (!res || !res.ok) {
        APP.toast('路径生成失败，请稍后重试', 'error');
        APP.rerender();
        return;
      }
      if (Store.get().lang !== sel.lang) Store.setLang(sel.lang);
      Store.setPath(res.path);
      APP.refreshChrome();
      APP.toast('学习路径已生成');
      APP.rerender();
    });
  }

  function mount(root) {
    root.onclick = function (e) {
      var chip = e.target.closest('[data-sel]');
      if (chip) {
        var field = chip.getAttribute('data-sel');
        var val = chip.getAttribute('data-val');
        if (field === 'lang') {
          sel.lang = val;
          sel.levelIndex = 0;
        } else if (field === 'levelIndex' || field === 'minutes') {
          sel[field] = parseInt(val, 10);
        } else {
          sel[field] = val;
        }
        APP.rerender();
        return;
      }
      if (e.target.closest('[data-generate]')) { generate(); return; }
      if (e.target.closest('[data-reset]')) {
        APP.modal({
          title: '重新规划学习路径？',
          text: '当前路径会被新的计划替换，学习记录不会丢失。',
          okText: '重新规划',
          danger: false,
          onOk: function () {
            Store.setPath(null);
            sel = null;
            APP.rerender();
          }
        });
      }
    };
  }

  window.Views = window.Views || {};
  window.Views.path = { render: render, mount: mount };
})();
