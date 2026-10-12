/**
 * 智枢智能工作台 - 零依赖静态服务器
 * 用法: node server.js  (或 npm start)
 * 端口: 默认 8080，可用环境变量 PORT 覆盖
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 8080;
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

const server = http.createServer((req, res) => {
  let urlPath;
  try {
    urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  } catch (e) {
    res.writeHead(400); return res.end('Bad Request');
  }
  if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
  // 子目录形式（如 /kb/）自动补 index.html
  if (urlPath.endsWith('/')) urlPath += 'index.html';

  const filePath = path.join(ROOT, path.normalize(urlPath));

  // 防目录穿越
  if (!(filePath === ROOT || filePath.startsWith(ROOT + path.sep))) {
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
