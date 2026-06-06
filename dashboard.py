"""Webダッシュボード - スーパー分析ボット版 (Flask, port 5057)"""
import json
import logging
import time

from flask import Flask, jsonify, request

from analyzer import analyze, get_chart_data
from config import SIGNALS_FILE
from kabuto_agent import (
    AGENT_LOG_FILE, ANALYSIS_CACHE_FILE, MARKET_CACHE_FILE,
    PTS_CACHE_FILE, SENTIMENT_CACHE_FILE,
)
from scheduler import log_signal

log = logging.getLogger(__name__)

_chart_cache: dict = {}

_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>kabutobot - スーパー分析ボット</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#f5f5f7;--card:#fff;--bd:#d2d2d7;--tx:#1d1d1f;--sub:#6e6e73;
  --g:#34c759;--r:#ff3b30;--b:#007aff;--y:#ff9f0a;--pu:#af52de;--cy:#00c7be;
  --sh:0 2px 12px rgba(0,0,0,.07);--rr:12px
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:var(--bg);color:var(--tx);font-size:14px}

/* ── Header ── */
header{background:#fff;border-bottom:1px solid var(--bd);padding:0 24px;
  position:sticky;top:0;z-index:100}
.h-top{display:flex;align-items:center;gap:12px;padding:12px 0 8px}
header h1{font-size:19px;font-weight:700;letter-spacing:-.3px}
header .sub{color:var(--sub);font-size:11px;margin-top:1px}
.h-actions{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.mkt-bar{display:flex;gap:0;border-top:1px solid var(--bg);
  overflow-x:auto;padding:6px 0 8px}
.mkt-item{display:flex;flex-direction:column;padding:0 18px 0;
  border-right:1px solid var(--bd);min-width:100px}
.mkt-item:first-child{padding-left:0}
.mkt-item .mn{font-size:10px;color:var(--sub);margin-bottom:2px}
.mkt-item .mp{font-size:14px;font-weight:700}
.mkt-item .mc{font-size:11px;margin-top:1px}

/* ── Layout ── */
.wrap{max-width:1500px;margin:0 auto;padding:20px 24px}

/* ── Stats ── */
.sgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px;margin-bottom:20px}
.scard{background:var(--card);border-radius:var(--rr);padding:16px 18px;
  box-shadow:var(--sh);border-top:3px solid transparent}
.scard.buy{border-top-color:var(--g)}
.scard.sell{border-top-color:var(--r)}
.scard.pts{border-top-color:var(--y)}
.scard.total{border-top-color:var(--b)}
.scard .sl{font-size:10px;font-weight:600;text-transform:uppercase;
  letter-spacing:.4px;color:var(--sub);margin-bottom:6px}
.scard .sv{font-size:26px;font-weight:700;line-height:1}
.scard .sc{font-size:11px;margin-top:5px;color:var(--sub)}

/* ── Analysis Grid Header ── */
.ag-header{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.ag-title{font-size:16px;font-weight:600}
.filter-btns{display:flex;gap:6px;margin-left:auto}
.fb{padding:5px 12px;border:1px solid var(--bd);border-radius:20px;
  background:#fff;cursor:pointer;font-size:12px;font-weight:500;
  color:var(--sub);transition:.15s}
.fb:hover{border-color:var(--b);color:var(--b)}
.fb.active{background:var(--b);border-color:var(--b);color:#fff}
.fb.buy.active{background:var(--g);border-color:var(--g);color:#fff}
.fb.sell.active{background:var(--r);border-color:var(--r);color:#fff}

/* ── Analysis Grid ── */
.ag{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:12px;margin-bottom:28px}
.ac{background:var(--card);border-radius:var(--rr);padding:14px;
  box-shadow:var(--sh);cursor:pointer;transition:.15s;
  border:2px solid transparent;position:relative}
.ac:hover{border-color:var(--b);transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(0,0,0,.1)}
.ac.buy{border-color:var(--g)}
.ac.sell{border-color:var(--r)}
.ac.hidden{display:none}
.ac-head{display:flex;justify-content:space-between;align-items:flex-start;
  margin-bottom:8px}
.ac-ticker{font-size:15px;font-weight:700;line-height:1.2}
.ac-name{font-size:11px;color:var(--sub);margin-top:2px}
.ac-price{font-size:15px;font-weight:700;text-align:right}
.ac-chg{font-size:12px;text-align:right;margin-top:2px}
.ac-spark{margin:6px 0}
.rsi-row{display:flex;align-items:center;gap:8px;margin:6px 0}
.rsi-track{flex:1;height:5px;background:#eee;border-radius:3px;overflow:hidden}
.rsi-fill{height:100%;border-radius:3px;transition:.3s}
.rsi-val{font-size:11px;font-weight:600;min-width:24px;text-align:right}
.ac-ma{font-size:11px;color:var(--sub);margin:3px 0}
.ac-footer{display:flex;justify-content:space-between;align-items:center;
  margin-top:8px;flex-wrap:wrap;gap:4px}
.ac-loading{text-align:center;padding:48px;color:var(--sub);
  grid-column:1/-1;font-size:13px}

/* ── Tabs ── */
.tabs{background:var(--card);border-radius:var(--rr);box-shadow:var(--sh);overflow:hidden}
.tnav{display:flex;border-bottom:1px solid var(--bd)}
.tb{padding:13px 18px;border:none;background:none;cursor:pointer;
  font-size:13px;font-weight:500;color:var(--sub);
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:.15s}
.tb.active{color:var(--b);border-bottom-color:var(--b)}
.tc{display:none;padding:20px}
.tc.active{display:block}

/* ── Tables ── */
table{width:100%;border-collapse:collapse}
th{font-size:11px;font-weight:600;text-transform:uppercase;color:var(--sub);
  padding:8px 12px;text-align:left;border-bottom:1px solid var(--bd)}
td{padding:9px 12px;border-bottom:1px solid var(--bd);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafafa}

/* ── Badges ── */
.badge{display:inline-block;padding:2px 8px;border-radius:6px;
  font-size:11px;font-weight:700}
.bb{background:#e8f5e9;color:#2e7d32}
.bs{background:#ffebee;color:#c62828}
.bh{background:#f5f5f5;color:#666}
.bp{background:#fff3e0;color:#e65100}

/* ── Buttons ── */
.btn{padding:7px 14px;border:none;border-radius:8px;cursor:pointer;
  font-size:12px;font-weight:600;transition:.15s;white-space:nowrap}
.btn:hover{opacity:.85}
.btn-r{background:var(--r);color:#fff}
.btn-b{background:var(--b);color:#fff}
.btn-g{background:var(--g);color:#fff}
.btn-y{background:var(--y);color:#fff}
.btn-outline{background:#fff;color:var(--b);border:1px solid var(--b)}
.btn-outline.off{color:var(--sub);border-color:var(--bd)}
.btn-sm{padding:4px 10px;font-size:11px}

/* ── Watchlist ── */
.wlg{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.wls h3{margin-bottom:10px;font-size:14px}
.si{display:flex;justify-content:space-between;align-items:center;
  padding:9px 12px;border-bottom:1px solid var(--bd)}
.si:last-child{border-bottom:none}
.af{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.af input,.af select{padding:7px 12px;border:1px solid var(--bd);
  border-radius:8px;font-size:13px;outline:none}
.af input:focus,.af select:focus{border-color:var(--b)}
.af input{flex:1;min-width:120px}
.empty{text-align:center;padding:40px;color:var(--sub);font-size:13px}

/* ── Chart Canvases ── */
.chart-wrap{position:relative;height:300px;margin-bottom:12px}
.chart-wrap-md{position:relative;height:180px;margin-bottom:12px}
.chart-wrap-sm{position:relative;height:140px;margin-bottom:12px}
.chart-label{font-size:11px;font-weight:600;color:var(--sub);
  margin:14px 0 6px;text-transform:uppercase;letter-spacing:.3px}

/* ── Agent Log ── */
.alog{max-height:480px;overflow-y:auto}
.alog-item{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid var(--bd)}
.alog-time{font-size:11px;color:var(--sub);min-width:120px;white-space:nowrap}
.alog-msg{font-size:13px;word-break:break-all}
.alog-status{background:#f0f4ff;border-radius:8px;padding:10px 14px;
  margin-bottom:14px;font-size:12px;color:var(--sub);line-height:1.6}

/* ── Modal ── */
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);
  z-index:1000;justify-content:center;align-items:flex-start;padding:20px;
  overflow-y:auto}
.overlay.open{display:flex}
.modal{background:#fff;border-radius:16px;padding:24px;
  width:min(940px,100%);margin:auto}
.modal-head{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:16px}
.modal-head h2{font-size:19px;font-weight:700}
.close-btn{background:none;border:none;font-size:22px;cursor:pointer;
  color:var(--sub);line-height:1;padding:4px 8px}
.modal-kv{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.kv{background:#f5f5f7;padding:10px 14px;border-radius:8px;min-width:110px}
.kv .kl{font-size:10px;color:var(--sub);margin-bottom:4px;text-transform:uppercase}
.kv .kv2{font-size:18px;font-weight:700}

/* ── News List ── */
.news-item{padding:8px 0;border-bottom:1px solid var(--bd)}
.news-item:last-child{border-bottom:none}
.news-title{font-size:13px;line-height:1.4}
.news-title a{color:var(--tx);text-decoration:none}
.news-title a:hover{color:var(--b)}
.news-meta{font-size:11px;color:var(--sub);margin-top:3px}
.news-score-pos{color:var(--g);font-weight:600}
.news-score-neg{color:var(--r);font-weight:600}

/* ── PTS Info ── */
.pts-bar{display:flex;align-items:center;gap:12px;padding:10px 14px;
  background:#fff3e0;border-radius:8px;margin-bottom:14px;flex-wrap:wrap}
.pts-bar .pts-label{font-size:12px;color:#e65100;font-weight:600}

/* ── Misc ── */
.pos{color:var(--g)}.neg{color:var(--r)}
.ts{font-size:11px;color:var(--sub)}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #ddd;
  border-top-color:var(--b);border-radius:50%;animation:spin .7s linear infinite;
  vertical-align:middle}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--g);margin-right:5px;animation:pulse 2s ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ── Screener ── */
.sc-region{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.sc-rb{padding:7px 16px;border:1px solid var(--bd);border-radius:20px;
  background:#fff;cursor:pointer;font-size:13px;font-weight:500;
  color:var(--sub);transition:.15s}
.sc-rb.active{background:var(--b);border-color:var(--b);color:#fff}
.sc-cats{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;
  padding-bottom:12px;border-bottom:1px solid var(--bd)}
.sc-cat{padding:5px 12px;border:1px solid var(--bd);border-radius:20px;
  background:#fff;cursor:pointer;font-size:12px;color:var(--sub);transition:.15s}
.sc-cat.active{background:var(--pu);border-color:var(--pu);color:#fff}
.sc-list-grid{display:flex;flex-direction:column;gap:0}
.sc-row{display:flex;align-items:center;justify-content:space-between;
  padding:10px 12px;border-bottom:1px solid var(--bd)}
.sc-row:last-child{border-bottom:none}
.sc-row:hover{background:#fafafa}
.sc-info{flex:1;cursor:pointer}
.sc-info:hover .sc-name{color:var(--b)}
.sc-name{font-size:14px;font-weight:600}
.sc-ticker{font-size:11px;color:var(--sub);margin-top:1px}
.sc-count{font-size:11px;color:var(--sub);margin-left:auto;margin-right:8px}

/* ── Sentiment Panel ── */
.sent-panel{background:#f5f5f7;border-radius:8px;padding:12px 14px;margin-bottom:12px}
.sent-score-bar{height:6px;border-radius:3px;background:#ddd;margin:6px 0;overflow:hidden}
.sent-score-fill{height:100%;border-radius:3px;transition:.4s}

/* ── Responsive ── */
@media(max-width:600px){
  .wlg{grid-template-columns:1fr}
  .h-actions{gap:6px}
  header .sub{display:none}
}
</style>
</head>
<body>
<header>
  <div class="h-top">
    <div>
      <h1>📊 kabutobot</h1>
      <div class="sub"><span class="dot"></span>スーパー分析ボット</div>
    </div>
    <div class="h-actions">
      <button class="btn btn-outline" id="auto-btn" onclick="toggleAuto()">⏱ 自動更新: ON</button>
      <button class="btn btn-b" id="scan-btn" onclick="manualScan()">🔄 今すぐスキャン</button>
      <button class="btn btn-outline" id="pull-btn" onclick="gitPull()" title="GitHubから最新コードを取得して再起動">⬇️ アップデート</button>
      <span class="ts" id="ts" style="min-width:120px;text-align:right"></span>
    </div>
  </div>
  <div class="mkt-bar" id="mkt-bar">
    <div class="mkt-item"><div class="mn">読み込み中...</div><div class="mp">—</div></div>
  </div>
</header>

<div class="wrap">
  <!-- Stats Cards -->
  <div class="sgrid" id="stats">
    <div class="scard total"><div class="sl">スキャン銘柄</div><div class="sv">—</div></div>
    <div class="scard buy"><div class="sl">BUYシグナル</div><div class="sv">—</div></div>
    <div class="scard sell"><div class="sl">SELLシグナル</div><div class="sv">—</div></div>
    <div class="scard pts"><div class="sl">PTS更新</div><div class="sv">—</div></div>
  </div>

  <!-- Analysis Grid -->
  <div class="ag-header">
    <span class="ag-title">📈 銘柄分析</span>
    <span class="ts" id="ag-updated"></span>
    <div class="filter-btns">
      <button class="fb active" onclick="filterCards('all')">全て</button>
      <button class="fb buy" onclick="filterCards('buy')">🟢 BUY</button>
      <button class="fb sell" onclick="filterCards('sell')">🔴 SELL</button>
    </div>
  </div>
  <div class="ag" id="ag">
    <div class="ac-loading"><span class="spinner"></span> エージェントスキャン中...</div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tnav">
      <button class="tb active" onclick="showTab('signals')">📋 シグナル履歴</button>
      <button class="tb" onclick="showTab('wl')">👁 監視銘柄</button>
      <button class="tb" onclick="showTab('screener')">🔍 スクリーナー</button>
      <button class="tb" onclick="showTab('agent')">🤖 エージェント</button>
    </div>
    <div id="tab-signals" class="tc active"><div id="signals-body"></div></div>
    <div id="tab-wl" class="tc">
      <div class="af">
        <input id="tk" placeholder="ティッカー (例: 7203.T / AAPL)">
        <input id="nm" placeholder="銘柄名">
        <select id="mkt">
          <option value="JP">🇯🇵 日本株</option>
          <option value="US">🇺🇸 米国株</option>
        </select>
        <button class="btn btn-b" onclick="addStock()">+ 追加</button>
      </div>
      <div class="wlg" id="wl-body"></div>
    </div>
    <div id="tab-agent" class="tc">
      <div class="alog-status" id="agent-status">読み込み中...</div>
      <div class="alog" id="agent-log"></div>
    </div>
    <div id="tab-screener" class="tc">
      <div style="margin-bottom:14px">
        <input id="sc-search" type="text" placeholder="🔍 銘柄名・ティッカーで検索（全カテゴリ）..."
          oninput="filterScreener()"
          style="width:100%;padding:9px 14px;border:1px solid var(--bd);
                 border-radius:8px;font-size:13px;outline:none">
      </div>
      <div class="sc-region">
        <button class="sc-rb active" onclick="showRegion('JP')">🇯🇵 日本株</button>
        <button class="sc-rb" onclick="showRegion('US')">🇺🇸 米国株</button>
        <button class="sc-rb" onclick="showRegion('OTHER')">🌐 その他</button>
      </div>
      <div class="sc-cats" id="sc-cats"></div>
      <div id="sc-list"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>
  </div>
</div>

<!-- Chart Modal -->
<div class="overlay" id="overlay" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-head">
      <div>
        <h2 id="modal-title"></h2>
        <div class="ts" id="modal-sub"></div>
      </div>
      <button class="close-btn" onclick="closeOverlay()">✕</button>
    </div>
    <div class="modal-kv" id="modal-stats"><span class="spinner"></span></div>
    <div id="modal-pts"></div>
    <div class="chart-label">価格 + 移動平均 + ボリンジャーバンド</div>
    <div class="chart-wrap"><canvas id="price-chart"></canvas></div>
    <div class="chart-label">MACD (12, 26, 9)</div>
    <div class="chart-wrap-md"><canvas id="macd-chart"></canvas></div>
    <div class="chart-label">RSI (14日)</div>
    <div class="chart-wrap-sm"><canvas id="rsi-chart"></canvas></div>
    <div id="modal-news" style="display:none;margin-top:4px"></div>
  </div>
</div>

<script>
let curTab    = 'signals';
let autoFlag  = true;
let autoTimer = null;
let priceChart = null, rsiChart = null, macdChart = null;
const $ = id => document.getElementById(id);
const pc = v => v >= 0 ? 'pos' : 'neg';
const ps = (v, d=2) => (v >= 0 ? '+' : '') + v.toFixed(d) + '%';
const qf = (v, cur) => cur === 'JPY'
  ? '¥' + Math.round(v).toLocaleString()
  : '$' + parseFloat(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:4});

// ─── Auto Refresh ───
function toggleAuto() {
  autoFlag = !autoFlag;
  const btn = $('auto-btn');
  if (autoFlag) {
    btn.textContent = '⏱ 自動更新: ON';
    btn.className   = 'btn btn-outline';
    startAuto();
  } else {
    btn.textContent = '⏱ 自動更新: OFF';
    btn.className   = 'btn btn-outline off';
    if (autoTimer) clearInterval(autoTimer);
  }
}
function startAuto() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = setInterval(refreshAll, 30000);
}
function refreshAll() {
  loadMarket(); loadStats(); loadAnalysis(); loadTab(curTab);
  $('ts').textContent = '更新: ' + new Date().toLocaleTimeString('ja-JP');
}

// ─── Market ───
async function loadMarket() {
  try {
    const d = await (await fetch('/api/market')).json();
    const items = Object.values(d.data || {});
    if (!items.length) return;
    $('mkt-bar').innerHTML = items.map(m => {
      const up = m.change_pct >= 0;
      return `<div class="mkt-item">
        <div class="mn">${m.name}</div>
        <div class="mp">${m.price >= 1000
          ? m.price.toLocaleString('ja-JP',{maximumFractionDigits:0})
          : m.price.toFixed(2)}</div>
        <div class="mc ${up?'pos':'neg'}">${up?'▲':'▼'} ${Math.abs(m.change_pct).toFixed(2)}%</div>
      </div>`;
    }).join('');
  } catch(e) {}
}

// ─── Stats ───
async function loadStats() {
  try {
    const s = await (await fetch('/api/stats')).json();
    const lastScan = s.last_scan
      ? new Date(s.last_scan).toLocaleTimeString('ja-JP')
      : '未実行';
    $('stats').innerHTML = `
      <div class="scard total">
        <div class="sl">スキャン銘柄</div>
        <div class="sv">${s.scan_count || 0}</div>
        <div class="sc">銘柄監視中</div>
      </div>
      <div class="scard buy">
        <div class="sl">BUYシグナル</div>
        <div class="sv pos">${s.buy_count || 0}</div>
        <div class="sc pos">買い推奨</div>
      </div>
      <div class="scard sell">
        <div class="sl">SELLシグナル</div>
        <div class="sv neg">${s.sell_count || 0}</div>
        <div class="sc neg">売り推奨</div>
      </div>
      <div class="scard pts">
        <div class="sl">PTS更新</div>
        <div class="sv" style="color:var(--y)">${s.pts_count || 0}</div>
        <div class="sc">時間外変動検知</div>
      </div>`;
    $('ts').textContent = '最終スキャン: ' + lastScan;
  } catch(e) {}
}

// ─── Analysis Grid ───
function sparkline(prices) {
  if (!prices || prices.length < 2) return '';
  const mn = Math.min(...prices), mx = Math.max(...prices);
  const rng = mx - mn || 1;
  const W = 88, H = 30;
  const pts = prices.map((p,i) =>
    `${(i/(prices.length-1))*W},${H-((p-mn)/rng)*H}`).join(' ');
  const up = prices[prices.length-1] >= prices[0];
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    <polyline points="${pts}" fill="none" stroke="${up?'#34c759':'#ff3b30'}"
      stroke-width="1.5" stroke-linejoin="round"/>
  </svg>`;
}
function rsiColor(r) {
  return r > 70 ? 'var(--r)' : r < 30 ? 'var(--g)' : 'var(--b)';
}

let _lastFilter = 'all';
function filterCards(f) {
  _lastFilter = f;
  document.querySelectorAll('.fb').forEach(b => b.classList.remove('active'));
  const map = {all:0,buy:1,sell:2};
  document.querySelectorAll('.fb')[map[f] ?? 0].classList.add('active');
  document.querySelectorAll('.ac').forEach(c => {
    const sig = c.dataset.signal || 'HOLD';
    const hide = f === 'buy' ? sig !== 'BUY' : f === 'sell' ? sig !== 'SELL' : false;
    c.classList.toggle('hidden', hide);
  });
}

async function loadAnalysis() {
  try {
    const d = await (await fetch('/api/analysis')).json();
    const cache = d.data || {};
    const keys = Object.keys(cache);
    if (!keys.length) {
      $('ag').innerHTML =
        '<div class="ac-loading">スキャン待機中... 「今すぐスキャン」を押してください</div>';
      return;
    }
    if (d.updated) {
      $('ag-updated').textContent =
        '更新: ' + new Date(d.updated).toLocaleTimeString('ja-JP');
    }
    $('ag').innerHTML = keys.map(ticker => {
      const r = cache[ticker];
      const sigCls   = r.signal === 'BUY' ? 'buy' : r.signal === 'SELL' ? 'sell' : '';
      const sigBadge = r.signal === 'BUY'
        ? '<span class="badge bb">🟢 BUY</span>'
        : r.signal === 'SELL'
        ? '<span class="badge bs">🔴 SELL</span>'
        : '<span class="badge bh">HOLD</span>';
      const chg = r.daily_change_pct ?? 0;
      const maTrend = r.ma_short > r.ma_long
        ? '<span style="color:var(--g)">↑ 上昇</span>'
        : '<span style="color:var(--r)">↓ 下降</span>';
      const priceStr = r.currency === 'JPY'
        ? '¥' + Math.round(r.price).toLocaleString()
        : '$' + r.price.toFixed(2);
      const ptsBadge = r.pts
        ? `<span class="badge bp">⏰PTS ${r.pts.pts_change_pct>=0?'+':''}${r.pts.pts_change_pct.toFixed(1)}%</span>`
        : '';
      const sentSpan = r.sentiment && r.sentiment.label !== 'N/A'
        ? `<span style="font-size:10px;color:${r.sentiment.color}">📰 ${r.sentiment.label}</span>`
        : '';
      // 銘柄名を大きく、ティッカーを常にサブ表示
      const dispName = r.name || ticker;
      const dispSub  = ticker;
      return `<div class="ac ${sigCls}" data-signal="${r.signal}"
          onclick="openChart('${ticker}','${(r.name||ticker).replace(/'/g,'\\x27')}')">
        <div class="ac-head">
          <div style="min-width:0;flex:1;margin-right:8px">
            <div class="ac-ticker" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${dispName}</div>
            <div class="ac-name">${dispSub}</div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div class="ac-price">${priceStr}</div>
            <div class="ac-chg ${pc(chg)}">${ps(chg,2)}</div>
          </div>
        </div>
        <div class="ac-spark">${sparkline(r.prices_20d)}</div>
        <div class="rsi-row">
          <span style="font-size:10px;color:var(--sub);min-width:22px">RSI</span>
          <div class="rsi-track">
            <div class="rsi-fill" style="width:${r.rsi}%;background:${rsiColor(r.rsi)}"></div>
          </div>
          <span class="rsi-val" style="color:${rsiColor(r.rsi)}">${r.rsi.toFixed(0)}</span>
        </div>
        <div class="ac-ma">MA ${maTrend} | ${r.reason.slice(0,16)}</div>
        <div class="ac-footer">
          <div style="display:flex;gap:4px;flex-wrap:wrap">${sigBadge}${ptsBadge}</div>
          ${sentSpan}
        </div>
      </div>`;
    }).join('');
    filterCards(_lastFilter);
  } catch(e) {
    $('ag').innerHTML = '<div class="ac-loading">データ取得失敗。再試行中...</div>';
  }
}

// ─── Tabs ───
const TABS = ['signals','wl','screener','agent'];
function showTab(name) {
  document.querySelectorAll('.tb').forEach((b,i) =>
    b.classList.toggle('active', TABS[i] === name));
  document.querySelectorAll('.tc').forEach(c => c.classList.remove('active'));
  $('tab-'+name).classList.add('active');
  curTab = name;
  loadTab(name);
}
function loadTab(n) {
  if (n==='signals')  loadSignals();
  else if (n==='wl')  loadWatchlist();
  else if (n==='screener') loadScreener();
  else if (n==='agent') loadAgentLog();
}

// ─── Signals ───
async function loadSignals() {
  try {
    const ss = await (await fetch('/api/signals')).json();
    const el = $('signals-body');
    if (!ss.length) { el.innerHTML='<div class="empty">シグナル履歴なし</div>'; return; }
    el.innerHTML = `<table><thead><tr>
      <th>日時</th><th>銘柄名</th><th>シグナル</th>
      <th>価格</th><th>RSI</th><th>理由</th>
    </tr></thead><tbody>${[...ss].reverse().slice(0,200).map(s => `<tr>
      <td class="ts">${(s.timestamp||'').replace('T',' ').slice(0,16)}</td>
      <td>
        <b style="cursor:pointer;color:var(--b)"
           onclick="openChart('${s.ticker}','${(s.name||s.ticker).replace(/'/g,'\\x27')}')">${s.name||s.ticker}</b>
        <div class="ts">${s.ticker}</div>
      </td>
      <td><span class="badge ${s.signal==='BUY'?'bb':s.signal==='SELL'?'bs':'bh'}">${
        s.signal==='BUY'?'🟢 買い':s.signal==='SELL'?'🔴 売り':'様子見'}</span></td>
      <td>${qf(s.price||0,s.currency||'USD')}</td>
      <td style="color:${rsiColor(s.rsi||50)}">${(s.rsi||0).toFixed(1)}</td>
      <td class="ts">${s.reason||'-'}</td>
    </tr>`).join('')}</tbody></table>`;
  } catch(e) {}
}

// ─── Watchlist ───
async function loadWatchlist() {
  try {
    const w = await (await fetch('/api/watchlist')).json();
    const rl = (list, mkt) => list.map(s => {
      const esc = v => v.replace(/'/g,'\\x27');
      return `<div class="si">
        <div style="flex:1;min-width:0">
          <b>${s.name||s.ticker}</b>
          <span style="color:var(--sub);font-size:11px;margin-left:8px">${s.ticker}</span>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          <button class="btn btn-outline btn-sm"
            onclick="editName('${esc(s.ticker)}','${mkt}','${esc(s.name||'')}')">✏️</button>
          <button class="btn btn-r btn-sm"
            onclick="rmStock('${esc(s.ticker)}','${mkt}')">削除</button>
        </div>
      </div>`;
    }).join('') || '<div class="si" style="color:var(--sub)">銘柄なし</div>';
    $('wl-body').innerHTML = `
      <div class="wls">
        <h3>🇯🇵 日本株 (${w.jp.length}件)</h3>
        <div style="background:var(--card);border:1px solid var(--bd);border-radius:8px">${rl(w.jp,'JP')}</div>
      </div>
      <div class="wls">
        <h3>🇺🇸 米国株 (${w.us.length}件)</h3>
        <div style="background:var(--card);border:1px solid var(--bd);border-radius:8px">${rl(w.us,'US')}</div>
      </div>`;
  } catch(e) {}
}

// ─── Agent Log ───
async function loadAgentLog() {
  try {
    const [logs, mkt, analysis] = await Promise.all([
      (await fetch('/api/agent/log')).json(),
      (await fetch('/api/market')).json(),
      (await fetch('/api/analysis')).json(),
    ]);
    const upd = analysis.updated
      ? new Date(analysis.updated).toLocaleTimeString('ja-JP')
      : '未実行';
    const mktUpd = mkt.updated
      ? new Date(mkt.updated).toLocaleTimeString('ja-JP')
      : '—';
    $('agent-status').innerHTML =
      `<span class="dot"></span> エージェント稼働中 &nbsp;|&nbsp; `+
      `最終分析スキャン: <b>${upd}</b> &nbsp;|&nbsp; `+
      `市場指数更新: <b>${mktUpd}</b> &nbsp;|&nbsp; `+
      `スキャン間隔: 10分`;
    if (!logs.length) {
      $('agent-log').innerHTML = '<div class="empty">ログなし</div>'; return;
    }
    $('agent-log').innerHTML = [...logs].reverse().slice(0,100).map(l => `
      <div class="alog-item">
        <div class="alog-time">${(l.time||'').replace('T',' ').slice(0,16)}</div>
        <div class="alog-msg">${l.msg}</div>
      </div>`).join('');
  } catch(e) {}
}

// ─── Chart Modal ───
async function openChart(ticker, name) {
  const dispName = name && name !== ticker ? name : ticker;
  $('modal-title').textContent = dispName;
  $('modal-sub').textContent   = ticker + ' | 60日チャート | MA / BB / MACD / RSI';
  $('modal-stats').innerHTML   = '<span class="spinner"></span>';
  $('modal-pts').innerHTML     = '';
  $('modal-news').style.display = 'none';
  $('overlay').classList.add('open');

  try {
    const [d, analysis] = await Promise.all([
      (await fetch('/api/chart/' + ticker)).json(),
      (await fetch('/api/analysis')).json(),
    ]);

    if (d.error) { $('modal-stats').textContent = d.error; return; }

    const ac    = (analysis.data || {})[ticker] || {};
    const last  = (d.close  || []).filter(Boolean).slice(-1)[0] || 0;
    const first = (d.close  || []).filter(Boolean)[0]  || 1;
    const rLast = (d.rsi    || []).filter(Boolean).slice(-1)[0] || 0;
    const mLast = (d.macd   || []).filter(Boolean).slice(-1)[0] || 0;
    const msLast= (d.macd_signal||[]).filter(Boolean).slice(-1)[0] || 0;
    const totalChg = ((last/first-1)*100);
    const isJpy = ticker.endsWith('.T');
    const fmt = v => isJpy ? '¥'+Math.round(v).toLocaleString() : '$'+v.toFixed(2);

    // Key stats
    const sigBadge = ac.signal === 'BUY'
      ? '<span class="badge bb">🟢 BUY</span>'
      : ac.signal === 'SELL'
      ? '<span class="badge bs">🔴 SELL</span>'
      : '<span class="badge bh">HOLD</span>';

    $('modal-stats').innerHTML = `
      <div class="kv"><div class="kl">現在値</div>
        <div class="kv2">${fmt(last)}</div></div>
      <div class="kv"><div class="kl">60日騰落率</div>
        <div class="kv2 ${totalChg>=0?'pos':'neg'}">${totalChg>=0?'+':''}${totalChg.toFixed(2)}%</div></div>
      <div class="kv"><div class="kl">RSI (14)</div>
        <div class="kv2" style="color:${rsiColor(rLast)}">${rLast.toFixed(1)}</div></div>
      <div class="kv"><div class="kl">MACD</div>
        <div class="kv2 ${mLast>=msLast?'pos':'neg'}">${mLast>=0?'+':''}${mLast.toFixed(3)}</div></div>
      <div class="kv"><div class="kl">シグナル</div>${sigBadge}</div>`;

    // PTS bar
    if (ac.pts) {
      const p = ac.pts;
      $('modal-pts').innerHTML = `
        <div class="pts-bar">
          <span class="pts-label">⏰ PTS (${p.pts_type === 'post' ? '時間後' : '時間前'})</span>
          <span>${fmt(p.pts_price)}</span>
          <span class="${p.pts_change_pct>=0?'pos':'neg'} " style="font-weight:700">
            ${p.pts_change_pct>=0?'+':''}${p.pts_change_pct.toFixed(2)}%</span>
          <span class="ts">通常: ${fmt(p.regular_price)}</span>
        </div>`;
    }

    // ── Price chart + BB ──
    if (priceChart) priceChart.destroy();
    priceChart = new Chart($('price-chart'), {
      type: 'line',
      data: {
        labels: d.dates,
        datasets: [
          { label: 'BB上限', data: d.bb_upper,
            borderColor:'rgba(175,82,222,.35)',borderWidth:1,pointRadius:0,tension:.1,
            fill:'+2',backgroundColor:'rgba(175,82,222,.04)' },
          { label: 'BB中', data: d.bb_mid,
            borderColor:'rgba(175,82,222,.5)',borderWidth:1,
            borderDash:[4,4],pointRadius:0,tension:.1 },
          { label: 'BB下限', data: d.bb_lower,
            borderColor:'rgba(175,82,222,.35)',borderWidth:1,pointRadius:0,tension:.1 },
          { label: '終値', data: d.close,
            borderColor:'#1d1d1f',borderWidth:2,pointRadius:0,tension:.1 },
          { label: 'MA5',  data: d.ma5,
            borderColor:'#ff9f0a',borderWidth:1.5,pointRadius:0,tension:.1 },
          { label: 'MA25', data: d.ma25,
            borderColor:'#ff3b30',borderWidth:1.5,pointRadius:0,tension:.1 },
        ]
      },
      options: {
        responsive:true, maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{font:{size:10},boxWidth:14}}},
        scales:{
          x:{ticks:{maxTicksLimit:8,font:{size:10}}},
          y:{ticks:{font:{size:10},callback:v=>fmt(v)}}
        }
      }
    });

    // ── MACD chart ──
    if (macdChart) macdChart.destroy();
    const histColors = (d.macd_hist||[]).map(v =>
      v == null ? 'transparent' : v >= 0 ? 'rgba(52,199,89,.6)' : 'rgba(255,59,48,.6)');
    macdChart = new Chart($('macd-chart'), {
      data: {
        labels: d.dates,
        datasets: [
          { type:'bar',   label:'ヒスト', data:d.macd_hist,
            backgroundColor:histColors,yAxisID:'y' },
          { type:'line',  label:'MACD',   data:d.macd,
            borderColor:'#007aff',borderWidth:1.5,pointRadius:0,tension:.2,yAxisID:'y' },
          { type:'line',  label:'Signal', data:d.macd_signal,
            borderColor:'#ff9f0a',borderWidth:1.5,pointRadius:0,tension:.2,yAxisID:'y' },
        ]
      },
      options: {
        responsive:true, maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{font:{size:10},boxWidth:12}}},
        scales:{
          x:{ticks:{maxTicksLimit:8,font:{size:10}}},
          y:{ticks:{font:{size:10}},grid:{color:'rgba(0,0,0,.05)'}}
        }
      }
    });

    // ── RSI chart ──
    if (rsiChart) rsiChart.destroy();
    rsiChart = new Chart($('rsi-chart'), {
      type:'line',
      data:{
        labels:d.dates,
        datasets:[{
          label:'RSI',data:d.rsi,
          borderColor:'#007aff',borderWidth:1.5,pointRadius:0,fill:false,tension:.2,
        }]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{legend:{display:false}},
        scales:{
          x:{ticks:{maxTicksLimit:8,font:{size:10}}},
          y:{min:0,max:100,
            ticks:{font:{size:10},callback:v=>[30,50,70].includes(v)?v:''},
            grid:{color:ctx =>
              ctx.tick.value===70?'rgba(255,59,48,.25)':
              ctx.tick.value===30?'rgba(52,199,89,.25)':'rgba(0,0,0,.04)'}}
        }
      }
    });

    // ── News / Sentiment (リアルタイム取得) ──
    $('modal-news').style.display = '';
    $('modal-news').innerHTML =
      '<div class="chart-label">📰 ニュース・感情分析</div>' +
      '<div class="ts" style="padding:8px 0"><span class="spinner"></span> 読み込み中...</div>';

    fetch('/api/sentiment/' + ticker)
      .then(r => r.json())
      .then(sent => {
        if (!sent || !sent.news || !sent.news.length) {
          $('modal-news').style.display = 'none'; return;
        }
        $('modal-news').innerHTML = buildSentimentHTML(sent);
      })
      .catch(() => { $('modal-news').style.display = 'none'; });

  } catch(e) {
    $('modal-stats').textContent = 'データ取得失敗: ' + e.message;
  }
}

function buildSentimentHTML(sent) {
  const color = sent.color || '#8e8e93';
  const label = sent.label || '—';
  const score = sent.score || 0;
  const pct   = Math.min(100, Math.max(0, (score + 2) / 4 * 100));
  return `
    <div class="chart-label" style="display:flex;align-items:center;gap:10px;margin-top:14px">
      📰 ニュース・感情分析
      <span style="color:${color};font-weight:700;font-size:12px">
        ${label} (${score>0?'+':''}${score.toFixed(2)})
      </span>
    </div>
    <div class="sent-panel">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--sub)">
        <span>弱気</span><span>中立</span><span>強気</span>
      </div>
      <div class="sent-score-bar">
        <div class="sent-score-fill" style="width:${pct}%;background:${color}"></div>
      </div>
      <div class="ts">ニュース ${sent.count||0}件を分析</div>
    </div>
    ${(sent.news||[]).map(n => `
      <div class="news-item">
        <div class="news-title">
          <a href="${n.link||'#'}" target="_blank" rel="noopener">${n.title||'—'}</a>
        </div>
        <div class="news-meta">
          ${n.publisher||''} &nbsp;·&nbsp; スコア:
          <span class="${n.score>0?'news-score-pos':n.score<0?'news-score-neg':''}">
            ${n.score>0?'+':''}${n.score}
          </span>
        </div>
      </div>`).join('')}`;
}
function closeOverlay() { $('overlay').classList.remove('open'); }
function closeModal(e)  { if (e.target === $('overlay')) closeOverlay(); }

// ─── Manual Scan ───
async function manualScan() {
  const btn = $('scan-btn');
  btn.innerHTML = '<span class="spinner"></span> スキャン中...';
  btn.disabled = true;
  try {
    const r = await (await fetch('/api/scan', {method:'POST'})).json();
    const buy  = (r.signals||[]).filter(s=>s.signal==='BUY').length;
    const sell = (r.signals||[]).filter(s=>s.signal==='SELL').length;
    alert(`スキャン完了: ${r.count}銘柄\n🟢 BUY: ${buy}件  🔴 SELL: ${sell}件`);
    refreshAll();
  } catch(e) {
    alert('スキャン失敗: ' + e.message);
  } finally {
    btn.innerHTML = '🔄 今すぐスキャン';
    btn.disabled  = false;
  }
}

// ─── Watchlist CRUD ───
async function addStock() {
  const ticker = $('tk').value.trim().toUpperCase();
  const name   = $('nm').value.trim();
  const market = $('mkt').value;
  if (!ticker) { alert('ティッカーを入力してください'); return; }
  const r = await (await fetch('/api/watchlist/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, name, market})
  })).json();
  if (r.ok) { $('tk').value=''; $('nm').value=''; loadWatchlist(); loadAnalysis(); }
  else alert(r.msg);
}
async function rmStock(ticker, market) {
  if (!confirm(ticker + ' を削除しますか？')) return;
  await fetch('/api/watchlist/remove',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, market})
  });
  loadWatchlist(); loadAnalysis();
}

async function editName(ticker, market, currentName) {
  const newName = prompt(ticker + ' の銘柄名:', currentName);
  if (newName === null) return;
  const r = await (await fetch('/api/watchlist/rename',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, name: newName.trim(), market})
  })).json();
  if (r.ok) { loadWatchlist(); loadAnalysis(); }
  else alert('更新失敗: ' + (r.msg||''));
}

// ─── Screener ───
let screenerData = null;
let scRegion = 'JP';
let scCategory = null;

async function loadScreener() {
  if (!screenerData) {
    const r = await (await fetch('/api/screener')).json();
    screenerData = r;
  }
  renderScCategories();
  renderScStocks();
}

function showRegion(region) {
  scRegion = region;
  scCategory = null;
  document.querySelectorAll('.sc-rb').forEach((b,i) =>
    b.classList.toggle('active', ['JP','US','OTHER'][i] === region));
  $('sc-search').value = '';
  renderScCategories();
  renderScStocks();
}

function renderScCategories() {
  if (!screenerData) return;
  const cats = Object.keys(screenerData[scRegion] || {});
  if (!scCategory || !cats.includes(scCategory)) scCategory = cats[0];
  $('sc-cats').innerHTML = cats.map(cat => {
    const n = ((screenerData[scRegion]||{})[cat]||[]).length;
    return `<button class="sc-cat ${cat===scCategory?'active':''}"
      onclick="showCategory('${cat.replace(/'/g,'\\x27')}')">${cat} <span style="opacity:.6">${n}</span></button>`;
  }).join('');
}

function showCategory(cat) {
  scCategory = cat;
  $('sc-search').value = '';
  document.querySelectorAll('.sc-cat').forEach(b => {
    b.classList.toggle('active', b.textContent.trim().startsWith(cat));
  });
  renderScStocks();
}

async function renderScStocks(stocks) {
  if (!screenerData) return;
  const q = ($('sc-search').value || '').toLowerCase().trim();
  let list = stocks;
  if (!list) {
    if (q) {
      // 全カテゴリ横断検索
      const seen = new Set();
      list = [];
      for (const [reg, cats] of Object.entries(screenerData)) {
        for (const [cat, arr] of Object.entries(cats)) {
          for (const s of arr) {
            if (!seen.has(s.ticker) &&
                (s.name.toLowerCase().includes(q) || s.ticker.toLowerCase().includes(q))) {
              seen.add(s.ticker);
              list.push({...s, _reg: reg, _cat: cat});
            }
          }
        }
      }
    } else {
      list = (screenerData[scRegion]||{})[scCategory] || [];
    }
  }
  const wl = await (await fetch('/api/watchlist')).json();
  const wlSet = new Set([...wl.jp.map(s=>s.ticker), ...wl.us.map(s=>s.ticker)]);
  const label = q ? `検索結果: ${list.length}件` :
    `${scCategory} (${list.length}件)`;
  $('sc-list').innerHTML = `
    <div style="font-size:12px;color:var(--sub);margin-bottom:8px">${label}</div>
    <div class="sc-list-grid" style="background:var(--card);border-radius:8px;border:1px solid var(--bd)">
      ${list.map(s => {
        const inWL = wlSet.has(s.ticker);
        const mkt  = s.ticker.endsWith('.T') ? 'JP' : 'US';
        const esc  = v => v.replace(/'/g,'\\x27');
        const catBadge = s._cat
          ? `<span class="ts" style="margin-left:8px">${s._cat}</span>` : '';
        return `<div class="sc-row">
          <div class="sc-info" onclick="openChart('${esc(s.ticker)}','${esc(s.name)}')">
            <div class="sc-name">${s.name}${catBadge}</div>
            <div class="sc-ticker">${s.ticker}</div>
          </div>
          ${inWL
            ? '<span class="badge bb" style="min-width:64px;text-align:center">追加済み</span>'
            : `<button class="btn btn-b btn-sm"
                 onclick="addFromScreener('${esc(s.ticker)}','${esc(s.name)}','${mkt}')">+ 追加</button>`
          }
        </div>`;
      }).join('') || '<div class="empty">該当なし</div>'}
    </div>`;
}

async function filterScreener() {
  await renderScStocks();
}

async function addFromScreener(ticker, name, market) {
  const r = await (await fetch('/api/watchlist/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, name, market})
  })).json();
  if (r.ok) { renderScStocks(); loadAnalysis(); }
  else alert('追加失敗: ' + (r.msg||''));
}

// ─── GitHub更新 ───
async function gitPull() {
  if (!confirm('GitHubから最新コードを取得してbotを再起動します。よろしいですか？')) return;
  const btn = $('pull-btn');
  btn.innerHTML = '<span class="spinner"></span> 更新中...';
  btn.disabled = true;
  try {
    const r = await (await fetch('/api/git/pull', {method:'POST'})).json();
    if (r.ok) {
      alert('✅ ' + r.msg + '\nページを再読み込みします。');
      setTimeout(() => location.reload(), 2000);
    } else {
      alert('❌ エラー:\n' + r.msg);
    }
  } catch(e) {
    alert('通信エラー: ' + e.message);
  } finally {
    btn.innerHTML = '⬇️ アップデート';
    btn.disabled = false;
  }
}

// ─── Init ───
loadMarket(); loadStats(); loadAnalysis(); loadSignals();
startAuto();
</script>
</body>
</html>"""


def create_app(trader, watchlist_manager, notifier_mod=None, agent=None) -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)

    @app.route("/")
    def index():
        return _HTML

    @app.route("/api/stats")
    def api_stats():
        """分析統計（売買なし版）"""
        try:
            if ANALYSIS_CACHE_FILE.exists():
                d = json.loads(ANALYSIS_CACHE_FILE.read_text(encoding="utf-8"))
                cache = d.get("data", {})
                return jsonify({
                    "scan_count": len(cache),
                    "buy_count":  sum(1 for r in cache.values() if r.get("signal") == "BUY"),
                    "sell_count": sum(1 for r in cache.values() if r.get("signal") == "SELL"),
                    "hold_count": sum(1 for r in cache.values() if r.get("signal") == "HOLD"),
                    "pts_count":  sum(1 for r in cache.values() if r.get("pts")),
                    "last_scan":  d.get("updated"),
                })
        except Exception:
            pass
        return jsonify({
            "scan_count": 0, "buy_count": 0, "sell_count": 0,
            "hold_count": 0, "pts_count": 0, "last_scan": None,
        })

    @app.route("/api/market")
    def api_market():
        if MARKET_CACHE_FILE.exists():
            return MARKET_CACHE_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify({"data": {}, "updated": None})

    @app.route("/api/analysis")
    def api_analysis():
        if ANALYSIS_CACHE_FILE.exists():
            return ANALYSIS_CACHE_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify({"data": {}, "updated": None})

    @app.route("/api/signals")
    def api_signals():
        if SIGNALS_FILE.exists():
            return SIGNALS_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify([])

    @app.route("/api/pts")
    def api_pts():
        if PTS_CACHE_FILE.exists():
            return PTS_CACHE_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify({"data": {}, "updated": None})

    @app.route("/api/sentiment")
    def api_sentiment():
        if SENTIMENT_CACHE_FILE.exists():
            return SENTIMENT_CACHE_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify({"data": {}, "updated": None})

    @app.route("/api/chart/<ticker>")
    def api_chart(ticker):
        ticker = ticker.upper()
        now = time.time()
        if ticker in _chart_cache and _chart_cache[ticker]["exp"] > now:
            return jsonify(_chart_cache[ticker]["data"])
        data = get_chart_data(ticker)
        if data:
            _chart_cache[ticker] = {"data": data, "exp": now + 300}
            return jsonify(data)
        return jsonify({"error": "データ取得失敗"}), 404

    @app.route("/api/agent/log")
    def api_agent_log():
        if AGENT_LOG_FILE.exists():
            return AGENT_LOG_FILE.read_text(encoding="utf-8"), 200, \
                {"Content-Type": "application/json"}
        return jsonify([])

    @app.route("/api/watchlist")
    def api_watchlist():
        return jsonify({"jp": watchlist_manager.get_jp(), "us": watchlist_manager.get_us()})

    @app.route("/api/watchlist/add", methods=["POST"])
    def api_watchlist_add():
        data   = request.get_json() or {}
        ticker = (data.get("ticker") or "").strip().upper()
        name   = (data.get("name") or "").strip()
        market = (data.get("market") or "US").strip().upper()
        if not ticker:
            return jsonify({"ok": False, "msg": "ティッカーを入力してください"})
        watchlist_manager.add(ticker, name, market)
        return jsonify({"ok": True})

    @app.route("/api/watchlist/remove", methods=["POST"])
    def api_watchlist_remove():
        data   = request.get_json() or {}
        ticker = (data.get("ticker") or "").strip().upper()
        market = (data.get("market") or "US").strip().upper()
        watchlist_manager.remove(ticker, market)
        return jsonify({"ok": True})

    @app.route("/api/watchlist/rename", methods=["POST"])
    def api_watchlist_rename():
        data   = request.get_json() or {}
        ticker = (data.get("ticker") or "").strip().upper()
        name   = (data.get("name") or "").strip()
        market = (data.get("market") or "US").strip().upper()
        if not ticker:
            return jsonify({"ok": False, "msg": "ティッカーを入力してください"})
        watchlist_manager.rename(ticker, name, market)
        return jsonify({"ok": True})

    @app.route("/api/screener")
    def api_screener():
        from screener_data import SCREENER
        return jsonify(SCREENER)

    @app.route("/api/sentiment/<ticker>")
    def api_sentiment_ticker(ticker):
        """リアルタイム感情分析（モーダル用）"""
        from sentiment import get_sentiment
        ticker = ticker.upper()
        return jsonify(get_sentiment(ticker))

    @app.route("/api/git/pull", methods=["POST"])
    def api_git_pull():
        """GitHub から git pull して bot を再起動"""
        import subprocess, os, threading
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True, text=True, timeout=30,
                cwd=bot_dir,
            )
            if result.returncode != 0:
                return jsonify({"ok": False, "msg": result.stderr.strip() or "git pull 失敗"})
            msg = result.stdout.strip() or "Already up to date."

            def _restart():
                import time, sys, signal
                time.sleep(1)
                # nohup で自分自身を再起動してから終了
                subprocess.Popen(
                    ["nohup", "python", "main.py"],
                    cwd=bot_dir,
                    stdout=open(os.path.join(bot_dir, "kabutobot.log"), "a"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                time.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)

            threading.Thread(target=_restart, daemon=True).start()
            return jsonify({"ok": True, "msg": msg})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
        """手動スキャン（シグナル記録・通知のみ。売買は人間が行う）"""
        results = []
        for stock in watchlist_manager.get_jp() + watchlist_manager.get_us():
            try:
                result = analyze(stock["ticker"])
                if result is None:
                    continue
                result["name"] = stock.get("name", stock["ticker"])
                log_signal(result)
                results.append(result)
                if notifier_mod:
                    if result["signal"] == "BUY":
                        try:
                            notifier_mod.notify_buy_signal(result)
                        except Exception:
                            pass
                    elif result["signal"] == "SELL":
                        try:
                            notifier_mod.notify_sell_signal(result)
                        except Exception:
                            pass
            except Exception as e:
                log.warning(f"[Dashboard] {stock['ticker']}: {e}")

        if agent:
            import threading
            threading.Thread(target=agent.cycle, daemon=True).start()

        return jsonify({"ok": True, "count": len(results), "signals": results})

    @app.route("/api/log/view")
    def api_log_view():
        """ログファイル閲覧（WebFetch直接参照用）"""
        import pathlib
        log_path = pathlib.Path("kabutobot.log")
        if not log_path.exists():
            return "ログファイルなし", 404
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-300:]), 200, {"Content-Type": "text/plain; charset=utf-8"}
        except Exception as e:
            return f"読み込みエラー: {e}", 500

    return app
