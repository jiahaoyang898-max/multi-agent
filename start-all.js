#!/usr/bin/env node
/**
 * 智枢套件一键启动器（零依赖，Node >= 18）
 *
 * 用法：
 *   npm start                     启动 services.json 中的全部中间件与服务
 *   node start-all.js --only workbench,data-agent
 *                                 只启动指定 name 的服务（跳过中间件）
 *   NO_BROWSER=1 npm start        就绪后不自动打开浏览器
 *
 * 说明：
 *   - 各项目原地引用（services.json 里写 cwd），不拷贝源码、不改业务代码
 *   - Ctrl+C 一次性停止全部子进程（Windows 下 taskkill /T 清进程树）
 */
'use strict';

const { spawn, spawnSync } = require('child_process');
const { StringDecoder } = require('string_decoder');
const net = require('net');
const path = require('path');
const fs = require('fs');

const ROOT = __dirname;
const IS_WIN = process.platform === 'win32';
const argv = process.argv.slice(2);

/* ---------- 解析命令行参数 ---------- */
let ONLY = null;
const onlyIdx = argv.indexOf('--only');
if (onlyIdx !== -1 && argv[onlyIdx + 1]) {
  ONLY = argv[onlyIdx + 1].split(',').map((s) => s.trim()).filter(Boolean);
}
const NO_BROWSER = !!process.env.NO_BROWSER;

/* ---------- 子进程输出编码（Windows 中文乱码根因修复） ----------
 * 现象：子进程日志里的中文全部变成 “ʶ����ɣ�” 这类乱码，ASCII 部分（接口名、
 *       路径、时间）却完全正常。
 * 原因：Windows 中文环境下，当 Python 的 stdout/stderr 被重定向到“管道”时，
 *       CPython 不再走控制台 API，而是退回系统 ANSI 代码页（cp936/GBK）编码输出；
 *       而本启动器默认按 UTF-8 解码，GBK 字节被当成 UTF-8 解析 → 非 ASCII 全丢。
 * 修复：启动子进程前显式注入 UTF-8 相关环境变量，让子进程统一输出 UTF-8。
 *       某个服务若需特殊处理，可在 services.json 的 env 里覆盖（优先级更高）。
 */
const UTF8_ENV = {
  PYTHONUTF8: '1',           // 打开 Python UTF-8 模式（stdio / 文件系统 / open 默认编码）
  PYTHONIOENCODING: 'utf-8'  // 仅约束 stdio，作为双保险
};

/* ---------- 读取配置 ---------- */
const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'services.json'), 'utf8'));
const allServices = cfg.services || [];
const services = ONLY ? allServices.filter((s) => ONLY.includes(s.name)) : allServices;
const middlewares = ONLY ? [] : (cfg.middlewares || cfg.middleware || []);

/* ---------- 带颜色的日志 ---------- */
const RESET = '\x1b[0m';
const tagOf = (s) => `\x1b[${s.color || '90'}m[${s.title || s.name}]${RESET}`;
function log(s, msg) { console.log(`${tagOf(s)} ${msg}`); }
function info(msg) { console.log(`\x1b[90m[总控]${RESET} ${msg}`); }
function warn(msg) { console.log(`\x1b[33m[总控]${RESET} ⚠ ${msg}`); }

/* ---------- 端口健康探测 ---------- */
function probePort(port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let done = false;
    const finish = (ok) => { if (!done) { done = true; socket.destroy(); resolve(ok); } };
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
    socket.connect(port, '127.0.0.1');
  });
}

async function waitPort(port, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  let last = false;
  while (Date.now() < deadline) {
    if (await probePort(port)) return true;
    await new Promise((r) => setTimeout(r, 1000));
    last = false;
    void last;
  }
  return false;
}

/* ---------- 端口占用预检查 ----------
 * 为什么必须做：waitPort() 只能判断「端口能否连上」，无法区分「这是我启的服务」
 * 还是「别人的进程」。一旦端口事先就被占用（旧的残留服务、PyCharm 运行配置起的
 * 第二份、或 test/ 下的临时脚本），本启动器会把别人的进程当成自己「✓ 就绪」，
 * 用户看到的就是「明明显示就绪，过一会儿又全挂了」。
 * 这里在启动前先探测一次：端口若已被占用，明确警告并给出占用者。
 */
function isPortFree(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.unref();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, '127.0.0.1');
  });
}

async function preflightPorts(list) {
  const busy = [];
  for (const s of list) {
    if (!s.port) continue;
    if (!(await isPortFree(s.port))) busy.push(s);
  }
  if (!busy.length) return busy;
  warn('以下端口在启动前就已被占用，对应服务将无法绑定（日志中会出现 WinError 10048）:');
  for (const s of busy) warn(`  · ${s.title}  ${s.port}`);
  warn('请先停止占用者再启动，否则会出现「一个端口能用、另一个就不行」的现象。');
  warn('查占用者：netstat -ano | findstr :端口     结束：taskkill /PID <pid> /T /F');
  console.log('');
  return busy;
}

/* ---------- 打开浏览器 ---------- */
function openBrowser(url) {
  if (NO_BROWSER) return;
  try {
    if (IS_WIN) spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore' }).unref();
    else if (process.platform === 'darwin') spawn('open', [url], { detached: true, stdio: 'ignore' }).unref();
    else spawn('xdg-open', [url], { detached: true, stdio: 'ignore' }).unref();
    info(`已打开浏览器: ${url}`);
  } catch (e) {
    info(`请手动打开浏览器: ${url}`);
  }
}

/* ---------- 子进程管理 ---------- */
const children = [];
let shuttingDown = false;

function killAll() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const c of children) {
    try {
      if (IS_WIN) spawnSync('taskkill', ['/pid', String(c.pid), '/T', '/F'], { stdio: 'ignore' });
      else c.kill('SIGTERM');
    } catch (_) { /* 忽略 */ }
  }
}

process.on('SIGINT', () => {
  console.log('');
  info('收到退出信号，正在停止所有服务...');
  killAll();
  process.exit(0);
});
process.on('SIGTERM', () => { killAll(); process.exit(0); });
process.on('exit', () => killAll());

function pipeWithPrefix(child, s) {
  const pump = (stream, isError) => {
    // 用 StringDecoder 而不是 chunk.toString()：
    // chunk 边界可能正好切在中文的多个字节中间，直接 toString 会把一个字拆成乱码。
    const decoder = new StringDecoder('utf8');
    const emit = (line) => {
      const text = line.endsWith('\r') ? line.slice(0, -1) : line; // 去掉 CRLF 残留的 \r
      if (isError) console.error(`${tagOf(s)} ${text}`);
      else console.log(`${tagOf(s)} ${text}`);
    };
    let buf = '';
    stream.on('data', (chunk) => {
      buf += decoder.write(chunk);
      let idx;
      while ((idx = buf.indexOf('\n')) !== -1) {
        emit(buf.slice(0, idx));
        buf = buf.slice(idx + 1);
      }
    });
    stream.on('end', () => {
      buf += decoder.end();
      if (buf) emit(buf);
    });
  };
  pump(child.stdout, false);
  pump(child.stderr, true);
}

/* ---------- 中间件（Docker，异步执行） ----------
 * 必须用异步 spawn：Windows 下 spawnSync 的同步管道在父进程 stdio 被重定向时
 * 会抛 EBUSY（与是否启用 shell 无关），导致中间件永远拉不起来。
 */
function runMiddleware(m) {
  return new Promise((resolve) => {
    const mCwd = path.isAbsolute(m.cwd) ? m.cwd : path.join(ROOT, m.cwd);
    if (!fs.existsSync(mCwd)) {
      warn(`${m.title} 目录不存在: ${mCwd}${m.optional ? '（可选，跳过）' : ''}`);
      return resolve(true);
    }
    const parts = String(m.command).trim().split(/\s+/).filter(Boolean);
    log(m, `拉起中间件: ${m.command}`);
    let child;
    try {
      child = spawn(parts[0], parts.slice(1), {
        cwd: mCwd,
        env: { ...process.env, ...UTF8_ENV, ...(m.env || {}) },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
        shell: !!m.shell
      });
    } catch (e) {
      warn(`${m.title} 启动失败${m.optional ? '（可选，继续）' : ''} ${e.message}`);
      return resolve(false);
    }
    pipeWithPrefix(child, m);
    let errBuf = '';
    child.stderr.on('data', (d) => { errBuf += d.toString(); });
    const timer = setTimeout(() => {
      warn(`${m.title} 超过 180s 未退出，跳过等待继续启动其他服务`);
      try { child.kill(); } catch (_) {}
      resolve(true);
    }, 180000);
    child.on('error', (e) => {
      clearTimeout(timer);
      warn(`${m.title} 启动失败${m.optional ? '（可选，继续）' : ''} ${e.message}`);
      if (e.code === 'ENOENT') warn(`  ↳ 未找到命令「${parts[0]}」，请确认已安装并在 PATH 中（如 Docker Desktop）。`);
      resolve(false);
    });
    child.on('exit', (code) => {
      clearTimeout(timer);
      if (code === 0) {
        log(m, '中间件就绪');
      } else {
        const tail = (errBuf.trim().split('\n').pop() || '').slice(0, 140);
        warn(`${m.title} 退出码 ${code}${m.optional ? '（可选，继续）' : ''} ${tail}`);
      }
      resolve(code === 0);
    });
  });
}

/* ---------- 主流程 ---------- */
async function main() {
  console.log('==============================================');
  console.log('   智枢套件 · 一键启动');
  console.log(`   服务数: ${services.length}${ONLY ? ` (仅: ${ONLY.join(', ')})` : ''}`);
  console.log('==============================================');
  console.log('');

  /* 1. 中间件（Docker，可选，并行拉起） */
  if (middlewares.length) {
    info('正在拉起中间件（Docker）...');
    await Promise.all(middlewares.map(runMiddleware));
  }

  /* 1.5 端口占用预检查（避免把别人的进程误判为自己就绪） */
  await preflightPorts(services);

  /* 2. 拉起各服务 */
  for (const s of services) {
    const cwd = path.isAbsolute(s.cwd) ? s.cwd : path.join(ROOT, s.cwd);
    if (!fs.existsSync(cwd)) {
      warn(`${s.title} 目录不存在: ${cwd}${s.optional ? '（可选，跳过）' : ''}`);
      s._skipped = true;
      continue;
    }
    const [cmd, ...cmdArgs] = s.command;
    const child = spawn(cmd, cmdArgs, {
      cwd,
      env: { ...process.env, ...UTF8_ENV, ...(s.env || {}) },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      shell: !!s.shell
    });
    child._svc = s;
    children.push(child);
    pipeWithPrefix(child, s);
    log(s, `已启动 (pid=${child.pid})  ->  http://127.0.0.1:${s.port}`);

    child.on('exit', (code) => {
      if (shuttingDown) return;
      if (code === 0 || code === null) {
        log(s, `进程退出 (code=${code})`);
      } else {
        warn(`${s.title} 异常退出 (code=${code})，请查看上方日志${s.optional ? '（可选服务，其余不受影响）' : ''}`);
      }
    });
  }

  /* 3. 并行健康检查，全部就绪后提示访问地址 */
  const checks = services
    .filter((s) => !s._skipped && children.some((c) => c._svc === s))
    .map(async (s) => {
      const ok = await waitPort(s.port, s.readyTimeoutMs || 120000);
      if (ok) log(s, `✓ 就绪  http://127.0.0.1:${s.port}`);
      else warn(`${s.title} 在 ${Math.round((s.readyTimeoutMs || 120000) / 1000)}s 内未就绪（首次启动可能在装依赖/加载模型，可稍后手动访问）`);
      return { s, ok };
    });

  const results = await Promise.all(checks);
  const workbench = results.find((r) => r.s.name === 'workbench' && r.ok);
  const firstOk = results.find((r) => r.ok);

  console.log('');
  console.log('----------------------------------------------');
  info('当前可用入口：');
  for (const r of results) {
    if (r.ok) info(`  ${r.s.title.padEnd(10, '\u3000')} http://127.0.0.1:${r.s.port}`);
  }
  console.log('----------------------------------------------');

  const target = (cfg.openBrowser && workbench) ? cfg.openBrowser : (firstOk ? `http://127.0.0.1:${firstOk.s.port}` : null);
  if (target) openBrowser(target);

  info('按 Ctrl+C 可一次性停止所有服务');
}

main().catch((e) => { warn(`启动失败: ${e.message}`); killAll(); process.exit(1); });
