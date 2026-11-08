/* Lingua · API 桩层
 * 说明：所有函数保持真实接口的签名与异步节奏，内部返回 mock 数据。
 * 后续接入后端时，只需替换实现，页面层无需改动。
 */
(function () {
  const ACCOUNTS_KEY = 'lingua.accounts.v1';
  const DEMO = { email: 'demo@lingua.app', password: '1234', name: '林知夏' };

  function delay(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // TODO: replace with POST /api/auth/login  { email, password } -> { token, user }
  async function login(email, password) {
    await delay(560);
    if (email === DEMO.email && password === DEMO.password) {
      return { ok: true, user: { name: DEMO.name, email: email, demo: true } };
    }
    const accounts = readAccounts();
    const acc = accounts.filter(function (a) { return a.email === email; })[0];
    if (!acc) return { ok: false, error: '该邮箱尚未注册，请先创建账号' };
    if (acc.password !== password) return { ok: false, error: '密码不正确，请重试' };
    return { ok: true, user: { name: acc.name, email: email, demo: false } };
  }

  // TODO: replace with POST /api/auth/register  { name, email, password } -> { token, user }
  async function register(payload) {
    await delay(680);
    const email = payload.email;
    if (email === DEMO.email) return { ok: false, error: '该邮箱为演示账号，请更换邮箱' };
    const accounts = readAccounts();
    if (accounts.some(function (a) { return a.email === email; })) {
      return { ok: false, error: '该邮箱已注册，请直接登录' };
    }
    accounts.push({ name: payload.name, email: email, password: payload.password });
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
    return { ok: true, user: { name: payload.name, email: email, demo: false } };
  }

  function readAccounts() {
    try { return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || '[]'); } catch (e) { return []; }
  }

  const GOALS = {
    travel: { label: '旅行沟通', icon: 'map', themes: ['开口生存句', '城市移动', '吃喝点单', '突发应对'] },
    career: { label: '职场进阶', icon: 'trending-up', themes: ['自我表达', '邮件与会议', '观点协商', '演讲呈现'] },
    exam: { label: '考试冲刺', icon: 'graduation-cap', themes: ['高频词汇', '语法查漏', '听力精练', '模拟复盘'] },
    culture: { label: '兴趣文化', icon: 'sparkles', themes: ['日常语感', '影视表达', '文化背景', '自由表达'] }
  };

  // TODO: replace with POST /api/path/generate
  // req: { lang, goal, level, minutes } -> res: { weeks: [...] }
  async function generatePath(opts) {
    await delay(900);
    const goal = GOALS[opts.goal] || GOALS.travel;
    const lessons = window.DB.lessonList(opts.lang);
    const start = Math.max(0, (opts.levelIndex || 0) * 6);
    const pick = function (i) { return lessons[(start + i) % lessons.length]; };
    const taskIcons = ['book-open', 'mic', 'headphones'];
    const weeks = goal.themes.map(function (theme, wi) {
      const tasks = [0, 1, 2].map(function (ti) {
        const lesson = pick(wi * 3 + ti);
        return {
          title: lesson.title,
          meta: lesson.levelCode + ' · ' + lesson.minutes + ' 分钟',
          icon: taskIcons[ti],
          lessonId: lesson.id
        };
      });
      return {
        no: wi + 1,
        theme: theme,
        goal: goal.label,
        minutes: opts.minutes,
        tasks: tasks,
        milestone: wi === 3 ? '完成阶段性测评，解锁下一等级' : '完成本周 3 次练习，保持连续打卡'
      };
    });
    return {
      ok: true,
      path: {
        lang: opts.lang,
        goal: opts.goal,
        goalLabel: goal.label,
        goalIcon: goal.icon,
        level: opts.level,
        minutes: opts.minutes,
        createdAt: Date.now(),
        weeks: weeks
      }
    };
  }

  window.API = { login: login, register: register, generatePath: generatePath, delay: delay, GOALS: GOALS };
})();
