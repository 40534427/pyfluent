/* Lingua · 轻量状态层：集中管理会话、学习进度、XP、社区互动，localStorage 持久化 */
(function () {
  const STATE_KEY = 'lingua.state.v1';
  const SESSION_KEY = 'lingua.session.v1';
  const DAY = 86400000;
  let state = null;

  function dateKey(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function todayKey() { return dateKey(new Date()); }
  function yesterdayKey() { return dateKey(new Date(Date.now() - DAY)); }

  function readSession() {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch (e) { return null; }
  }
  function setSession(user) {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ name: user.name, email: user.email, demo: !!user.demo }));
  }
  function clearSession() { localStorage.removeItem(SESSION_KEY); }
  function isLoggedIn() { return !!readSession(); }

  function buildHistory(todayMinutes, rich) {
    const hist = {};
    for (let i = 83; i >= 1; i--) {
      const d = new Date(Date.now() - i * DAY);
      let mins = 0;
      if (rich) {
        const seed = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1;
        if (seed > 0.3) mins = Math.round(8 + seed * 38);
        if (seed > 0.94) mins = 0;
      }
      hist[dateKey(d)] = mins;
    }
    hist[todayKey()] = todayMinutes;
    return hist;
  }

  function demoState(session) {
    return {
      user: { name: session.name || '林知夏', email: session.email, demo: true },
      lang: 'en',
      xp: 2680,
      streak: 12,
      lastActive: todayKey(),
      dailyGoalMin: 30,
      minutesToday: 18,
      totalMinutes: 1460,
      wordsMastered: { en: 128, ja: 42, ko: 17 },
      completedLessons: ['en-a1-u1-l1', 'en-a1-u1-l2', 'en-a1-u1-l3', 'en-a1-u2-l1', 'en-a2-u1-l1', 'ja-n5-u1-l1', 'ko-t1-u1-l1'],
      lessonProgress: { 'en-a1-u2-l2': { word: true } },
      skills: {
        en: { vocab: 72, grammar: 64, listening: 58, speaking: 49 },
        ja: { vocab: 41, grammar: 36, listening: 30, speaking: 25 },
        ko: { vocab: 22, grammar: 18, listening: 16, speaking: 14 }
      },
      history: buildHistory(18, true),
      dailyActions: { speaking: 1, words: 6, lessons: 1 },
      bestSpeaking: 78,
      perfectGrammar: false,
      nightOwl: false,
      posts: [],
      likes: [],
      myComments: {},
      claimed: {},
      path: null
    };
  }

  function freshState(session) {
    const skills = { vocab: 28, grammar: 24, listening: 22, speaking: 20 };
    return {
      user: { name: session.name, email: session.email, demo: false },
      lang: 'en',
      xp: 0,
      streak: 1,
      lastActive: todayKey(),
      dailyGoalMin: 20,
      minutesToday: 0,
      totalMinutes: 0,
      wordsMastered: { en: 0, ja: 0, ko: 0 },
      completedLessons: [],
      lessonProgress: {},
      skills: { en: Object.assign({}, skills), ja: Object.assign({}, skills), ko: Object.assign({}, skills) },
      history: buildHistory(0, false),
      dailyActions: { speaking: 0, words: 0, lessons: 0 },
      bestSpeaking: 0,
      perfectGrammar: false,
      nightOwl: false,
      posts: [],
      likes: [],
      myComments: {},
      claimed: {},
      path: null
    };
  }

  function load() {
    try { return JSON.parse(localStorage.getItem(STATE_KEY) || 'null'); } catch (e) { return null; }
  }
  function save() {
    if (state) localStorage.setItem(STATE_KEY, JSON.stringify(state));
  }

  function init() {
    const session = readSession();
    if (!session) return false;
    const stored = load();
    if (!stored || !stored.user || stored.user.email !== session.email) {
      state = session.demo ? demoState(session) : freshState(session);
      save();
    } else {
      state = stored;
    }
    if (!state.history) state.history = buildHistory(state.minutesToday || 0, true);
    if (!state.dailyActions) state.dailyActions = { speaking: 0, words: 0, lessons: 0 };
    if (typeof state.bestSpeaking !== 'number') state.bestSpeaking = 0;
    if (!state.claimed) state.claimed = {};
    if (!state.myComments) state.myComments = {};
    checkIn();
    return true;
  }

  function checkIn() {
    const today = todayKey();
    if (state.lastActive !== today) {
      state.streak = state.lastActive === yesterdayKey() ? state.streak + 1 : 1;
      state.lastActive = today;
      state.minutesToday = 0;
      state.dailyActions = { speaking: 0, words: 0, lessons: 0 };
      state.history[today] = 0;
      save();
    }
  }

  function get() { return state; }

  function addXp(n) { state.xp += n; save(); }

  function addMinutes(n) {
    state.minutesToday += n;
    state.totalMinutes += n;
    state.history[todayKey()] = state.minutesToday;
    save();
  }

  function levelInfo() {
    const level = Math.floor(state.xp / 240) + 1;
    const into = state.xp % 240;
    return { level: level, into: into, need: 240, pct: Math.round(into / 240 * 100) };
  }

  function last7() {
    const out = [];
    const names = ['日', '一', '二', '三', '四', '五', '六'];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(Date.now() - i * DAY);
      out.push({
        label: names[d.getDay()],
        minutes: state.history[dateKey(d)] || 0,
        isToday: i === 0
      });
    }
    return out;
  }

  function historyDays(n) {
    const out = [];
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(Date.now() - i * DAY);
      out.push({ date: dateKey(d), minutes: state.history[dateKey(d)] || 0 });
    }
    return out;
  }

  const SKILL_LABEL = { vocab: '词汇', grammar: '语法', listening: '听力', speaking: '口语' };
  function skillList(lang) {
    const s = state.skills[lang] || state.skills.en;
    return ['vocab', 'grammar', 'listening', 'speaking'].map(function (k) {
      return { key: k, label: SKILL_LABEL[k], value: s[k] };
    });
  }
  function weakestSkill(lang) {
    return skillList(lang).slice().sort(function (a, b) { return a.value - b.value; })[0];
  }

  function courseProgress(lang) {
    const list = DB.lessonList(lang);
    const done = list.filter(function (l) { return state.completedLessons.indexOf(l.id) >= 0; }).length;
    return { done: done, total: list.length, pct: list.length ? Math.round(done / list.length * 100) : 0 };
  }

  function lessonModulesDone(lessonId) {
    const p = state.lessonProgress[lessonId];
    if (!p) return 0;
    return ['word', 'grammar', 'speaking', 'listening'].filter(function (k) { return !!p[k]; }).length;
  }

  function currentLesson(lang) {
    const list = DB.lessonList(lang);
    let partial = null;
    list.forEach(function (l) {
      const n = lessonModulesDone(l.id);
      if (!partial && n > 0 && n < 4 && state.completedLessons.indexOf(l.id) < 0) partial = l;
    });
    if (partial) return partial;
    for (let i = 0; i < list.length; i++) {
      if (state.completedLessons.indexOf(list[i].id) < 0) return list[i];
    }
    return list[list.length - 1];
  }

  function totalWords() {
    return state.wordsMastered.en + state.wordsMastered.ja + state.wordsMastered.ko;
  }

  function setLang(lang) {
    if (state.lang === lang) return;
    state.lang = lang;
    save();
  }

  function bumpSkill(key, gain) {
    const s = state.skills[state.lang];
    if (s && typeof s[key] === 'number') s[key] = Math.min(100, s[key] + gain);
  }

  // 模块完成后统一结算：XP、词汇量、技能值、每日任务、课程完成奖励
  function markModule(lessonId, key, opts) {
    opts = opts || {};
    state.lessonProgress[lessonId] = state.lessonProgress[lessonId] || {};
    const was = !!state.lessonProgress[lessonId][key];
    state.lessonProgress[lessonId][key] = true;
    let earned = 5;
    if (!was) {
      earned = opts.xp || 10;
      if (opts.words) {
        state.wordsMastered[state.lang] += opts.words;
        state.dailyActions.words += opts.words;
      }
      if (opts.skill) bumpSkill(opts.skill, opts.gain || 3);
      if (opts.score) {
        state.bestSpeaking = Math.max(state.bestSpeaking, opts.score);
        state.dailyActions.speaking += 1;
      }
      if (opts.perfectGrammar) state.perfectGrammar = true;
      if (new Date().getHours() >= 22) state.nightOwl = true;
      state.minutesToday += 2;
      state.totalMinutes += 2;
      state.history[todayKey()] = state.minutesToday;
    }
    const p = state.lessonProgress[lessonId];
    const allDone = ['word', 'grammar', 'speaking', 'listening'].every(function (k) { return !!p[k]; });
    let bonus = 0;
    let firstComplete = false;
    if (allDone && state.completedLessons.indexOf(lessonId) < 0) {
      state.completedLessons.push(lessonId);
      bonus = 30;
      firstComplete = true;
      state.dailyActions.lessons += 1;
    }
    state.xp += earned + bonus;
    save();
    return { first: !was, allDone: allDone, bonus: bonus, earned: earned + bonus, firstComplete: firstComplete };
  }

  function allModulesDone(lessonId) {
    return lessonModulesDone(lessonId) === 4;
  }

  function isLiked(postId) { return state.likes.indexOf(postId) >= 0; }
  function likeCount(post) { return post.likes + (isLiked(post.id) ? 1 : 0); }
  function toggleLike(postId) {
    const i = state.likes.indexOf(postId);
    if (i >= 0) state.likes.splice(i, 1); else state.likes.push(postId);
    save();
    return i < 0;
  }

  function addPost(payload) {
    const meta = DB.langMeta(payload.lang || state.lang);
    state.posts.unshift({
      id: 'u-' + Date.now(),
      author: state.user.name,
      lang: payload.lang || state.lang,
      badge: meta.badge,
      time: '刚刚',
      tag: '#学习记录',
      content: payload.content,
      lesson: payload.lesson || '',
      likes: 0,
      comments: []
    });
    save();
  }

  function addComment(postId, text) {
    state.myComments[postId] = state.myComments[postId] || [];
    state.myComments[postId].push({ author: state.user.name, text: text, time: '刚刚' });
    save();
  }

  function commentsOf(post) {
    return (post.comments || []).concat(state.myComments[post.id] || []);
  }

  function unlockedCount() {
    return DB.achievements.filter(function (a) { return a.current(state) >= a.goal; }).length;
  }

  function isClaimed(id) {
    const today = todayKey();
    return !!(state.claimed[today] && state.claimed[today][id]);
  }
  function claimChallenge(id) {
    const ch = DB.challenges.filter(function (c) { return c.id === id; })[0];
    if (!ch || isClaimed(id) || ch.current(state) < ch.goal) return false;
    const today = todayKey();
    state.claimed[today] = state.claimed[today] || {};
    state.claimed[today][id] = true;
    state.xp += ch.reward;
    save();
    return true;
  }

  function setPath(path) { state.path = path; save(); }
  function getPath() { return state.path; }

  window.Store = {
    init: init,
    get: get,
    save: save,
    readSession: readSession,
    setSession: setSession,
    clearSession: clearSession,
    isLoggedIn: isLoggedIn,
    checkIn: checkIn,
    addXp: addXp,
    addMinutes: addMinutes,
    levelInfo: levelInfo,
    last7: last7,
    historyDays: historyDays,
    skillList: skillList,
    weakestSkill: weakestSkill,
    courseProgress: courseProgress,
    lessonModulesDone: lessonModulesDone,
    currentLesson: currentLesson,
    totalWords: totalWords,
    setLang: setLang,
    markModule: markModule,
    allModulesDone: allModulesDone,
    isLiked: isLiked,
    likeCount: likeCount,
    toggleLike: toggleLike,
    addPost: addPost,
    addComment: addComment,
    commentsOf: commentsOf,
    unlockedCount: unlockedCount,
    isClaimed: isClaimed,
    claimChallenge: claimChallenge,
    setPath: setPath,
    getPath: getPath,
    todayKey: todayKey
  };
})();
