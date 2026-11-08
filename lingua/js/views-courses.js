/* Lingua · 分级课程 */
(function () {
  var activeLang = null;
  var levelIndex = 0;

  function levelStats(level, s) {
    var lessons = [];
    level.units.forEach(function (u) { lessons = lessons.concat(u.lessons); });
    var done = lessons.filter(function (l) { return s.completedLessons.indexOf(l.id) >= 0; }).length;
    return { done: done, total: lessons.length, pct: lessons.length ? Math.round(done / lessons.length * 100) : 0 };
  }

  function render() {
    var s = Store.get();
    var lang = s.lang;
    var meta = DB.langMeta(lang);
    var course = DB.courses[lang];
    if (activeLang !== lang) { activeLang = lang; levelIndex = 0; }
    if (levelIndex >= course.levels.length) levelIndex = 0;

    var prog = Store.courseProgress(lang);
    var cur = Store.currentLesson(lang);
    var level = course.levels[levelIndex];

    var tabs = course.levels.map(function (lv, i) {
      var st = levelStats(lv, s);
      return '<button class="level-tab' + (i === levelIndex ? ' active' : '') + '" type="button" data-level="' + i + '" aria-pressed="' + (i === levelIndex) + '">' +
        '<span class="lt-top"><span class="lt-code">' + lv.code + '</span>' +
        '<span class="lt-pct">' + st.pct + '%</span></span>' +
        '<span class="lt-title" style="display:block">' + U.esc(lv.title) + '</span>' +
        '<span class="lt-desc" style="display:block">' + U.esc(lv.desc) + '</span>' +
        '<span class="progress" style="display:block"><span style="width:' + st.pct + '%"></span></span>' +
        '</button>';
    }).join('');

    var units = level.units.map(function (unit, ui) {
      var rows = unit.lessons.map(function (lesson, li) {
        var done = s.completedLessons.indexOf(lesson.id) >= 0;
        var isCur = !done && cur && lesson.id === cur.id;
        var indexText = done ? Icon('check', 15) : isCur ? Icon('play', 13) : String(li + 1).padStart(2, '0');
        var stateTag = done
          ? '<span class="tag tag-green">已完成</span>'
          : isCur
            ? '<span class="tag tag-amber">继续学习</span>'
            : '<span class="tag tag-flat">未开始</span>';
        return '<a class="lesson-row' + (done ? ' done' : '') + (isCur ? ' current' : '') + '" href="#/learn?lesson=' + lesson.id + '">' +
          '<span class="lesson-index">' + indexText + '</span>' +
          '<div class="lesson-info"><div class="lesson-title">' + U.esc(lesson.title) + '</div>' +
            '<div class="lesson-meta">' +
              '<span class="m">' + Icon('clock', 12) + lesson.minutes + ' 分钟</span>' +
              '<span class="m">' + Icon('zap', 12) + lesson.xp + ' XP</span>' +
              '<span class="lesson-tags">' + lesson.tags.map(function (t) { return '<span class="tag tag-flat">' + U.esc(t) + '</span>'; }).join('') + '</span>' +
            '</div>' +
          '</div>' +
          '<span class="lesson-state">' + stateTag + '</span>' +
        '</a>';
      }).join('');

      return '<section class="unit-card">' +
        '<div class="unit-head">' +
          '<span class="unit-no">UNIT ' + String(ui + 1).padStart(2, '0') + '</span>' +
          '<div class="unit-text"><div class="unit-title">' + U.esc(unit.title) + '</div><div class="unit-scene">' + U.esc(unit.scene) + '</div></div>' +
          '<span class="tag tag-mono">' + unit.lessons.length + ' LESSONS</span>' +
        '</div>' +
        '<div class="lesson-list">' + rows + '</div>' +
      '</section>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">CURRICULUM · 分级课程</div><h1>' + meta.name + '分级课程体系</h1>' +
          '<p class="sub">从 ' + course.levels[0].code + ' 到 ' + course.levels[course.levels.length - 1].code + '，' + course.totalLessons + ' 节场景课，按单元循序推进</p></div>' +
        '<div class="head-actions">' +
          '<a class="btn btn-ghost" href="#/progress">' + Icon('bar-chart-3', 16) + '查看进度</a>' +
          '<a class="btn btn-primary" href="#/path">' + Icon('sparkles', 16) + '生成学习路径</a>' +
        '</div>' +
      '</div>' +

      '<section class="course-hero reveal" style="--d:60ms">' +
        '<div>' +
          '<div class="eyebrow">LEVEL SYSTEM · ' + meta.badge + '</div>' +
          '<div class="ch-title">' + meta.name + '<span class="ch-native">' + meta.native + '</span></div>' +
          '<div class="ch-sub">' + U.esc(meta.blurb) + '</div>' +
          '<div class="ch-meta">' +
            '<span class="tag tag-green">' + course.levels.length + ' 个等级</span>' +
            '<span class="tag tag-amber">' + course.totalLessons + ' 节课程</span>' +
            '<span class="tag tag-mono">' + U.fmt(meta.learners) + ' 名学习者</span>' +
          '</div>' +
        '</div>' +
        '<div class="course-hero-side">' +
          '<div class="ch-stat"><div class="num">' + course.totalLessons + '</div><div class="cap">总课时</div></div>' +
          '<div class="ch-stat"><div class="num">' + prog.done + '</div><div class="cap">已完成</div></div>' +
          '<div class="ch-stat"><div class="num">' + prog.pct + '%</div><div class="cap">完成率</div></div>' +
        '</div>' +
      '</section>' +

      '<div class="level-tabs reveal" style="--d:100ms">' + tabs + '</div>' +

      '<div class="unit-list reveal" style="--d:140ms">' +
        '<div class="section-head"><div><div class="section-title">' + level.code + ' · ' + U.esc(level.title) + '</div>' +
          '<div class="section-sub">' + level.units.length + ' 个单元 · ' + levelStats(level, s).total + ' 节课</div></div>' +
          '<span class="tag tag-green">' + levelStats(level, s).done + ' / ' + levelStats(level, s).total + ' 已完成</span></div>' +
        units +
      '</div>' +

      '<div class="learn-foot"><span>' + meta.native + ' · ' + U.esc(meta.tagline) + '</span>' +
        '<a class="link-more" href="#/learn?lesson=' + cur.id + '">继续当前课程' + Icon('chevron-right', 14) + '</a></div>';
  }

  function mount(root) {
    root.onclick = function (e) {
      var tab = e.target.closest('[data-level]');
      if (!tab) return;
      levelIndex = parseInt(tab.getAttribute('data-level'), 10) || 0;
      APP.rerender();
    };
  }

  window.Views = window.Views || {};
  window.Views.courses = { render: render, mount: mount };
})();
