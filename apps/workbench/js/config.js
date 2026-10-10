/**
 * 智枢智能工作台 - 站点配置
 * ---------------------------------------------------------------
 * 增删智能体卡片、改标题、改跳转地址，只需要改这个文件，
 * 不需要动 index.html / main.js / style.css。
 *
 * 端口分配（与 services.json 保持一致）：
 *   智枢问数   前端(Vite) -> 5173（/api 代理到后端 8000，前端即完整功能入口）
 *   智枢知库   合并页     -> 8080/kb/（问答+导入合体页，由工作台托管；
 *                                   页面跨域调用 :8001 问答 API 与 :8004 导入 API，
 *                                   两个后端已开 CORS，后端代码零改动）
 */
window.WORKBENCH_CONFIG = {

  // 顶部标题与副标题
  title: '智枢智能工作台',
  subtitle: '统一入口，连接数据与知识',

  // 智能体卡片列表（顺序即展示顺序；theme: blue | teal | wine）
  // 点击卡片任意位置都会在新标签页打开 url
  agents: [
    {
      id: 'data-agent',
      title: '智枢问数',
      subtitle: '数据查询智能体',
      theme: 'blue',
      url: 'http://localhost:5173/'
    },
    {
      id: 'knowledge-base',
      title: '智枢知库',
      subtitle: '知识库智能体',
      theme: 'teal',
      url: 'http://127.0.0.1:8080/kb/'
    }
  ],

  // 「更多智能体」按钮点击时的提示文案
  moreTip: '更多智能体正在接入中，敬请期待'
};

/* 如需恢复「智枢审约」卡片，在 agents 数组中追加：
{
  id: 'contract-review',
  title: '智枢审约',
  subtitle: '合同审查智能体',
  theme: 'wine',
  url: 'http://127.0.0.1:8003/'
}
并在 multi-agent/services.json 的 services 中恢复 contract 服务条目。 */

