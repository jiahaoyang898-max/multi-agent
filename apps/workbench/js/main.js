/**
 * 智枢企业智能工作台 - 页面渲染与交互
 * 依据 window.WORKBENCH_CONFIG 渲染卡片 / 分页指示器，并处理点击跳转。
 */
(function () {
  'use strict';

  var cfg = window.WORKBENCH_CONFIG || {};
  var agents = cfg.agents || [];

  /* ---------- 图标库（内联线性 SVG，统一 stroke 风格） ---------- */
  var ICONS = {
    'data-agent': {
      badge:
        '<svg viewBox="0 0 24 24">' +
        '<line x1="4" y1="20" x2="20" y2="20"/>' +
        '<rect x="5" y="11" width="3.2" height="9" rx="1.2"/>' +
        '<rect x="10.4" y="6" width="3.2" height="14" rx="1.2"/>' +
        '<rect x="15.8" y="13" width="3.2" height="7" rx="1.2"/></svg>',
      viz:
        '<svg viewBox="0 0 150 120">' +
        '<rect class="fill-blue" x="22" y="40" width="20" height="60" rx="4"/>' +
        '<rect class="fill-blue" x="50" y="24" width="20" height="76" rx="4"/>' +
        '<rect class="fill-blue" x="78" y="52" width="20" height="48" rx="4"/>' +
        '<line class="stroke-blue" x1="14" y1="100" x2="120" y2="100"/>' +
        '<rect class="stroke-blue" x="22" y="40" width="20" height="60" rx="4"/>' +
        '<rect class="stroke-blue" x="50" y="24" width="20" height="76" rx="4"/>' +
        '<rect class="stroke-blue" x="78" y="52" width="20" height="48" rx="4"/>' +
        '<path class="stroke-blue" d="M104 30 h34 a6 6 0 0 1 6 6 v18 a6 6 0 0 1 -6 6 h-22 l-10 9 v-9 h-2 a6 6 0 0 1 -6 -6 v-18 a6 6 0 0 1 6 -6 z"/>' +
        '<line class="stroke-blue" x1="114" y1="44" x2="134" y2="44"/>' +
        '<line class="stroke-blue" x1="114" y1="54" x2="128" y2="54"/></svg>'
    },
    'knowledge-base': {
      badge:
        '<svg viewBox="0 0 24 24">' +
        '<path d="M12 6.5c-2.2-1.3-5-1.3-7.2 0v11c2.2-1.3 5-1.3 7.2 0 2.2-1.3 5-1.3 7.2 0v-11c-2.2-1.3-5-1.3-7.2 0z"/>' +
        '<line x1="12" y1="6.5" x2="12" y2="17.5"/></svg>',
      viz:
        '<svg viewBox="0 0 150 120">' +
        '<rect class="stroke-teal" x="26" y="34" width="44" height="56" rx="6"/>' +
        '<rect class="stroke-teal fill-teal" x="36" y="26" width="44" height="56" rx="6"/>' +
        '<line class="stroke-teal" x1="44" y1="40" x2="72" y2="40"/>' +
        '<line class="stroke-teal" x1="44" y1="50" x2="72" y2="50"/>' +
        '<line class="stroke-teal" x1="44" y1="60" x2="64" y2="60"/>' +
        '<circle class="stroke-teal" cx="104" cy="62" r="16"/>' +
        '<line class="stroke-teal" x1="116" y1="74" x2="128" y2="86"/>' +
        '<line class="stroke-teal" x1="98" y1="62" x2="110" y2="62"/>' +
        '<line class="stroke-teal" x1="104" y1="56" x2="104" y2="68"/>' +
        '<path class="stroke-teal" d="M80 54 C 92 54, 92 62, 88 62" stroke-dasharray="3 4"/></svg>'
    },
    'contract-review': {
      badge:
        '<svg viewBox="0 0 24 24">' +
        '<path d="M7 3 h7 l5 5 v13 a1 1 0 0 1 -1 1 H7 a1 1 0 0 1 -1 -1 V4 a1 1 0 0 1 1 -1z"/>' +
        '<path d="M14 3 v5 h5"/>' +
        '<path d="M9 13 l2 2 3.5 -4"/></svg>',
      viz:
        '<svg viewBox="0 0 150 120">' +
        '<path class="stroke-wine" d="M30 22 h44 l16 16 v58 a2 2 0 0 1 -2 2 H30 a2 2 0 0 1 -2 -2 V24 a2 2 0 0 1 2 -2z"/>' +
        '<path class="stroke-wine" d="M74 22 v16 h16"/>' +
        '<line class="stroke-wine" x1="38" y1="52" x2="80" y2="52"/>' +
        '<line class="stroke-wine" x1="38" y1="64" x2="80" y2="64"/>' +
        '<line class="stroke-wine" x1="38" y1="76" x2="66" y2="76"/>' +
        '<circle class="stroke-wine" cx="100" cy="40" r="14"/>' +
        '<circle class="stroke-wine" cx="100" cy="40" r="8"/>' +
        '<line class="stroke-wine" x1="92" y1="40" x2="108" y2="40"/>' +
        '<rect class="stroke-wine" x="86" y="70" width="40" height="30" rx="5"/>' +
        '<path class="stroke-wine" d="M94 82 l4 4 8 -9"/>' +
        '<line class="stroke-wine" x1="110" y1="82" x2="120" y2="82"/>' +
        '<line class="stroke-wine" x1="94" y1="92" x2="120" y2="92"/></svg>'
    },
    // 兜底图标（新增智能体 id 未上图标库时使用）
    _default: {
      badge:
        '<svg viewBox="0 0 24 24">' +
        '<rect x="4" y="4" width="16" height="16" rx="3"/>' +
        '<line x1="8" y1="12" x2="16" y2="12"/></svg>',
      viz:
        '<svg viewBox="0 0 150 120">' +
        '<circle class="stroke-blue" cx="75" cy="60" r="30"/></svg>'
    }
  };

  /* ---------- 头部文案 ---------- */
  if (cfg.title) {
    document.getElementById('app-title').textContent = cfg.title;
    document.title = cfg.title;
  }
  if (cfg.subtitle) {
    document.getElementById('app-subtitle').textContent = cfg.subtitle;
  }

  /* ---------- 渲染卡片 ---------- */
  var cardsBox = document.getElementById('cards');
  cardsBox.innerHTML = agents.map(function (a) {
    var icon = ICONS[a.id] || ICONS._default;
    var theme = a.theme || 'blue';
    return (
      '<section class="card" tabindex="0" role="link" data-url="' + (a.url || '#') + '"' +
        ' aria-label="打开 ' + a.title + '">' +
        '<div class="badge ' + theme + '">' + icon.badge + '</div>' +
        '<h2>' + a.title + '</h2>' +
        '<div class="sub">' + (a.subtitle || '') + '</div>' +
        '<div class="viz ' + theme + '">' + icon.viz + '</div>' +
      '</section>'
    );
  }).join('');

  function openAgent(card) {
    var url = card.getAttribute('data-url');
    if (!url || url === '#') return;
    window.open(url, '_blank', 'noopener');
  }

  cardsBox.addEventListener('click', function (e) {
    var card = e.target.closest('.card');
    if (card) openAgent(card);
  });
  cardsBox.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var card = e.target.closest('.card');
    if (card) { e.preventDefault(); openAgent(card); }
  });

  /* ---------- 分页指示器（数量跟随卡片数，首个高亮） ---------- */
  var dotsBox = document.getElementById('dots');
  dotsBox.innerHTML = agents.map(function (a, i) {
    return '<span class="' + (i === 0 ? 'on' : '') + '"></span>';
  }).join('');

  /* ---------- 轻提示 ---------- */
  var toast = document.getElementById('toast');
  var toastTimer = null;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 2200);
  }

  document.getElementById('more-btn').addEventListener('click', function () {
    showToast(cfg.moreTip || '更多智能体正在接入中');
  });
})();
