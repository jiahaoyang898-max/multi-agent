#!/usr/bin/env node
/**
 * 登录 / 注册页 · 独立启动器（零依赖，仅用 Node 内置模块）
 *
 * 用法：
 *     cd apps/workbench/login
 *     npm start                     # 打开 http://127.0.0.1:8090/
 *     PORT=9000 npm start           # 指定端口
 *     NO_BROWSER=1 npm start        # 不自动开浏览器（CI / 远程终端用）
 *
 * 特点：
 *   · 只托管本目录，**不依赖 Docker / Python / 后端服务**，无需联网，秒开。
 *   · 端口默认 8090；若被占用会自动向后找一个空闲端口，并在控制台打印真实地址。
 *   · 每次请求实时读盘，改完 html/css/js 刷新浏览器即可，无需重启。
 *
 * 与整套系统的关系：
 *   · 本文件只是"单独看这个页面"的快捷方式，不影响原有任何启动方式。
 *   · 用仓库根目录的 `npm start` 启动整套时，本页面地址是
 *     http://127.0.0.1:8080/login/  （由 apps/workbench/server.js 托管）。
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const {spawn} = require('child_process');

const ROOT = __dirname;
const BASE_PORT = Number(process.env.PORT) || 8090;
const MAX_TRIES = 20;
const HOST = '127.0.0.1';

const NO_BROWSER =
    /^(1|true|yes|on)$/i.test(String(process.env.NO_BROWSER || '')) ||
    process.argv.includes('--no-open');

const MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.map': 'application/json; charset=utf-8',
};

function notFound(res, urlPath) {
    res.writeHead(404, {'Content-Type': 'text/html; charset=utf-8'});
    res.end(
        '<!doctype html><meta charset="utf-8"><title>404</title>' +
        '<style>body{font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;' +
        'padding:48px;color:#1d1d1f;background:#fbfcfe}code{background:#eef3f9;padding:2px 6px;border-radius:5px}</style>' +
        '<h2>404 Not Found</h2><p>本启动器只托管登录页目录，找不到：<code>' +
        urlPath.replace(/[<>&]/g, '') +
        '</code></p><p><a href="/">返回登录页</a></p>'
    );
}

function serve(req, res) {
    let urlPath;
    try {
        urlPath = decodeURIComponent((req.url || '/').split('?')[0].split('#')[0]);
    } catch (e) {
        res.writeHead(400, {'Content-Type': 'text/plain; charset=utf-8'});
        return res.end('Bad Request');
    }

    // 显式拒绝含 ".." 段、反斜杠或空字节的路径（Windows 上 normalize 可能被绕过）
    if (urlPath.includes('\\') || urlPath.includes('\0') || urlPath.split('/').includes('..')) {
        res.writeHead(403, {'Content-Type': 'text/plain; charset=utf-8'});
        return res.end('Forbidden');
    }

    if (urlPath === '' || urlPath === '/') urlPath = '/index.html';
    else if (urlPath.endsWith('/')) urlPath += 'index.html';

    const filePath = path.join(ROOT, path.normalize(urlPath));

    // 防目录穿越
    if (!(filePath === ROOT || filePath.startsWith(ROOT + path.sep))) {
        res.writeHead(403, {'Content-Type': 'text/plain; charset=utf-8'});
        return res.end('Forbidden');
    }

    fs.readFile(filePath, (err, data) => {
        if (err) return notFound(res, urlPath);
        const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
        res.writeHead(200, {
            'Content-Type': type,
            'Cache-Control': 'no-cache, no-store, must-revalidate',
        });
        res.end(data);
    });
}

function openBrowser(url) {
    if (NO_BROWSER) return;
    let cmd;
    let args;
    if (process.platform === 'win32') {
        cmd = 'cmd';
        args = ['/c', 'start', '', url];
    } else if (process.platform === 'darwin') {
        cmd = 'open';
        args = [url];
    } else {
        cmd = 'xdg-open';
        args = [url];
    }
    try {
        spawn(cmd, args, {stdio: 'ignore', detached: true}).unref();
    } catch (e) {
        /* 打不开浏览器不影响服务 */
    }
}

function banner(port) {
    const url = `http://${HOST}:${port}/`;
    const line = '═'.repeat(52);
    console.log('');
    console.log(line);
    console.log('  智枢 · 登录 / 注册页  已启动');
    console.log(line);
    console.log(`  本页地址      ${url}`);
    console.log(`  页面内"进入工作台"在独立模式下会回到本页`);
    console.log(`  （整套系统下为 http://127.0.0.1:8080/login/）`);
    console.log('');
    console.log('  停止：Ctrl + C');
    console.log(line);
    console.log('');
}

function listen(port, attempt) {
    const server = http.createServer(serve);

    server.once('error', (err) => {
        if (err.code === 'EADDRINUSE' && attempt < MAX_TRIES) {
            console.log(`  · 端口 ${port} 已被占用，尝试 ${port + 1} …`);
            return listen(port + 1, attempt + 1);
        }
        console.error(`\n  启动失败：${err.code || err.message}\n`);
        process.exit(1);
    });

    server.listen(port, HOST, () => {
        banner(port);
        openBrowser(`http://${HOST}:${port}/`);
    });

    const bye = () => {
        server.close(() => process.exit(0));
        setTimeout(() => process.exit(0), 400).unref();
    };
    process.once('SIGINT', bye);
    process.once('SIGTERM', bye);

    return server;
}

listen(BASE_PORT, 0);
