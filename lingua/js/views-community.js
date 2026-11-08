/* Lingua · 社区交流 */
(function () {
  var filter = 'all';
  var topic = '';
  var openComments = {};
  var publishing = false;

  var TABS = [['all', '全部'], ['en', '英语'], ['ja', '日语'], ['ko', '韩语']];

  function allPosts() {
    return Store.get().posts.concat(DB.posts);
  }

  function visiblePosts() {
    return allPosts().filter(function (p) {
      if (filter !== 'all' && p.lang !== filter) return false;
      if (topic && p.tag !== topic) return false;
      return true;
    });
  }

  function commentHTML(c, lang) {
    return '<div class="comment">' + U.avatar(c.author, lang) +
      '<div class="c-body"><div class="c-name">' + U.esc(c.author) + '</div><div class="c-text">' + U.esc(c.text) + '</div></div></div>';
  }

  function postHTML(p) {
    var comments = Store.commentsOf(p);
    var liked = Store.isLiked(p.id);
    var open = !!openComments[p.id];
    return '<article class="card post">' +
      '<div class="post-head">' + U.avatar(p.author, p.lang) +
        '<div class="post-meta"><div class="post-name">' + U.esc(p.author) +
          (p.badge ? '<span class="tag tag-mono">' + U.esc(p.badge) + '</span>' : '') + '</div>' +
          '<div class="post-sub">' + U.esc(p.time) + ' · ' + U.esc(p.tag) + '</div></div>' +
      '</div>' +
      '<div class="post-body">' + U.esc(p.content) + '</div>' +
      (p.lesson ? '<span class="post-lesson">' + Icon('book-marked', 12) + U.esc(p.lesson) + '</span>' : '') +
      '<div class="post-actions">' +
        '<button class="action-btn' + (liked ? ' liked' : '') + '" type="button" data-like="' + p.id + '">' + Icon('heart', 15) + '<span>' + Store.likeCount(p) + '</span></button>' +
        '<button class="action-btn" type="button" data-comments="' + p.id + '">' + Icon('message-circle', 15) + '<span>' + comments.length + '</span></button>' +
        '<button class="action-btn" type="button" data-share="' + p.id + '">' + Icon('send', 15) + '<span>分享</span></button>' +
      '</div>' +
      (open ? '<div class="comments">' + comments.map(function (c) { return commentHTML(c, p.lang); }).join('') +
        '<form class="comment-form" data-comment-form="' + p.id + '">' +
          '<input type="text" maxlength="120" placeholder="写下你的想法…" aria-label="评论内容">' +
          '<button type="submit" aria-label="发送评论">' + Icon('send', 14) + '</button>' +
        '</form></div>' : '') +
    '</article>';
  }

  function leaderRows(s) {
    var rows = DB.leaderboard.filter(function (r) { return !r.me; }).map(function (r) {
      return { name: r.name, xp: r.xp, lang: r.lang };
    });
    rows.push({ name: s.user.name, xp: s.xp, lang: s.lang, me: true });
    rows.sort(function (a, b) { return b.xp - a.xp; });
    return rows.slice(0, 7).map(function (r, i) {
      return '<div class="lb-row' + (r.me ? ' me' : '') + '">' +
        '<span class="lb-rank">' + String(i + 1).padStart(2, '0') + '</span>' +
        U.avatar(r.name, r.lang) +
        '<span class="lb-name">' + U.esc(r.name) + (r.me ? '（我）' : '') + '</span>' +
        '<span class="lb-xp">' + U.fmt(r.xp) + ' XP</span></div>';
    }).join('');
  }

  function render() {
    var s = Store.get();
    var posts = visiblePosts();
    var tabs = TABS.map(function (t) {
      return '<button class="feed-tab' + (filter === t[0] ? ' active' : '') + '" type="button" data-filter="' + t[0] + '">' + t[1] + '</button>';
    }).join('');
    var langOptions = DB.langs.map(function (l) {
      return '<option value="' + l.id + '"' + (l.id === s.lang ? ' selected' : '') + '>' + l.name + ' · ' + l.native + '</option>';
    }).join('');
    var topics = DB.topics.map(function (t) {
      var on = topic === t.tag;
      return '<button class="topic-chip' + (on ? ' active' : '') + '" type="button" data-topic="' + U.esc(t.tag) + '"' + (on ? ' style="border-color:var(--green);color:var(--green)"' : '') + '>' +
        U.esc(t.tag) + '<span class="cnt">' + t.count + '</span></button>';
    }).join('');

    return '' +
      '<div class="page-head reveal">' +
        '<div><div class="eyebrow">COMMUNITY · 社区交流</div><h1>和同路人一起学习</h1>' +
          '<p class="sub">' + DB.posts.length + ' 条真实学习动态 · 分享方法、记录打卡、寻找语伴</p></div>' +
        '<div class="head-actions"><span class="tag tag-green">' + Icon('users', 12) + DB.leaderboard.length + ' 位活跃学习者</span></div>' +
      '</div>' +

      '<div class="community-grid reveal" style="--d:60ms">' +
        '<div>' +
          '<section class="card composer">' +
            '<div class="composer-top">' + U.avatar(s.user.name, s.lang) +
              '<div class="composer-body">' +
                '<textarea id="composerInput" maxlength="200" placeholder="分享今天的学习心得、方法或问题…"></textarea>' +
                '<div class="composer-foot">' +
                  '<select class="lang-select" id="composerLang" aria-label="动态语言">' + langOptions + '</select>' +
                  '<span class="count" id="composerCount">0 / 200</span>' +
                  '<button class="btn btn-primary btn-sm" type="button" data-publish>' + Icon('send', 14) + '发布</button>' +
                '</div>' +
              '</div>' +
            '</div>' +
          '</section>' +

          '<div class="feed-tabs" style="margin-top:16px">' + tabs + '</div>' +
          '<div class="feed">' +
            (posts.length ? posts.map(postHTML).join('') : '<div class="card card-pad"><div class="section-sub">还没有匹配的动态，换个筛选看看。</div></div>') +
          '</div>' +
        '</div>' +

        '<aside class="rail">' +
          '<div class="card rail-card"><h3>' + Icon('crown', 17) + '本周学习榜</h3><div class="rail-sub">按累计经验值排名</div>' +
            '<div style="margin-top:10px">' + leaderRows(s) + '</div></div>' +
          '<div class="card rail-card"><h3>' + Icon('compass', 17) + '热门话题</h3><div class="rail-sub">点击标签筛选动态</div>' +
            '<div class="topic-list">' + topics + '</div></div>' +
          '<div class="card rail-card"><h3>' + Icon('heart', 17) + '社区公约</h3>' +
            '<ul class="guideline">' +
              '<li>' + Icon('check-circle', 13) + '<span>分享真实的学习体验，不发布广告与无关内容</span></li>' +
              '<li>' + Icon('check-circle', 13) + '<span>友善讨论，尊重不同水平的学习者</span></li>' +
              '<li>' + Icon('check-circle', 13) + '<span>提问时附上上下文，更容易得到帮助</span></li>' +
            '</ul></div>' +
        '</aside>' +
      '</div>';
  }

  function publish(root) {
    if (publishing) return;
    var input = root.querySelector('#composerInput');
    var text = input ? input.value.trim() : '';
    if (text.length < 4) { APP.toast('再多写几个字吧', 'error'); return; }
    var select = root.querySelector('#composerLang');
    var lang = select ? select.value : Store.get().lang;
    publishing = true;
    setTimeout(function () { publishing = false; }, 600);
    Store.addPost({ content: text, lang: lang });
    Store.addXp(10);
    APP.refreshChrome();
    APP.toast('动态已发布 · +10 XP');
    filter = 'all';
    topic = '';
    APP.rerender();
  }

  function mount(root) {
    root.onclick = function (e) {
      var like = e.target.closest('[data-like]');
      if (like) { Store.toggleLike(like.getAttribute('data-like')); APP.rerender(); return; }

      var cm = e.target.closest('[data-comments]');
      if (cm) {
        var pid = cm.getAttribute('data-comments');
        openComments[pid] = !openComments[pid];
        APP.rerender();
        return;
      }

      if (e.target.closest('[data-share]')) { APP.toast('动态链接已复制（演示）'); return; }

      var tab = e.target.closest('[data-filter]');
      if (tab) { filter = tab.getAttribute('data-filter'); topic = ''; APP.rerender(); return; }

      var tp = e.target.closest('[data-topic]');
      if (tp) {
        var tag = tp.getAttribute('data-topic');
        topic = topic === tag ? '' : tag;
        filter = 'all';
        APP.rerender();
        return;
      }

      if (e.target.closest('[data-publish]')) { publish(root); return; }
    };

    root.oninput = function (e) {
      if (e.target.id === 'composerInput') {
        var count = root.querySelector('#composerCount');
        if (count) count.textContent = e.target.value.length + ' / 200';
      }
    };

    root.onsubmit = function (e) {
      var form = e.target.closest('[data-comment-form]');
      if (!form) return;
      e.preventDefault();
      var input = form.querySelector('input');
      var text = input ? input.value.trim() : '';
      if (!text) { APP.toast('评论不能为空', 'error'); return; }
      Store.addComment(form.getAttribute('data-comment-form'), text);
      openComments[form.getAttribute('data-comment-form')] = true;
      APP.toast('评论已发布');
      APP.rerender();
    };
  }

  window.Views = window.Views || {};
  window.Views.community = { render: render, mount: mount };
})();
