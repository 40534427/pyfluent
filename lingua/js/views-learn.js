/* Lingua · 互动学习（单词 / 语法 / 口语 / 听力） */
(function () {
  var ORDER = ['word', 'grammar', 'speaking', 'listening'];
  var mode = 'word';

  var wordIdx = 0, flipped = false, wordKnown = 0;
  var quizIdx = 0, picked = null, correct = 0;
  var speakIdx = 0, phase = 'idle', score = 0, attempt = 0;
  var listenIdx = 0, listenPicked = null, playing = false;
  var showDone = false;

  var lastHash = null, lastLessonKey = null;
  var recTimer = null, playTimer = null;

  function ctx() {
    var s = Store.get();
    var lang = s.lang;
    var lesson = null;
    if (APP.params && APP.params.lesson) lesson = DB.findLesson(lang, APP.params.lesson);
    if (!lesson) lesson = Store.currentLesson(lang);
    return { s: s, lang: lang, meta: DB.langMeta(lang), lesson: lesson, deck: DB.decks[lang], course: DB.courses[lang] };
  }

  function clearTimers() {
    if (recTimer) { clearTimeout(recTimer); recTimer = null; }
    if (playTimer) { clearTimeout(playTimer); playTimer = null; }
  }

  function ensure(c) {
    var hashNow = location.hash;
    var key = c.lang + '|' + c.lesson.id;
    if (hashNow === lastHash && key === lastLessonKey) return;
    clearTimers();
    wordIdx = 0; flipped = false; wordKnown = 0;
    quizIdx = 0; picked = null; correct = 0;
    speakIdx = 0; phase = 'idle'; score = 0; attempt = 0;
    listenIdx = 0; listenPicked = null; playing = false;
    showDone = false;
    var pm = (APP.params && APP.params.mode) || APP.sub;
    if (ORDER.indexOf(pm) >= 0) mode = pm;
    lastHash = hashNow;
    lastLessonKey = key;
  }

  function resetModule(k) {
    if (k === 'word') { wordIdx = 0; flipped = false; wordKnown = 0; }
    if (k === 'grammar') { quizIdx = 0; picked = null; correct = 0; }
    if (k === 'speaking') { speakIdx = 0; phase = 'idle'; score = 0; attempt = 0; }
    if (k === 'listening') { listenIdx = 0; listenPicked = null; playing = false; }
  }

  function complete(c, keyName, opts, label) {
    clearTimers();
    var p = Store.get().lessonProgress[c.lesson.id] || {};
    var next = null;
    ORDER.forEach(function (k) { if (!next && k !== keyName && !p[k]) next = k; });
    if (!next) next = 'word';
    var res = Store.markModule(c.lesson.id, keyName, opts);
    APP.refreshChrome();
    APP.toast(label + '完成 · +' + res.earned + ' XP');
    if (res.allDone) {
      showDone = true;
      playing = false;
      phase = 'idle';
    } else {
      mode = next;
      resetModule(next);
    }
    APP.rerender();
  }

  function speakText(text, lang) {
    if (!APP.speak(text, lang)) APP.toast('当前浏览器不支持语音合成，可参考文字提示', 'error');
  }

  function render() {
    var c = ctx();
    ensure(c);
    var done = Store.lessonModulesDone(c.lesson.id);

    var dots = ['word', 'grammar', 'speaking', 'listening'].map(function (k) {
      var p = Store.get().lessonProgress[c.lesson.id] || {};
      return '<span class="dot' + (p[k] ? ' done' : (k === mode && !showDone ? ' active' : '')) + '"></span>';
    }).join('');

    var tabs = DB.modes.map(function (m) {
      var p = Store.get().lessonProgress[c.lesson.id] || {};
      return '<button class="mode-tab' + (m.key === mode && !showDone ? ' active' : '') + '" type="button" data-mode="' + m.key + '">' +
        Icon(m.icon, 15) + '<span>' + m.name + '</span>' +
        (p[m.key] ? '<span class="mini-check">' + Icon('check', 11) + '</span>' : '') +
      '</button>';
    }).join('');

    var panel = showDone ? donePanel(c) :
      mode === 'word' ? wordPanel(c) :
      mode === 'grammar' ? grammarPanel(c) :
      mode === 'speaking' ? speakingPanel(c) : listeningPanel(c);

    return '<div class="learn-wrap">' +
      '<div class="learn-head">' +
        '<a class="icon-btn" href="#/courses" aria-label="返回课程目录">' + Icon('arrow-left', 18) + '</a>' +
        '<div class="learn-head-main">' +
          '<div class="eyebrow">LESSON · ' + c.meta.badge + ' ' + c.lesson.levelCode + '</div>' +
          '<h1>' + U.esc(c.lesson.title) + '</h1>' +
          '<div class="lh-sub">' + c.meta.name + ' · ' + U.esc(c.lesson.unitTitle) + ' · 约 ' + c.lesson.minutes + ' 分钟</div>' +
        '</div>' +
        '<div class="module-dots" title="四个模块的完成情况">' + dots + '</div>' +
      '</div>' +
      '<div class="mode-tabs" role="tablist" aria-label="学习模块">' + tabs + '</div>' +
      '<div class="learn-panel">' + panel + '</div>' +
      '<div class="learn-foot"><span>' + c.meta.native + ' · ' + U.esc(c.lesson.unitTitle) + ' · 已完成 ' + done + ' / 4 模块</span>' +
        '<a class="link-more" href="#/courses">返回课程目录' + Icon('chevron-right', 14) + '</a></div>' +
    '</div>';
  }

  function wordPanel(c) {
    var words = c.deck.words;
    var i = Math.min(wordIdx, words.length - 1);
    var w = words[i];
    var pct = Math.round((i + 1) / words.length * 100);
    return '' +
      '<div class="panel-head"><div><h2>单词记忆</h2><div class="ph-sub">翻卡记忆 · 三档自评</div></div>' +
        '<div class="speak-controls" style="margin:0;gap:8px">' +
          '<button class="btn btn-ghost btn-sm" type="button" data-say="word">' + Icon('volume-2', 14) + '朗读</button>' +
          '<span class="panel-count">' + (i + 1) + ' / ' + words.length + '</span>' +
        '</div></div>' +
      '<div class="flash-progress"><div class="fp-top"><span>WORD ' + String(i + 1).padStart(2, '0') + '</span><span>' + c.meta.native + ' · 词汇</span></div>' +
        '<div class="progress"><span style="width:' + pct + '%"></span></div></div>' +
      '<div class="flashcard' + (flipped ? ' flipped' : '') + '" data-act="flip" role="button" tabindex="0" aria-label="翻转单词卡">' +
        '<div class="flashcard-inner">' +
          '<div class="flashcard-face flashcard-front">' +
            '<span class="fc-tag">' + c.meta.badge + ' · WORD</span>' +
            '<div class="word-term">' + U.esc(w.term) + '</div>' +
            '<div class="word-ipa">' + U.esc(w.ipa) + '</div>' +
            '<span class="flip-hint">' + Icon('rotate-ccw', 12) + '点击卡片查看释义</span>' +
          '</div>' +
          '<div class="flashcard-face flashcard-back">' +
            '<div class="word-meaning">' + U.esc(w.meaning) + '</div>' +
            '<div class="word-example">“' + U.esc(w.example) + '”</div>' +
            '<div class="word-example-cn">' + U.esc(w.exampleCn) + '</div>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="rating-row">' +
        '<button class="btn btn-ghost" type="button" data-rate="0">不认识<small>再来一次</small></button>' +
        '<button class="btn btn-soft" type="button" data-rate="1">有点模糊<small>稍后复习</small></button>' +
        '<button class="btn btn-primary" type="button" data-rate="2">记住了<small>加入已掌握</small></button>' +
      '</div>';
  }

  function grammarPanel(c) {
    var list = c.deck.grammar;
    var i = Math.min(quizIdx, list.length - 1);
    var item = list[i];
    var q = U.esc(item.q).replace(/___/g, '<span class="blank">___</span>');
    var opts = item.options.map(function (opt, oi) {
      var cls = 'option';
      if (picked !== null) {
        if (oi === item.answer) cls += ' correct';
        else if (oi === picked) cls += ' wrong';
        else cls += ' dim';
      }
      return '<button class="' + cls + '" type="button" data-opt="' + oi + '"' + (picked !== null ? ' disabled' : '') + '>' +
        '<span class="option-letter">' + String.fromCharCode(65 + oi) + '</span><span>' + U.esc(opt) + '</span></button>';
    }).join('');

    var feedback = '';
    if (picked !== null) {
      feedback = '<div class="explain"><strong>' + (picked === item.answer ? '答对了' : '再想想') + '</strong>：' + U.esc(item.explain) + '</div>' +
        '<div class="quiz-foot"><span class="quiz-score">已答对 ' + correct + ' / ' + list.length + '</span>' +
        '<button class="btn btn-primary btn-sm" type="button" data-next>' + (i === list.length - 1 ? '完成练习' : '下一题') + Icon('chevron-right', 14) + '</button></div>';
    } else {
      feedback = '<div class="quiz-foot"><span class="quiz-score">选择你认为正确的答案</span></div>';
    }

    return '<div class="panel-head"><div><h2>语法练习</h2><div class="ph-sub">逐题作答 · 即时解析</div></div>' +
        '<span class="panel-count">' + (i + 1) + ' / ' + list.length + '</span></div>' +
      '<div class="quiz-wrap"><div class="quiz-q">' + q + '</div><div class="options">' + opts + '</div>' + feedback + '</div>';
  }

  function speakingPanel(c) {
    var list = c.deck.speaking;
    var i = speakIdx % list.length;
    var item = list[i];
    var wave = '<div class="wave' + (phase === 'recording' ? ' recording' : phase === 'result' ? ' playing' : '') + '">' +
      Array.apply(null, Array(26)).map(function () { return '<span></span>'; }).join('') + '</div>';

    var controls;
    if (phase === 'result') {
      var acc = Math.min(99, score + 2);
      var flu = Math.max(60, score - 4);
      var com = Math.min(99, score + 5);
      var tokens = item.sentence.indexOf(' ') >= 0 ? item.sentence.split(' ') : item.sentence.split('');
      var chips = tokens.map(function (t, ti) {
        var cls = (ti === tokens.length - 2) ? 'warn' : 'good';
        return '<span class="word-chip ' + cls + '">' + U.esc(t) + '</span>';
      }).join('');
      controls = '<div class="speak-result">' +
        '<div class="score-big">' + score + '<small> 分</small></div>' +
        '<div class="score-metrics">' +
          '<div class="score-metric"><div class="sm-val">' + acc + '</div><div class="sm-cap">准确度</div></div>' +
          '<div class="score-metric"><div class="sm-val">' + flu + '</div><div class="sm-cap">流利度</div></div>' +
          '<div class="score-metric"><div class="sm-val">' + com + '</div><div class="sm-cap">完整度</div></div>' +
        '</div>' +
        '<div class="word-chips">' + chips + '</div>' +
        '<div class="speak-controls">' +
          '<button class="btn btn-ghost" type="button" data-act="redo">' + Icon('rotate-ccw', 15) + '再读一次</button>' +
          '<button class="btn btn-primary" type="button" data-act="finish">完成跟读 +16 XP</button>' +
        '</div>' +
        (attempt > 1 ? '<div class="speak-hint">第 ' + attempt + ' 次尝试 · 分数随熟练度提升</div>' : '<div class="speak-hint">演示评分为模拟结果，不采集真实录音</div>') +
      '</div>';
    } else {
      controls = '<div class="speak-controls">' +
          '<button class="btn btn-ghost btn-sm" type="button" data-say="sentence">' + Icon('volume-2', 15) + '听示范</button>' +
          '<button class="record-btn' + (phase === 'recording' ? ' recording' : '') + '" type="button" data-act="record" aria-label="开始跟读录音">' +
            Icon(phase === 'recording' ? 'pause' : 'mic', 30) +
          '</button>' +
          '<button class="btn btn-ghost btn-sm" type="button" data-act="skip">换一句</button>' +
        '</div>' +
        '<div class="speak-hint">' + (phase === 'recording' ? '正在录音… 请完整读出这句话' : '点击麦克风开始跟读，录音约 2 秒（演示评分）') + '</div>';
    }

    return '<div class="panel-head"><div><h2>口语跟读</h2><div class="ph-sub">听示范 · 跟读 · 立即评分</div></div>' +
        '<span class="panel-count">' + (i + 1) + ' / ' + list.length + '</span></div>' +
      '<div class="speak-card">' +
        '<div class="speak-sentence">' + U.esc(item.sentence) + '</div>' +
        '<div class="speak-translation">' + U.esc(item.translation) + '</div>' +
        '<div class="speak-tip">' + Icon('lightbulb', 14) + '<span>' + U.esc(item.tip) + '</span></div>' +
        wave + controls +
      '</div>';
  }

  function listeningPanel(c) {
    var list = c.deck.listening;
    var i = listenIdx % list.length;
    var item = list[i];
    var eq = Array.apply(null, Array(30)).map(function () { return '<span></span>'; }).join('');

    var opts = item.options.map(function (opt, oi) {
      var cls = 'option';
      if (listenPicked !== null) {
        if (oi === item.answer) cls += ' correct';
        else if (oi === listenPicked) cls += ' wrong';
        else cls += ' dim';
      }
      return '<button class="' + cls + '" type="button" data-opt="' + oi + '"' + (listenPicked !== null ? ' disabled' : '') + '>' +
        '<span class="option-letter">' + String.fromCharCode(65 + oi) + '</span><span>' + U.esc(opt) + '</span></button>';
    }).join('');

    var foot = listenPicked !== null
      ? '<div class="quiz-foot"><span class="quiz-score">' + (listenPicked === item.answer ? '听力准确' : '正确答案是 ' + String.fromCharCode(65 + item.answer)) + '</span>' +
        '<button class="btn btn-primary btn-sm" type="button" data-next>' + (i === list.length - 1 ? '完成训练' : '下一题') + Icon('chevron-right', 14) + '</button></div>'
      : '<div class="quiz-foot"><span class="quiz-score">先听两遍，再选择答案</span></div>';

    var transcript = listenPicked !== null
      ? '<div class="transcript"><div class="tr-label">TRANSCRIPT</div><div class="tr-text">' + U.esc(item.transcript) + '</div><div class="tr-cn">' + U.esc(item.translation) + '</div></div>'
      : '';

    return '<div class="panel-head"><div><h2>听力训练</h2><div class="ph-sub">真实场景听力 · 理解关键信息</div></div>' +
        '<span class="panel-count">' + (i + 1) + ' / ' + list.length + '</span></div>' +
      '<div class="listening-card">' +
        '<div class="player' + (playing ? ' playing' : '') + '">' +
          '<button class="play-btn" type="button" data-act="play" aria-label="' + (playing ? '停止播放' : '播放音频') + '">' + Icon(playing ? 'pause' : 'play', 20) + '</button>' +
          '<div class="equalizer">' + eq + '</div>' +
          '<div class="player-meta"><div class="pm-label">LISTEN</div><div class="pm-time">0:0' + (4 + i) + '</div></div>' +
        '</div>' +
        '<div class="listen-question">' + U.esc(item.question) + '</div>' +
        '<div class="options">' + opts + '</div>' +
        transcript + foot +
      '</div>';
  }

  function donePanel(c) {
    var list = DB.lessonList(c.lang);
    var idx = -1;
    list.forEach(function (l, i) { if (l.id === c.lesson.id) idx = i; });
    var next = list[Math.min(list.length - 1, idx + 1)];
    var mods = ['word', 'grammar', 'speaking', 'listening'].map(function (k) {
      var name = { word: '单词', grammar: '语法', speaking: '口语', listening: '听力' }[k];
      return '<span class="dm ok">' + Icon('check-circle', 13) + name + '</span>';
    }).join('');
    return '<div class="done-card">' +
      '<div class="done-seal">' + Icon('trophy', 36) + '</div>' +
      '<h2>本节课完成</h2>' +
      '<p class="done-sub">四个模块全部打卡，课程已计入学习进度</p>' +
      '<div class="done-xp">' + Icon('zap', 14) + '+30 XP 完成奖励</div>' +
      '<div class="done-mods">' + mods + '</div>' +
      '<div class="done-actions">' +
        '<a class="btn btn-primary" href="#/courses">返回课程目录</a>' +
        '<a class="btn btn-ghost" href="#/learn?lesson=' + next.id + '">下一课：' + U.esc(next.title.split(' · ')[0]) + '</a>' +
      '</div>' +
    '</div>';
  }

  function mount(root) {
    root.onclick = function (e) {
      var c = ctx();

      var modeBtn = e.target.closest('[data-mode]');
      if (modeBtn) {
        mode = modeBtn.getAttribute('data-mode');
        resetModule(mode);
        showDone = false;
        APP.rerender();
        return;
      }

      var act = e.target.closest('[data-act]');
      if (act) {
        var kind = act.getAttribute('data-act');
        if (kind === 'flip') {
          act.classList.toggle('flipped');
          flipped = act.classList.contains('flipped');
          return;
        }
        if (kind === 'record') {
          if (phase === 'recording') return;
          phase = 'recording';
          attempt += 1;
          APP.rerender();
          clearTimers();
          recTimer = setTimeout(function () {
            if (APP.route !== 'learn' || mode !== 'speaking') return;
            var item = c.deck.speaking[speakIdx % c.deck.speaking.length];
            phase = 'result';
            score = Math.min(95, 72 + (item.sentence.length % 9) + (attempt > 1 ? 4 : 0) + (speakIdx % 3));
            APP.rerender();
          }, 2200);
          return;
        }
        if (kind === 'redo') {
          phase = 'idle';
          score = 0;
          APP.rerender();
          return;
        }
        if (kind === 'skip') {
          speakIdx = (speakIdx + 1) % c.deck.speaking.length;
          phase = 'idle';
          score = 0;
          APP.rerender();
          return;
        }
        if (kind === 'finish') {
          complete(c, 'speaking', { skill: 'speaking', gain: 4, xp: 16, score: score }, '口语跟读');
          return;
        }
        if (kind === 'play') {
          if (playing) {
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            playing = false;
            clearTimers();
            APP.rerender();
            return;
          }
          var item = c.deck.listening[listenIdx % c.deck.listening.length];
          var ok = APP.speak(item.text, c.lang);
          if (!ok) APP.toast('当前浏览器不支持语音合成，可参考文字稿', 'error');
          playing = true;
          APP.rerender();
          clearTimers();
          playTimer = setTimeout(function () {
            playing = false;
            if (APP.route === 'learn') APP.rerender();
          }, 3800);
          return;
        }
      }

      var say = e.target.closest('[data-say]');
      if (say) {
        if (say.getAttribute('data-say') === 'word') {
          speakText(c.deck.words[Math.min(wordIdx, c.deck.words.length - 1)].term, c.lang);
        } else {
          speakText(c.deck.speaking[speakIdx % c.deck.speaking.length].sentence, c.lang);
        }
        return;
      }

      var rate = e.target.closest('[data-rate]');
      if (rate) {
        var val = parseInt(rate.getAttribute('data-rate'), 10);
        if (val === 2) wordKnown += 1;
        if (wordIdx < c.deck.words.length - 1) {
          wordIdx += 1;
          flipped = false;
          APP.rerender();
        } else {
          complete(c, 'word', { words: Math.max(1, wordKnown), skill: 'vocab', gain: 3, xp: 15 }, '单词记忆');
        }
        return;
      }

      var opt = e.target.closest('[data-opt]');
      if (opt) {
        var oi = parseInt(opt.getAttribute('data-opt'), 10);
        if (mode === 'grammar' && picked === null) {
          picked = oi;
          if (oi === c.deck.grammar[Math.min(quizIdx, c.deck.grammar.length - 1)].answer) correct += 1;
          APP.rerender();
        } else if (mode === 'listening' && listenPicked === null) {
          listenPicked = oi;
          APP.rerender();
        }
        return;
      }

      var next = e.target.closest('[data-next]');
      if (next) {
        if (mode === 'grammar') {
          if (quizIdx < c.deck.grammar.length - 1) {
            quizIdx += 1;
            picked = null;
            APP.rerender();
          } else {
            complete(c, 'grammar', { skill: 'grammar', gain: 4, xp: 18, perfectGrammar: correct === c.deck.grammar.length }, '语法练习');
          }
        } else if (mode === 'listening') {
          if (listenIdx < c.deck.listening.length - 1) {
            listenIdx += 1;
            listenPicked = null;
            playing = false;
            APP.rerender();
          } else {
            complete(c, 'listening', { skill: 'listening', gain: 4, xp: 16 }, '听力训练');
          }
        }
      }
    };
  }

  window.Views = window.Views || {};
  window.Views.learn = { render: render, mount: mount };
})();
