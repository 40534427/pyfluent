/* Lingua · 学习进度追踪 */
(function () {
  function shortDate(date) {
    var p = String(date).split('-');
    return p.length === 3 ? (parseInt(p[1], 10) + '/' + parseInt(p[2], 10)) : date;
  }

  function render() {
    var s = Store.get();
    var meta = DB.langMeta(s.lang);
    var days30 = Store.historyDays(30);
    var values = days30.map(function (d) { return d.minutes; });
    var labels = days30.map(function (d, i) {
      return (i % 5 === 0 || i === days30.length - 1) ? shortDate(d.date) : '';
    });
    var sum30 = values.reduce(function (a, b) { return a + b; }, 0);
    var max30 = values.length ? Math.max.apply(null, values) : 0;
    var skills = Store.skillList(s.lang);
    var lv = Store.levelInfo();
    var cur = Store.currentLesson(s.lang);
    var history = Store.historyDays(84);

    var recent = [];
    if (cur && s.completedLessons.indexOf(cur.id) < 0) recent.push({ lesson: cur, done: Store.lessonModulesDone(cur.id) });
    s.completedLessons.slice().reverse().forEach(function (id) {
      var l = DB.findLesson(s.lang, id);
      if (l) recent.push({ lesson: l, done: 4 });
    });
    recent = recent.slice(0, 5);

    var recentRows = recent.map(function (r) {
      var pct = Math.round(r.done / 4 * 100);
      return '<div class="recent-row"><span class="rr-icon">' + Icon(r.done >= 4 ? 'check-circle' : 'target', 15) + '</span>' +
        '<div class="rr-body"><div class="rr-title">' + U.esc(r.lesson.title) + '</div>' +
        '<div class="rr-meta">' + r.lesson.levelCode + ' · ' + U.esc(r.lesson.unitTitle) + '</div></div>' +
        '<span class="rr-pct">' + r.done + ' / 4</span>' +
        '<span class="tag ' + (r.done >= 4 ? 'tag-green' : 'tag-amber') + '">' + (r.done >= 4 ? '已完成' : pct + '%') + '</span></div>';
    }).join('');

    var langCards = DB.langs.map(function (l) {
      var p = Store.courseProgress(l.id);
      var active = l.id === s.lang;
      return '<div class="card card-pad">' +
        '<div class="section-head"><div><div class="section-title">' + l.native + ' · ' + l.name + '</div>' +
          '<div class="section-sub">' + p.done + ' / ' + p.total + ' 节已完成</div></div>' +
          (active ? '<span class="tag tag-green">当前学习</span>' : '<span class="tag tag-flat">' + l.badge + '</span>') + '</div>' +
        '<div class="progress' + (active ? '' : '') + '" style="margin-top:14px"><span style="width:' + p.pct + '%"></span></div>' +
      '</div>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">INSIGHTS · 学习进度</div><h1>学习进度追踪</h1>' +
          '<p class="sub">' + meta.name + '学习数据 · 近 30 天与能力维度全景</p></div>' +
        '<div class="head-actions"><a class="btn btn-ghost" href="#/courses">' + Icon('book-open', 16) + '回到课程</a>' +
          '<a class="btn btn-primary" href="#/path">' + Icon('compass', 16) + '规划下一步</a></div>' +
      '</div>' +

      '<div class="summary-grid reveal" style="--d:50ms">' +
        '<div class="card summary-card"><div class="sc-top"><span class="sc-icon">' + Icon('clock', 17) + '</span><span class="tag tag-mono">累计</span></div>' +
          '<div class="sc-num">' + U.fmt(s.totalMinutes) + '<small> 分钟</small></div><div class="sc-cap">累计学习时长</div></div>' +
        '<div class="card summary-card"><div class="sc-top"><span class="sc-icon">' + Icon('flame', 17) + '</span><span class="tag tag-red">持续中</span></div>' +
          '<div class="sc-num">' + s.streak + '<small> 天</small></div><div class="sc-cap">连续学习天数</div></div>' +
        '<div class="card summary-card"><div class="sc-top"><span class="sc-icon">' + Icon('layers', 17) + '</span><span class="tag tag-green">三语</span></div>' +
          '<div class="sc-num">' + U.fmt(Store.totalWords()) + '<small> 词</small></div><div class="sc-cap">已掌握词汇</div></div>' +
        '<div class="card summary-card"><div class="sc-top"><span class="sc-icon">' + Icon('graduation-cap', 17) + '</span><span class="tag tag-amber">' + meta.badge + '</span></div>' +
          '<div class="sc-num">' + s.completedLessons.length + '<small> 节</small></div><div class="sc-cap">已完成课程</div></div>' +
      '</div>' +

      '<div class="progress-grid reveal" style="--d:90ms">' +
        '<section class="card chart-card">' +
          '<div class="chart-head"><div><div class="section-title">近 30 天学习时长</div><div class="section-sub">每日专注分钟数</div></div>' +
            '<span class="tag tag-green">日均 ' + Math.round(sum30 / 30) + ' MIN</span></div>' +
          Charts.line(values, labels, { height: 210 }) +
          '<div class="chart-foot"><span>合计 <strong>' + sum30 + '</strong> 分钟</span><span>单日峰值 <strong>' + max30 + '</strong> 分钟</span></div>' +
        '</section>' +
        '<section class="card chart-card">' +
          '<div class="chart-head"><div><div class="section-title">能力雷达</div><div class="section-sub">' + meta.native + '四项核心能力</div></div></div>' +
          '<div class="radar-wrap">' + Charts.radar(skills) + '</div>' +
          '<div class="chart-foot"><span>弱项 <strong>' + U.esc(Store.weakestSkill(s.lang).label) + '</strong></span><span>建议专项练习</span></div>' +
        '</section>' +
      '</div>' +

      '<section class="card heat-card reveal" style="--d:120ms">' +
        '<div class="section-head"><div><div class="section-title">学习热力图</div><div class="section-sub">近 12 周 · 每天的学习分钟数</div></div>' +
          '<div class="heat-legend"><span>少</span><span class="lg-cell heat-0"></span><span class="lg-cell heat-1"></span><span class="lg-cell heat-2"></span><span class="lg-cell heat-3"></span><span class="lg-cell heat-4"></span><span>多</span></div></div>' +
        Charts.heatmap(history) +
      '</section>' +

      '<div class="progress-lower reveal" style="--d:150ms">' +
        '<section class="card level-card">' +
          '<div class="lv-top"><div class="level-orb"><span class="lv-no">' + lv.level + '</span><span class="lv-cap">LEVEL</span></div>' +
            '<div><div class="lv-name">语言旅人 · LV ' + lv.level + '</div>' +
            '<div class="lv-xp">' + U.fmt(s.xp) + ' XP · 距下一级还差 ' + (lv.need - lv.into) + ' XP</div></div></div>' +
          '<div class="progress"><span style="width:' + lv.pct + '%"></span></div>' +
          '<div class="lv-foot"><span>' + lv.into + ' / ' + lv.need + ' XP</span><span>' + lv.pct + '%</span></div>' +
        '</section>' +
        '<section class="card recent-card">' +
          '<div class="section-head"><div><div class="section-title">最近学习</div><div class="section-sub">按模块完成度追踪</div></div>' +
            '<a class="link-more" href="#/courses">课程目录' + Icon('chevron-right', 14) + '</a></div>' +
          (recentRows || '<div class="section-sub">还没有学习记录，先去完成第一节课吧。</div>') +
        '</section>' +
      '</div>' +

      '<div class="lang-grid reveal" style="--d:180ms">' + langCards + '</div>';
  }

  window.Views = window.Views || {};
  window.Views.progress = { render: render };
})();
