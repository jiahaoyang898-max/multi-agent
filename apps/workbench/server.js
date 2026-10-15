/**
 * 智枢智能工作台 - 零依赖静态服务器
 * 用法: node server.js  (或 npm start)
 * 端口: 默认 8180，可用环境变量 PORT 覆盖
 *
 * 除了静态托管，本文件还提供 /api/session「跨源共享会话」接口（见下方 SESSION API 段）。
 * 为什么需要它：登录体系是纯前端的（账号/会话存在 localStorage），而 localStorage 按
 * origin 隔离——问数前端 (:8173, vite) 与独立登录页 (:8190) 读不到 :8180 的会话，
 * 于是「在工作台点了退出，8173 里却还能继续用」。本接口把「现在到底有没有人登录」
 * 收敛到服务端一处，任何页面都用同一条 GET /api/session 去问。
 *
 * ⚠️ 诚实边界：这是**前端体验级的软守门**，不是安全机制。
 *    会话可以被人用 curl 直接 POST 伪造，账号数据也仍在浏览器本地可被改写。
 *    它防的是「误点」「退出后页面还在」这类体验问题，防不住刻意绕过前端的人。
 *    真要安全边界必须上后端鉴权（签发 token + 服务端校验）。
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8180;
const ROOT = __dirname;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg':  'image/svg+xml',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif':  'image/gif',
  '.ico':  'image/x-icon',
  '.woff': 'font/woff',
  '.woff2':'font/woff2'
};

/* =========================================================
   SESSION API —— 跨源共享会话（唯一真相源）
   GET    /api/session  -> {ok:true,email,name,expiresAt} | {ok:false}
   POST   /api/session  -> 登记当前会话 {email,name,token,expiresAt}
   DELETE /api/session  -> 清除
   会话存内存 + 落盘 .session-store.json（重启不把人踢下线）。
   仅对 8173 / 8190 的 origin 回显 CORS；:8180 自身是同源，无需 CORS。
   ========================================================= */
const SESSION_PATH = '/api/session';
const SESSION_STORE = path.join(ROOT, '.session-store.json');
const SESSION_TMP = SESSION_STORE + '.tmp';
const MAX_SESSION_BODY = 8 * 1024;           /* 会话体很小，超了直接拒，防内存被打爆 */
const ALLOWED_ORIGINS = new Set([
  'http://127.0.0.1:8173', 'http://localhost:8173',
  'http://127.0.0.1:8190', 'http://localhost:8190'
]);

let sessionState = null;        /* {email,name,token,expiresAt} | null */
let storeLoaded = false;

function writeStore(data) {
  /* 原子写：先写 tmp 再 rename；任何失败都不抛出——内存态仍在，服务不受影响 */
  try {
    fs.writeFileSync(SESSION_TMP, JSON.stringify(data, null, 2), 'utf8');
    fs.renameSync(SESSION_TMP, SESSION_STORE);
    return true;
  } catch (e) {
    console.warn('[session] 落盘失败（不影响本次运行）:', e && e.message);
    return false;
  }
}

function normalizeSession(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const email = typeof raw.email === 'string' ? raw.email.trim().toLowerCase() : '';
  if (!email) return null;
  const expiresAt = Number(raw.expiresAt);
  if (!Number.isFinite(expiresAt)) return null;
  return {
    email: email,
    name: typeof raw.name === 'string' ? raw.name.slice(0, 60) : '',
    token: typeof raw.token === 'string' ? raw.token.slice(0, 128) : '',
    expiresAt: expiresAt
  };
}

function isLive(s) {
  return !!s && Number(s.expiresAt) >= Date.now();
}

function loadStore() {
  storeLoaded = true;
  try {
    const parsed = normalizeSession(JSON.parse(fs.readFileSync(SESSION_STORE, 'utf8')));
    sessionState = parsed;
  } catch (e) {
    /* 文件不存在 / JSON 损坏 → 一律按「未登录」处理并重建，不抛未捕获异常 */
    sessionState = null;
    if (e.code !== 'ENOENT') {
      console.warn('[session] 会话文件损坏，已按未登录处理并重建:', e.message);
      writeStore(null);
    }
  }
}

function readSession() {
  if (!storeLoaded) loadStore();
  if (!isLive(sessionState)) {
    sessionState = null;      /* 过期即视为无效（文件留给下次 POST 覆盖，读时不做写盘） */
    return null;
  }
  return sessionState;
}

function sendJson(res, status, payload, origin) {
  const headers = { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' };
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    /* 按请求 Origin 回显，绝不写 '*'（虽然本接口不用凭据，也保持最小暴露面） */
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Vary'] = 'Origin';
  }
  res.writeHead(status, headers);
  res.end(JSON.stringify(payload));
}

function handleOptions(req, res, origin) {
  const headers = { 'Content-Length': '0' };
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS';
    headers['Access-Control-Allow-Headers'] = 'Content-Type';
    headers['Access-Control-Max-Age'] = '600';
    headers['Vary'] = 'Origin';
  }
  res.writeHead(204, headers);
  res.end();
}

function handlePostSession(req, res, origin) {
  let size = 0;
  const chunks = [];
  req.on('data', (c) => {
    size += c.length;
    if (size > MAX_SESSION_BODY) {
      sendJson(res, 413, { ok: false, error: 'payload too large' }, origin);
      req.destroy();
      return;
    }
    chunks.push(c);
  });
  req.on('end', () => {
    if (size > MAX_SESSION_BODY) return;      /* 已经回过 413 */
    let body;
    try {
      body = JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
    } catch (e) {
      sendJson(res, 400, { ok: false, error: 'invalid json' }, origin);
      return;
    }
    const next = normalizeSession(body);
    if (!next) {
      sendJson(res, 400, { ok: false, error: 'email and valid expiresAt are required' }, origin);
      return;
    }
    sessionState = next;
    storeLoaded = true;
    const saved = writeStore(next);
    sendJson(res, 200, { ok: true, saved: saved, email: next.email }, origin);
  });
  req.on('error', () => {
    sendJson(res, 400, { ok: false, error: 'request error' }, origin);
  });
}

function handleSessionApi(req, res, urlPath) {
  const origin = req.headers.origin || '';
  if (urlPath !== SESSION_PATH) return false;

  /* 兜底：读路径异常（权限、磁盘故障）也不能让请求悬着 */
  try {
    switch (req.method) {
      case 'OPTIONS':
        handleOptions(req, res, origin);
        return true;
      case 'GET': {
        const s = readSession();
        if (!s) sendJson(res, 200, { ok: false }, origin);
        else sendJson(res, 200, { ok: true, email: s.email, name: s.name, expiresAt: s.expiresAt }, origin);
        return true;
      }
      case 'POST':
        handlePostSession(req, res, origin);
        return true;
      case 'DELETE': {
        sessionState = null;
        storeLoaded = true;
        writeStore(null);
        sendJson(res, 200, { ok: true, cleared: true }, origin);
        return true;
      }
      default:
        sendJson(res, 405, { ok: false, error: 'method not allowed' }, origin);
        return true;
    }
  } catch (e) {
    console.error('[session] 处理异常:', e && e.message);
    if (!res.headersSent) sendJson(res, 500, { ok: false, error: 'server error' }, origin);
    else res.end();
    return true;
  }
}

/* 进程起来先读一次盘：工作台重启不该把人踢下线 */
loadStore();

const server = http.createServer((req, res) => {
  let urlPath;
  try {
    urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  } catch (e) {
    res.writeHead(400); return res.end('Bad Request');
  }
  /* 会话接口优先于静态托管（不参与路径拼接/穿越判定，也不落文件） */
  if (handleSessionApi(req, res, urlPath)) return;
  if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
  // 子目录形式（如 /kb/）自动补 index.html
  if (urlPath.endsWith('/')) urlPath += 'index.html';

  const filePath = path.join(ROOT, path.normalize(urlPath));

  // 防目录穿越
  if (!(filePath === ROOT || filePath.startsWith(ROOT + path.sep))) {
    res.writeHead(403); return res.end('Forbidden');
  }
  // 点开头的是本机运行时文件（.session-store.json 含会话 token），一律不作为静态文件吐出
  if (path.basename(filePath).charAt(0) === '.') {
    res.writeHead(403); return res.end('Forbidden');
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('404 Not Found');
    }
    const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
      // no-cache：每次导航都向服务器确认/取最新 —— 防止浏览器拿旧版 index.html
      //（旧版没有登录守卫，会让已加守卫的改动"看起来没生效"）
      res.writeHead(200, {'Content-Type': type, 'Cache-Control': 'no-cache'});
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log('==========================================');
  console.log('  智枢智能工作台 已启动');
  console.log(`  请在浏览器打开: http://localhost:${PORT}`);
  console.log('==========================================');
});
