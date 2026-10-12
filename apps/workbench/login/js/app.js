/* =========================================================
   智枢智能工作台 · 登录 / 注册
   真实可运行的账号体系（本机）：注册、登录、会话、重置密码。

   · 口令以 PBKDF2-SHA256 + 每账号独立随机盐 派生后存储，不保存明文
   · 会话带签发时间与过期时间，勾选「记住我」写 localStorage（7 天），
     未勾选写 sessionStorage（关闭浏览器即失效，最长 12 小时）
   · 不请求任何后端接口，也不新增端口 —— 页面由已有的 8080 静态服务托管

   接真实后端时，只需替换 Store 段这几个函数：
     readUsers / writeUsers / findUser / saveUser / updatePassword
     readSession / writeSession / clearSession
   其余（校验、强度、交互、可访问性）与存储无关，可原样保留。
   ========================================================= */
(function () {
    'use strict';

    var DB_KEY = 'zhishu.auth.v1';
    var SS_SESSION = 'zhishu.session';
    var LS_SESSION = 'zhishu.session.persist';
    var THEME_KEY = 'zhishu.theme';

    var ITER = 150000;   /* PBKDF2 迭代次数 */
    var REMEMBER_DAYS = 7;
    var SESSION_HOURS = 12;
    var RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    var LEVEL_TXT = ['', '弱', '一般', '较强', '很强'];

    var HI = {
        login: {t: '欢迎回来！', d: '登录后可继续使用问数与知库。'},
        signup: {t: '欢迎加入！', d: '完成注册后即可进入工作台。'}
    };
    var ALERT_ICON = {
        error: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7.6v5.4M12 16.2v.3"/></svg>',
        success: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.4 2.5 2.5 4.6-5"/></svg>'
    };

    var C = window.ZhiCrypto;
    C.iterations = ITER;
    if (window.console && console.info) {
        console.info('[智枢] 口令派生模式：' + C.mode + '，迭代 ' + ITER + ' 次');
    }

    function $(s, r) {
        return (r || document).querySelector(s);
    }

    function $$(s, r) {
        return Array.prototype.slice.call((r || document).querySelectorAll(s));
    }

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }

    /* ---------------- 元素 ---------------- */
    var card = $('#card');
    var formLogin = $('#formLogin');
    var formSignup = $('#formSignup');
    var resetForm = $('#resetForm');
    var resetDlg = $('#resetDlg');
    var hiTitle = $('#hiTitle');
    var hiDesc = $('#hiDesc');
    var toastEl = $('#toast');
    var themeBtn = $('#themeToggle');
    var bar = $('#sessionBar');
    var barWho = $('#sbWho');

    var state = 'login';
    var busy = {login: false, signup: false, reset: false};
    var isNarrow = function () {
        return window.innerWidth <= 820;
    };

    /* =========================================================
       Store —— 账号与会话的唯一落点
       ========================================================= */
    function readUsers() {
        try {
            var d = JSON.parse(localStorage.getItem(DB_KEY) || 'null');
            if (d && Array.isArray(d.users)) return d.users;
        } catch (e) {
        }
        return [];
    }

    function writeUsers(users) {
        try {
            localStorage.setItem(DB_KEY, JSON.stringify({v: 1, users: users}));
            return true;
        } catch (e) {
            return false;
        }
    }

    function normalize(email) {
        return String(email || '').trim().toLowerCase();
    }

    function findUser(email) {
        var key = normalize(email);
        return readUsers().filter(function (u) {
            return u.email === key;
        })[0] || null;
    }

    function saveUser(rec) {
        var users = readUsers();
        if (users.some(function (u) {
            return u.email === rec.email;
        })) return false;
        users.push(rec);
        return writeUsers(users);
    }

    function updatePassword(email, salt, hash, iter) {
        var key = normalize(email);
        var users = readUsers();
        var hit = false;
        users.forEach(function (u) {
            if (u.email === key) {
                u.salt = salt;
                u.hash = hash;
                u.iter = iter;
                u.updatedAt = Date.now();
                hit = true;
            }
        });
        if (!hit) return false;
        return writeUsers(users);
    }

    function readSession() {
        var raw = null;
        try {
            raw = sessionStorage.getItem(SS_SESSION);
        } catch (e) {
        }
        if (!raw) {
            try {
                raw = localStorage.getItem(LS_SESSION);
            } catch (e) {
            }
        }
        if (!raw) return null;
        var s;
        try {
            s = JSON.parse(raw);
        } catch (e) {
            return null;
        }
        if (!s || !s.uid || !s.expiresAt || s.expiresAt < Date.now()) {
            clearSession();
            return null;
        }
        if (!findUser(s.email)) {
            clearSession();
            return null;
        }   /* 账号已被移除 */
        return s;
    }

    function writeSession(s, persist) {
        var raw = JSON.stringify(s);
        try {
            if (persist) {
                localStorage.setItem(LS_SESSION, raw);
                sessionStorage.removeItem(SS_SESSION);
            } else {
                sessionStorage.setItem(SS_SESSION, raw);
                localStorage.removeItem(LS_SESSION);
            }
            return true;
        } catch (e) {
            return false;
        }
    }

    function clearSession() {
        try {
            sessionStorage.removeItem(SS_SESSION);
        } catch (e) {
        }
        try {
            localStorage.removeItem(LS_SESSION);
        } catch (e) {
        }
    }

    /* ---------------- 轻提示 ---------------- */
    var toastTimer;

    function toast(msg) {
        if (!toastEl) return;
        toastEl.textContent = msg;
        toastEl.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            toastEl.classList.remove('show');
        }, 2800);
    }

    /* ---------------- 提示条 ---------------- */
    function setAlert(form, msg, kind) {
        if (!form) return;
        var box = form.querySelector('.alert');
        if (!box) return;
        if (!msg) {
            box.className = 'alert';
            box.innerHTML = '';
            return;
        }
        kind = kind || 'error';
        box.className = 'alert show' + (kind === 'success' ? ' success' : '');
        box.innerHTML = (ALERT_ICON[kind] || ALERT_ICON.error) + '<span>' + esc(msg) + '</span>';
    }

    function clearAlerts() {
        setAlert(formLogin, '');
        setAlert(formSignup, '');
        setAlert(resetForm, '');
    }

    /* ---------------- 字段校验 ---------------- */
    function setErr(fieldId, msg) {
        var f = document.getElementById(fieldId);
        if (!f) return !msg;
        f.classList.toggle('invalid', !!msg);
        var p = f.querySelector('.err');
        if (p) p.textContent = msg || '';
        var input = f.querySelector('input');
        if (input) {
            if (msg) input.setAttribute('aria-invalid', 'true');
            else input.removeAttribute('aria-invalid');
        }
        return !msg;
    }

    function clearErrs() {
        $$('.field.invalid').forEach(function (f) {
            f.classList.remove('invalid');
            var p = f.querySelector('.err');
            if (p) p.textContent = '';
            var i = f.querySelector('input');
            if (i) i.removeAttribute('aria-invalid');
        });
        var aw = $('#agreeWrap');
        if (aw) aw.classList.remove('invalid');
    }

    /* ---------------- 按钮忙碌态 ---------------- */
    function setBusy(btn, on, label) {
        if (!btn) return;
        if (on) {
            if (!btn.dataset.html) btn.dataset.html = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spin"></span>' + esc(label || '处理中');
        } else {
            btn.disabled = false;
            if (btn.dataset.html) {
                btn.innerHTML = btn.dataset.html;
                delete btn.dataset.html;
            }
        }
    }

    /* ---------------- 密码强度 ---------------- */
    function pwOK(pw) {
        return pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw);
    }

    function pwLevel(pw) {
        if (!pw) return 0;
        var variety = 0;
        if (/[a-z]/.test(pw)) variety++;
        if (/[A-Z]/.test(pw)) variety++;
        if (/\d/.test(pw)) variety++;
        if (/[^A-Za-z0-9]/.test(pw)) variety++;
        var score = 0;
        if (pw.length >= 8) score++;
        if (pw.length >= 12) score++;
        if (variety >= 2) score++;
        if (variety >= 3) score++;
        if (pw.length < 8 || variety < 2) score = Math.min(score, 1);
        return Math.max(1, Math.min(4, score));
    }

    var meterEl = $('#pwMeter');
    var meterTxt = $('#pwMeterTxt');

    function paintMeter(pw) {
        if (!meterEl || !meterTxt) return;
        var lv = pwLevel(pw);
        meterEl.className = 'meter' + (lv ? ' lv-' + lv : '');
        $$('i', meterEl).forEach(function (seg, i) {
            seg.classList.toggle('on', i < lv);
        });
        meterTxt.className = 'meter-txt' + (lv ? ' lv-' + lv : '');
        meterTxt.textContent = lv ? '密码强度：' + LEVEL_TXT[lv] : '';
    }

    /* ---------------- 会话 ---------------- */
    function startSession(user, persist) {
        var s = {
            uid: user.id,
            email: user.email,
            name: user.name || '',
            token: C.randomHex(24),
            issuedAt: Date.now(),
            expiresAt: Date.now() + (persist ? REMEMBER_DAYS * 86400000 : SESSION_HOURS * 3600000),
            persist: !!persist
        };
        return writeSession(s, persist) ? s : null;
    }

    function showSessionBar(s) {
        if (!bar) return;
        barWho.textContent = s.name ? (s.name + '（' + s.email + '）') : s.email;
        bar.hidden = false;
    }

    function hideSessionBar() {
        if (bar) bar.hidden = true;
    }

    function enterWorkbench(user, form, persist) {
        if (!startSession(user, persist)) {
            setAlert(form, '无法保存登录状态，请检查浏览器是否禁用了本地存储', 'error');
            return false;
        }
        setAlert(form, '登录成功，正在进入工作台…', 'success');
        toast('欢迎回来' + (user.name ? '，' + user.name : ''));
        setTimeout(function () {
            window.location.href = '../';
        }, 900);
        return true;
    }

    /* 兜底：成功态会一直保持按钮禁用直到跳转；若跳转被浏览器/扩展拦截，
       4 秒后自动解锁，避免表单卡在忙碌态无法重试 */
    function unlockLater(key, btn) {
        setTimeout(function () {
            busy[key] = false;
            setBusy(btn, false);
        }, 4000);
    }

    /* ---------------- 登录 ---------------- */
    var loginEmail = $('#loginEmail');
    var loginPass = $('#loginPass');
    var loginBtn = $('#loginBtn');
    var remember = $('#remember');

    async function doLogin() {
        if (busy.login) return;
        clearAlerts();

        var email = loginEmail.value.trim();
        var pass = loginPass.value;
        var ok1 = setErr('f-login-email',
            !email ? '请输入邮箱' : (!RE_EMAIL.test(email) ? '邮箱格式不正确' : ''));
        var ok2 = setErr('f-login-pass', !pass ? '请输入密码' : '');
        if (!ok1 || !ok2) return;

        busy.login = true;
        setBusy(loginBtn, true, '登录中');

        var user, ok;
        try {
            user = findUser(email);
            if (user) {
                ok = await C.verify(pass, user.salt, user.iter || ITER, user.hash);
            } else {
                await C.equalize(pass, ITER);
                ok = false;
            }
        } catch (e) {
            busy.login = false;
            setBusy(loginBtn, false);
            setAlert(formLogin, '登录失败：' + ((e && e.message) || '无法完成口令校验'), 'error');
            return;
        }

        if (!ok) {
            busy.login = false;
            setBusy(loginBtn, false);
            setErr('f-login-pass', '邮箱或密码不正确');
            setAlert(formLogin, '邮箱或密码不正确，请检查后重试', 'error');
            loginPass.focus();
            loginPass.select();
            return;
        }

        /* 成功：保持忙碌态直到跳转，避免重复提交 */
        if (!enterWorkbench(user, formLogin, !!(remember && remember.checked))) {
            busy.login = false;
            setBusy(loginBtn, false);
            return;
        }
        unlockLater('login', loginBtn);
    }

    formLogin.addEventListener('submit', function (e) {
        e.preventDefault();
        doLogin();
    });
    loginEmail.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            loginPass.focus();
        }
    });

    /* ---------------- 注册 ---------------- */
    var suName = $('#suName');
    var suEmail = $('#suEmail');
    var suPass = $('#suPass');
    var suBtn = $('#signupBtn');

    async function doSignup() {
        if (busy.signup) return;
        clearAlerts();

        var name = suName.value.trim();
        var email = suEmail.value.trim();
        var pass = suPass.value;
        var agree = $('#agree');

        var ok1 = setErr('f-su-name',
            !name ? '请输入用户名' : (name.length < 2 ? '用户名至少 2 个字符' : ''));
        var ok2 = setErr('f-su-email',
            !email ? '请输入邮箱' : (!RE_EMAIL.test(email) ? '邮箱格式不正确' : ''));
        var ok3 = setErr('f-su-pass',
            !pass ? '请设置密码' : (!pwOK(pass) ? '至少 8 位，且需同时包含字母与数字' : ''));

        var aw = $('#agreeWrap');
        var ok4 = true;
        if (agree && !agree.checked) {
            aw.classList.add('invalid');
            ok4 = false;
        } else if (aw) {
            aw.classList.remove('invalid');
        }

        if (!ok1 || !ok2 || !ok3 || !ok4) return;

        busy.signup = true;
        setBusy(suBtn, true, '正在创建');

        var salt, hash;
        try {
            salt = C.randomSalt(16);
            hash = await C.derive(pass, salt, ITER, 32);
        } catch (e) {
            busy.signup = false;
            setBusy(suBtn, false);
            setAlert(formSignup, '注册失败：' + ((e && e.message) || '无法完成口令派生'), 'error');
            return;
        }

        /* 派生耗时以百毫秒计，重新判重，避免并发注册同一邮箱 */
        if (findUser(email)) {
            busy.signup = false;
            setBusy(suBtn, false);
            setErr('f-su-email', '该邮箱已注册，请直接登录');
            setAlert(formSignup, '该邮箱已注册，可直接登录', 'error');
            return;
        }

        var rec = {
            id: C.randomHex(8),
            email: normalize(email),
            name: name,
            salt: salt,
            hash: hash,
            iter: ITER,
            createdAt: Date.now()
        };

        if (!saveUser(rec)) {
            busy.signup = false;
            setBusy(suBtn, false);
            setAlert(formSignup, '无法写入本机存储，请检查浏览器是否禁用了本地存储', 'error');
            return;
        }

        toast('注册成功，正在进入工作台…');
        if (!enterWorkbench(rec, formSignup, true)) {
            busy.signup = false;
            setBusy(suBtn, false);
            return;
        }
        unlockLater('signup', suBtn);
    }

    formSignup.addEventListener('submit', function (e) {
        e.preventDefault();
        doSignup();
    });

    /* ---------------- 重置密码 ---------------- */
    var rsEmail = $('#rsEmail');
    var rsPass = $('#rsPass');
    var rsPass2 = $('#rsPass2');
    var rsBtn = $('#resetSubmit');

    function openReset() {
        clearErrs();
        clearAlerts();
        rsEmail.value = loginEmail.value.trim();
        rsPass.value = '';
        rsPass2.value = '';
        if (!resetDlg) return;
        if (typeof resetDlg.showModal === 'function') resetDlg.showModal();
        else resetDlg.setAttribute('open', '');
        setTimeout(function () {
            (rsEmail.value ? rsPass : rsEmail).focus();
        }, 30);
    }

    function closeReset() {
        if (!resetDlg) return;
        if (typeof resetDlg.close === 'function') resetDlg.close();
        else resetDlg.removeAttribute('open');
    }

    $('#forgotBtn').addEventListener('click', openReset);
    $('#resetCancel').addEventListener('click', closeReset);
    if (resetDlg) {
        resetDlg.addEventListener('click', function (e) {
            if (e.target === resetDlg) closeReset();
        });
    }

    resetForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        if (busy.reset) return;
        clearAlerts();

        var email = rsEmail.value.trim();
        var pass = rsPass.value;
        var pass2 = rsPass2.value;

        var ok1 = setErr('f-rs-email',
            !email ? '请输入邮箱' : (!RE_EMAIL.test(email) ? '邮箱格式不正确' : ''));
        var ok2 = setErr('f-rs-pass',
            !pass ? '请设置新密码' : (!pwOK(pass) ? '至少 8 位，且需同时包含字母与数字' : ''));
        var ok3 = setErr('f-rs-pass2',
            !pass2 ? '请再次输入新密码' : (pass2 !== pass ? '两次输入的新密码不一致' : ''));
        if (!ok1 || !ok2 || !ok3) return;

        busy.reset = true;
        setBusy(rsBtn, true, '正在重置');

        var user = findUser(email);
        var salt, hash;
        try {
            salt = C.randomSalt(16);
            hash = await C.derive(pass, salt, ITER, 32);
        } catch (err) {
            busy.reset = false;
            setBusy(rsBtn, false);
            setAlert(resetForm, '重置失败：' + ((err && err.message) || '无法完成口令派生'), 'error');
            return;
        }

        if (!user || !updatePassword(email, salt, hash, ITER)) {
            busy.reset = false;
            setBusy(rsBtn, false);
            setErr('f-rs-email', '本机没有该邮箱对应的账号');
            setAlert(resetForm, '本机没有该邮箱对应的账号，请先注册', 'error');
            return;
        }

        /* 改密后原有会话立即失效 */
        var s = readSession();
        if (s && s.email === normalize(email)) {
            clearSession();
            hideSessionBar();
        }

        busy.reset = false;
        setBusy(rsBtn, false);
        closeReset();
        toast('密码已重置，请用新密码登录');
        loginEmail.value = normalize(email);
        loginEmail.closest('.field').classList.add('has-value');
        applyState('login');
        setTimeout(function () {
            loginPass.focus();
        }, 40);
    });

    /* ---------------- 切换状态 ---------------- */
    function render() {
        var h = HI[state] || HI.login;
        if (hiTitle.textContent !== h.t) hiTitle.textContent = h.t;
        if (hiDesc.textContent !== h.d) hiDesc.textContent = h.d;
        formLogin.hidden = (state !== 'login');
        formSignup.hidden = (state !== 'signup');
    }

    function applyState(name) {
        if (name !== 'login' && name !== 'signup') name = 'login';
        state = name;
        card.classList.toggle('reg', state === 'signup');
        clearAlerts();
        clearErrs();
        render();
        if (history.replaceState) history.replaceState(null, '', '#' + state);
    }

    $$('[data-go]').forEach(function (b) {
        b.addEventListener('click', function () {
            applyState(b.getAttribute('data-go'));
        });
    });

    /* ---------------- 拖拽 / 横扫切换 ---------------- */
    var drag = null;

    function isInteractive(el) {
        if (!el || !el.closest) return false;
        return !!el.closest('input, button, a, label, textarea, select, code');
    }

    card.addEventListener('pointerdown', function (e) {
        if (isNarrow()) return;
        if (isInteractive(e.target)) return;
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        drag = {
            x: e.clientX, t0: state === 'signup' ? 1 : 0, t: state === 'signup' ? 1 : 0,
            id: e.pointerId, moved: false
        };
        card.classList.add('dragging');
        try {
            card.setPointerCapture(e.pointerId);
        } catch (err) {
        }
    });

    card.addEventListener('pointermove', function (e) {
        if (!drag || e.pointerId !== drag.id) return;
        var span = card.clientWidth * 0.46;
        var t = drag.t0 + (e.clientX - drag.x) / span;
        if (t < 0) t = 0;
        if (t > 1) t = 1;
        if (Math.abs(e.clientX - drag.x) > 6) drag.moved = true;
        drag.t = t;
        card.style.setProperty('--t', t.toFixed(4));
    });

    function endDrag(e) {
        if (!drag) return;
        if (e && e.pointerId !== undefined && e.pointerId !== drag.id) return;
        var d = drag;
        drag = null;
        card.classList.remove('dragging');
        card.style.removeProperty('--t');
        if (!d.moved) return;
        applyState(d.t > 0.5 ? 'signup' : 'login');
    }

    card.addEventListener('pointerup', endDrag);
    card.addEventListener('pointercancel', endDrag);
    window.addEventListener('blur', function () {
        endDrag(null);
    });

    /* ---------------- 密码显隐 ---------------- */
    $$('[data-eye]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.getElementById(btn.getAttribute('data-eye'));
            if (!input) return;
            var show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            btn.classList.toggle('on', show);
            btn.setAttribute('aria-pressed', show ? 'true' : 'false');
            btn.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
            input.focus();
        });
    });

    /* ---------------- 输入态 ---------------- */
    $$('.field input').forEach(function (input) {
        var field = input.closest('.field');

        function sync() {
            if (!field) return;
            field.classList.toggle('has-value', !!input.value);
            if (field.classList.contains('invalid')) {
                field.classList.remove('invalid');
                input.removeAttribute('aria-invalid');
                var p = field.querySelector('.err');
                if (p) p.textContent = '';
            }
        }

        input.addEventListener('input', function () {
            sync();
            if (input === suPass) paintMeter(input.value);
        });
        input.addEventListener('change', sync);
        sync();
    });
    var agreeBox = $('#agree');
    if (agreeBox) {
        agreeBox.addEventListener('change', function () {
            var aw = $('#agreeWrap');
            if (aw && agreeBox.checked) aw.classList.remove('invalid');
        });
    }

    /* ---------------- 退出登录 ---------------- */
    var logoutBtn = $('#logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
            clearSession();
            hideSessionBar();
            loginPass.value = '';
            loginPass.closest('.field').classList.remove('has-value');
            clearErrs();
            clearAlerts();
            toast('已退出登录');
            applyState('login');
        });
    }

    /* ---------------- 主题切换 ---------------- */
    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            var dark = document.documentElement.classList.toggle('dark');
            try {
                localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
            } catch (e) {
            }
        });
    }

    /* ---------------- 全局快捷键 ---------------- */
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !(resetDlg && resetDlg.open)) {
            clearAlerts();
            clearErrs();
        }
    });

    /* ---------------- 初始化 ---------------- */
    var hash = String(location.hash || '').replace(/^#/, '');
    if (hash === 'signup' || hash === 'login') state = hash;
    applyState(state);

    var session = readSession();
    if (session) showSessionBar(session);
    paintMeter('');
})();
