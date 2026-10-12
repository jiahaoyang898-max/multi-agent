/**
 * 智枢工作台 · 登录守卫（纯前端，零依赖）
 *
 * 引入方式：放在工作台各页面 <head> 里**最先**加载（同步脚本，阻塞渲染）——
 *           未登录会在页面绘制前就跳走，不会闪一下工作台再跳。
 *
 *     <script src="js/auth-guard.js"></script>        <!-- 首页 -->
 *     <script src="../js/auth-guard.js"></script>     <!-- 子目录页 -->
 *
 * 判定规则与 login/js/app.js 的 readSession() **完全一致**（同一套 localStorage 键），
 * 四处必须同步修改时请一起改：
 *     会话键   zhishu.session（sessionStorage）/ zhishu.session.persist（localStorage）
 *     账号库   zhishu.auth.v1  →  { v: 1, users: [...] }
 *     有效条件 uid 存在 且 expiresAt 未过期 且 该邮箱账号仍在库中
 *
 * 注意：这是**前端体验守卫**，不是安全边界 —— 数据都在浏览器本地，可被手动改写。
 */
(function () {
    'use strict';

    var DB_KEY = 'zhishu.auth.v1';
    var SS_SESSION = 'zhishu.session';
    var LS_SESSION = 'zhishu.session.persist';

    function readRaw() {
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
        return raw;
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

    /* 账号被移除（或换了浏览器）时，残留会话应当失效 */
    function accountExists(email) {
        if (!email) return false;
        try {
            var d = JSON.parse(localStorage.getItem(DB_KEY) || 'null');
            if (!d || !Array.isArray(d.users)) return false;
            var key = String(email).trim().toLowerCase();
            for (var i = 0; i < d.users.length; i++) {
                var u = d.users[i];
                if (u && u.email === key) return true;
            }
        } catch (e) {
        }
        return false;
    }

    function sessionValid() {
        var raw = readRaw();
        if (!raw) return false;

        var s;
        try {
            s = JSON.parse(raw);
        } catch (e) {
            clearSession();
            return false;
        }
        if (!s || !s.uid || !s.expiresAt || Number(s.expiresAt) < Date.now()) {
            clearSession();
            return false;
        }
        if (!accountExists(s.email)) {
            clearSession();
            return false;
        }
        return true;
    }

    /* 用本脚本自身的 URL 反推工作台根目录，
       这样无论挂在 /、/kb/ 还是 PyCharm 内置服务器的深层路径下都能找对登录页 */
    function loginUrl() {
        try {
            var el = document.currentScript;
            if (el && el.src) {
                var base = el.src.replace(/[?#].*$/, '').replace(/js\/auth-guard\.js$/, '');
                if (base) return base + 'login/';
            }
        } catch (e) {
        }
        return 'login/';
    }

    if (!sessionValid()) {
        if (window.console && console.info) {
            console.info('[智枢] 未检测到有效登录状态，跳转登录页。');
        }
        try {
            location.replace(loginUrl());
        } catch (e) {
            window.location.href = 'login/';
        }
    }
})();
