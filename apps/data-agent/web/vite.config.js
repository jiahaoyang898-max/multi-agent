import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端作为独立工程运行，通过 Vite 开发代理把 /api 同源转发到后端 8000 端口。
// 这样浏览器不会触发跨域（后端未开启 CORS），且完全不需要改动任何后端代码。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    // strictPort：5173 被占用时"直接报错退出"，而不是静默漂移到 5174。
    // 静默漂移是「一个端口能用、另一个就不行」的元凶之一：
    // 工作台 apps/workbench/js/config.js 里写死了 http://localhost:5173/，
    // 一旦 Vite 悄悄跑到 5174，工作台入口就指向了一个不存在的实例。
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('Cache-Control', 'no-cache')
            proxyReq.setHeader('Connection', 'keep-alive')
          })
        },
      },
    },
  },
})
