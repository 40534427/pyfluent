/* Lingua · 登录 / 注册页交互：校验、Tab 切换、密码可见、演示账号、会话写入 */
(function () {
  var SESSION_KEY = 'lingua.session.v1';

  try {
    var existing = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
    if (existing && existing.email) { location.replace('app.html'); return; }
  } catch (e) { /* ignore */ }

  var form = document.getElementById('authForm');
  var tabLogin = document.getElementById('tabLogin');
  var tabRegister = document.getElementById('tabRegister');
  var nameField = document.getElementById('nameField');
  var nameInput = document.getElementById('nameInput');
  var emailField = document.getElementById('emailField');
  var emailInput = document.getElementById('emailInput');
  var passwordField = document.getElementById('passwordField');
  var passwordInput = document.getElementById('passwordInput');
  var pwdOpt = document.getElementById('pwdOpt');
  var togglePwd = document.getElementById('togglePwd');
  var authError = document.getElementById('authError');
  var authTitle = document.getElementById('authTitle');
  var authSub = document.getElementById('authSub');
  var submitBtn = document.getElementById('submitBtn');
  var demoBtn = document.getElementById('demoBtn');

  var mode = 'login';
  var pwdVisible = false;

  function clearError() {
    authError.textContent = '';
    authError.classList.remove('show');
    [nameField, emailField, passwordField].forEach(function (f) { if (f) f.classList.remove('invalid'); });
  }

  function showError(msg, field) {
    authError.textContent = msg;
    authError.classList.add('show');
    if (field) field.classList.add('invalid');
  }

  function setMode(next) {
    mode = next;
    clearError();
    var login = mode === 'login';
    tabLogin.classList.toggle('active', login);
    tabRegister.classList.toggle('active', !login);
    tabLogin.setAttribute('aria-selected', login ? 'true' : 'false');
    tabRegister.setAttribute('aria-selected', login ? 'false' : 'true');
    nameField.hidden = login;
    nameInput.setAttribute('autocomplete', login ? 'nickname' : 'nickname');
    passwordInput.setAttribute('autocomplete', login ? 'current-password' : 'new-password');
    pwdOpt.textContent = login ? '至少 4 位' : '至少 6 位';
    authTitle.textContent = login ? '继续你的语言旅程' : '创建你的学习档案';
    authSub.textContent = login
      ? '登录后同步课程进度、连续打卡与成就'
      : '一次注册，三种语言的学习记录都会保存在这里';
    submitBtn.textContent = login ? '登 录' : '创建账号';
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    if (on) {
      submitBtn.innerHTML = '<span class="spinner"></span> ' + (mode === 'login' ? '登录中…' : '创建中…');
    } else {
      submitBtn.textContent = mode === 'login' ? '登 录' : '创建账号';
    }
  }

  function validate() {
    clearError();
    var email = emailInput.value.trim();
    var password = passwordInput.value;
    if (mode === 'register' && nameInput.value.trim().length < 2) {
      showError('昵称至少需要 2 个字符', nameField);
      nameInput.focus();
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError('请输入有效的邮箱地址', emailField);
      emailInput.focus();
      return false;
    }
    if (password.length < (mode === 'login' ? 4 : 6)) {
      showError(mode === 'login' ? '密码至少 4 位' : '密码至少需要 6 位', passwordField);
      passwordInput.focus();
      return false;
    }
    return true;
  }

  async function submit() {
    if (!validate()) return;
    setLoading(true);
    var email = emailInput.value.trim();
    var password = passwordInput.value;
    var res;
    try {
      res = mode === 'login'
        ? await API.login(email, password)
        : await API.register({ name: nameInput.value.trim(), email: email, password: password });
    } catch (e) {
      res = { ok: false, error: '网络异常，请稍后重试' };
    }
    setLoading(false);
    if (!res.ok) {
      showError(res.error, passwordField);
      return;
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      name: res.user.name,
      email: res.user.email,
      demo: !!res.user.demo
    }));
    location.href = 'app.html';
  }

  tabLogin.addEventListener('click', function () { setMode('login'); });
  tabRegister.addEventListener('click', function () { setMode('register'); });

  togglePwd.addEventListener('click', function () {
    pwdVisible = !pwdVisible;
    passwordInput.type = pwdVisible ? 'text' : 'password';
    togglePwd.innerHTML = window.Icon(pwdVisible ? 'eye-off' : 'eye', 17);
    togglePwd.setAttribute('aria-label', pwdVisible ? '隐藏密码' : '显示密码');
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    submit();
  });

  demoBtn.addEventListener('click', function () {
    setMode('login');
    emailInput.value = 'demo@lingua.app';
    passwordInput.value = '1234';
    clearError();
    submit();
  });

  [emailInput, passwordInput, nameInput].forEach(function (input) {
    input.addEventListener('input', clearError);
  });

  setMode('login');
})();
