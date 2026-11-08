/* Lingua · 学习主页 */
(function () {
  function render() {
    var s = Store.get();
    var meta = DB.langMeta(s.lang);
    var cur = Store.currentLesson(s.lang);
    var lv = Store.levelInfo();
    var doneMods = Store.lessonModulesDone(cur.id);
    var goalPct = s.dailyGoalMin ? Math.min(100, Math.round(s.minutesToday / s.dailyGoalMin * 100)) : 0;
    var remain = Math.max(0, s.dailyGoalMin - s.minutesToday);
    var week = Store.last7();
    var weekTotal = week.reduce(function (a, b) { return a + b.minutes; }, 0);
    var weak = Store.weakestSkill(s.lang);
    var weakMode = { vocab: 'word', grammar: 'grammar', listening: 'listening', speaking: 'speaking' }[weak.key];
    var hour = new Date().getHours();
    var greet = hour < 5 ? '夜深了' : hour < 11 ? '早上好' : hour < 14 ? '中午好' : hour < 19 ? '下午好' : '晚上好';
    var dateStr = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' });

    var unlocked = DB.achievements.filter(function (a) { return a.current(s) >= a.goal; });
    var nextBadges = DB.achievements.filter(function (a) { return a.current(s) < a.goal; });
    var recent = unlocked.slice(-5);
    var nextShow = nextBadges.slice(0, Math.max(0, 5 - recent.length));
    var labels = week.map(function (d) { return d.isToday ? '今天' : d.label; });

    var dots = ['word', 'grammar', 'speaking', 'listening'].map(function (k) {
      var p = s.lessonProgress[cur.id] || {};
      return '<span class="dot' + (p[k] ? ' done' : '') + '"></span>';
    }).join('');

    var badgeStrip = recent.concat(nextShow).map(function (a) {
      var got = a.current(s) >= a.goal;
      return '<span class="badge-mini' + (got ? '' : ' locked next') + '" title="' + U.esc(a.name) + ' · ' + U.esc(a.desc) + '">' + Icon(a.icon, 22) + '</span>';
    }).join('');

    var miniFeed = DB.posts.slice(0, 3).map(function (p) {
      return '<div class="mini-post">' + U.avatar(p.author, p.lang) +
        '<div class="mp-body"><div class="mp-meta">' + U.esc(p.author) + ' · ' + U.esc(p.time) + '</div><div class="mp-text">' + U.esc(p.content) + '</div></div></div>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">DASHBOARD · 今日学习</div><h1>' + greet + '，' + U.esc(s.user.name) + '</h1>' +
          '<p class="sub">' + dateStr + ' · 已连续学习 ' + s.streak + ' 天，' + (remain > 0 ? '再学 ' + remain + ' 分钟达成今日目标' : '今日目标已达成') + '</p></div>' +
        '<div class="head-actions">' +
          '<a class="btn btn-ghost" href="#/path">' + Icon('compass', 16) + '学习路径</a>' +
          '<a class="btn btn-primary" href="#/learn?lesson=' + cur.id + '">' + Icon('play', 15) + '继续学习</a>' +
        '</div>' +
      '</div>' +

      '<div class="dash-grid reveal" style="--d:60ms">' +
        '<section class="hero-card">' +
          '<div class="hero-copy">' +
            '<div class="hero-eyebrow">' + Icon('sparkles', 13) + "TODAY'S SESSION · " + meta.badge + '</div>' +
            '<h2 class="hero-title">' + U.esc(cur.title) + '</h2>' +
            '<div class="hero-sub">' + meta.name + ' · ' + cur.levelCode + ' · ' + U.esc(cur.unitTitle) + ' · ' + cur.minutes + ' 分钟</div>' +
            '<div class="hero-progress"><div class="dots">' + dots + '</div><span class="cap">' + doneMods + ' / 4 模块完成</span></div>' +
            '<div class="hero-actions">' +
              '<a class="btn btn-amber" href="#/learn?lesson=' + cur.id + '">' + Icon('play', 15) + (doneMods > 0 ? '继续本课' : '开始本课') + '</a>' +
              '<a class="btn hero-ghost" href="#/learn?lesson=' + cur.id + '&mode=word">' + Icon('layers', 15) + '复习单词</a>' +
            '</div>' +
          '</div>' +
          '<div class="hero-side">' + Charts.ring(goalPct, { size: 118, stroke: 10, label: '今日目标', valueText: goalPct + '%' }) +
            '<div class="hero-ring-cap">' + s.minutesToday + ' / ' + s.dailyGoalMin + ' MIN</div></div>' +
        '</section>' +

        '<section class="card goal-card">' +
          '<div class="goal-top"><div><h3>今日目标</h3><div class="goal-sub">保持连续学习的节奏</div></div>' +
            '<span class="tag tag-red">' + Icon('flame', 12) + s.streak + ' 天</span></div>' +
          '<div class="goal-body"><div class="goal-copy">' +
            '<div class="big">' + s.minutesToday + '<small> / ' + s.dailyGoalMin + ' 分钟</small></div>' +
            '<div class="hint">' + (remain > 0 ? '距离今日目标还差 ' + remain + ' 分钟，完成一个模块即可推进。' : '目标已完成，额外的练习也会计入连续打卡。') + '</div>' +
          '</div></div>' +
          '<div class="goal-actions">' +
            '<button class="quick-action" type="button" data-go="#/learn?lesson=' + cur.id + '&mode=word">' + Icon('layers', 15) + '复习单词<span class="qa-min">约 6 分钟</span></button>' +
            '<button class="quick-action" type="button" data-go="#/learn?lesson=' + cur.id + '&mode=speaking">' + Icon('mic', 15) + '口语跟读<span class="qa-min">约 5 分钟</span></button>' +
            '<button class="quick-action" type="button" data-go="#/learn?lesson=' + cur.id + '&mode=listening">' + Icon('headphones', 15) + '听力训练<span class="qa-min">约 7 分钟</span></button>' +
          '</div>' +
        '</section>' +
      '</div>' +

      '<div class="stat-row reveal" style="--d:110ms">' +
        '<div class="card stat-card"><span class="stat-icon red">' + Icon('flame', 19) + '</span><div>' +
          '<div class="stat-value">' + s.streak + ' <small>天</small></div><div class="stat-label">连续打卡</div><div class="stat-delta">今日已打卡</div></div></div>' +
        '<div class="card stat-card"><span class="stat-icon amber">' + Icon('zap', 19) + '</span><div>' +
          '<div class="stat-value">' + U.fmt(s.xp) + ' <small>XP</small></div><div class="stat-label">等级 LV ' + lv.level + '</div><div class="stat-delta">距下一级 ' + (lv.need - lv.into) + ' XP</div></div></div>' +
        '<div class="card stat-card"><span class="stat-icon">' + Icon('layers', 19) + '</span><div>' +
          '<div class="stat-value">' + U.fmt(Store.totalWords()) + ' <small>词</small></div><div class="stat-label">三语掌握词汇</div><div class="stat-delta">今日 +' + s.dailyActions.words + '</div></div></div>' +
        '<div class="card stat-card"><span class="stat-icon ink">' + Icon('clock', 19) + '</span><div>' +
          '<div class="stat-value">' + U.fmt(s.totalMinutes) + ' <small>分钟</small></div><div class="stat-label">累计学习时长</div><div class="stat-delta">本周 ' + weekTotal + ' 分钟</div></div></div>' +
      '</div>' +

      '<div class="dash-lower reveal" style="--d:150ms">' +
        '<section class="card chart-card">' +
          '<div class="chart-head"><div><div class="section-title">本周学习节奏</div><div class="section-sub">每日专注时长 · 分钟</div></div>' +
            '<span class="tag tag-green">' + weekTotal + ' MIN</span></div>' +
          Charts.bars(week.map(function (d) { return d.minutes; }), labels, { height: 190 }) +
          '<div class="chart-foot"><span>日均 <strong>' + Math.round(weekTotal / 7) + '</strong> 分钟</span><span>目标 <strong>' + s.dailyGoalMin + '</strong> 分钟 / 天</span></div>' +
        '</section>' +
        '<section class="card rec-card">' +
          '<div class="section-head"><div><div class="section-title">为你推荐</div><div class="section-sub">基于薄弱项与学习进度生成</div></div></div>' +
          '<div class="rec-list">' +
            '<button class="rec-item" type="button" data-go="#/learn?lesson=' + cur.id + '&mode=' + weakMode + '">' +
              '<span class="rec-icon">' + Icon('target', 17) + '</span>' +
              '<div class="rec-text"><div class="rec-title">补强' + weak.label + '</div><div class="rec-desc">当前 ' + weak.value + ' 分，是四项能力中的短板</div></div>' +
              '<span class="chev">' + Icon('chevron-right', 16) + '</span></button>' +
            '<button class="rec-item" type="button" data-go="#/learn?lesson=' + cur.id + '">' +
              '<span class="rec-icon">' + Icon('book-open', 17) + '</span>' +
              '<div class="rec-text"><div class="rec-title">继续《' + U.esc(cur.title.split(' · ')[0]) + '》</div><div class="rec-desc">' + doneMods + ' / 4 模块已完成，预计 ' + cur.minutes + ' 分钟</div></div>' +
              '<span class="chev">' + Icon('chevron-right', 16) + '</span></button>' +
            '<button class="rec-item" type="button" data-go="#/community">' +
              '<span class="rec-icon">' + Icon('users', 17) + '</span>' +
              '<div class="rec-text"><div class="rec-title">去社区看看</div><div class="rec-desc">' + DB.posts.length + ' 条学习动态，找到同路人</div></div>' +
              '<span class="chev">' + Icon('chevron-right', 16) + '</span></button>' +
          '</div>' +
        '</section>' +
      '</div>' +

      '<div class="strip-grid reveal" style="--d:190ms">' +
        '<section class="card card-pad">' +
          '<div class="section-head"><div><div class="section-title">最近成就</div><div class="section-sub">已解锁 ' + unlocked.length + ' / ' + DB.achievements.length + ' 枚</div></div>' +
            '<a class="link-more" href="#/achievements">全部' + Icon('chevron-right', 14) + '</a></div>' +
          '<div class="badge-strip">' + badgeStrip + '</div>' +
          '<div class="badge-strip-cap">' + (nextBadges.length ? '下一枚：' + U.esc(nextBadges[0].name) + ' · ' + U.esc(nextBadges[0].desc) : '全部成就已解锁，继续保持') + '</div>' +
        '</section>' +
        '<section class="card card-pad">' +
          '<div class="section-head"><div><div class="section-title">社区新鲜事</div><div class="section-sub">同伴的学习现场</div></div>' +
            '<a class="link-more" href="#/community">进入社区' + Icon('chevron-right', 14) + '</a></div>' +
          '<div class="feed-mini">' + miniFeed + '</div>' +
        '</section>' +
      '</div>';
  }

  window.Views = window.Views || {};
  window.Views.dashboard = { render: render };
})();
