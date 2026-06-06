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
  box-shadow:var(--sh);border-top:3px solid transparent;
  cursor:pointer;transition:.15s}
.scard:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.1)}
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
.filter-btns{display:flex;gap:6px;margin-left:auto;flex-wrap:wrap}
.fb{padding:5px 12px;border:1px solid var(--bd);border-radius:20px;
  background:#fff;cursor:pointer;font-size:12px;font-weight:500;
  color:var(--sub);transition:.15s}
.fb:hover{border-color:var(--b);color:var(--b)}
.fb.active{background:var(--b);border-color:var(--b);color:#fff}
.fb.buy.active{background:var(--g);border-color:var(--g);color:#fff}
.fb.sell.active{background:var(--r);border-color:var(--r);color:#fff}
.fb.pts.active{background:var(--y);border-color:var(--y);color:#fff}

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
.tnav{display:flex;border-bottom:1px solid var(--bd);overflow-x:auto}
.tb{padding:13px 16px;border:none;background:none;cursor:pointer;
  font-size:13px;font-weight:500;color:var(--sub);white-space:nowrap;
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:.15s;flex-shrink:0}
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

/* ── Sentiment Panel ── */
.sent-panel{background:#f5f5f7;border-radius:8px;padding:12px 14px;margin-bottom:12px}
.sent-score-bar{height:6px;border-radius:3px;background:#ddd;margin:6px 0;overflow:hidden}
.sent-score-fill{height:100%;border-radius:3px;transition:.4s}

/* ── Portfolio ── */
.pf-summary{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.pf-kv{background:#f5f5f7;border-radius:8px;padding:12px 16px;min-width:130px;text-align:center}
.pf-kv .pk{font-size:10px;color:var(--sub);text-transform:uppercase;
  margin-bottom:4px;font-weight:600;letter-spacing:.3px}
.pf-kv .pv{font-size:20px;font-weight:700}
.pf-add{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:flex-end}
.pf-add>div{display:flex;flex-direction:column;gap:3px}
.pf-add label{font-size:11px;color:var(--sub);font-weight:500}
.pf-add input,.pf-add select{padding:7px 10px;border:1px solid var(--bd);
  border-radius:8px;font-size:13px;outline:none}
.pf-add input:focus,.pf-add select:focus{border-color:var(--b)}

/* ── Alerts ── */
.al-add{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:flex-end}
.al-add>div{display:flex;flex-direction:column;gap:3px}
.al-add label{font-size:11px;color:var(--sub);font-weight:500}
.al-add input,.al-add select{padding:7px 10px;border:1px solid var(--bd);
  border-radius:8px;font-size:13px;outline:none}
.al-add input:focus,.al-add select:focus{border-color:var(--b)}
.al-triggered td{opacity:.55}

/* ── Settings ── */
.sg{margin-bottom:24px}
.sg h4{font-size:13px;font-weight:600;margin-bottom:12px;
  padding-bottom:6px;border-bottom:1px solid var(--bd)}
.sr{display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.sr label{font-size:13px;min-width:190px;color:var(--tx);font-weight:500}
.sr input[type=text],.sr input[type=number],.sr input[type=url]{
  padding:7px 12px;border:1px solid var(--bd);border-radius:8px;
  font-size:13px;outline:none;min-width:200px;max-width:420px;flex:1}
.sr input:focus{border-color:var(--b)}
.sr-note{font-size:11px;color:var(--sub);margin:-4px 0 8px 202px;line-height:1.5}

/* ── Backtest ── */
.bt-summary{display:flex;gap:10px;margin:10px 0 14px;flex-wrap:wrap}
.bt-kv{background:#f5f5f7;border-radius:8px;padding:10px 14px;
  min-width:100px;text-align:center}
.bt-kv .bk{font-size:10px;color:var(--sub);text-transform:uppercase;
  margin-bottom:3px;font-weight:600;letter-spacing:.3px}
.bt-kv .bv{font-size:18px;font-weight:700}
.bt-divider{border:none;border-top:1px solid var(--bd);margin:16px 0}

/* ── Modal Inner Tabs ── */
.mtabs{display:flex;gap:0;border-bottom:1px solid var(--bd);margin:0 -24px 16px;padding:0 24px;overflow-x:auto}
.mtb{padding:9px 14px;border:none;background:none;cursor:pointer;
  font-size:12px;font-weight:500;color:var(--sub);white-space:nowrap;
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:.15s;flex-shrink:0}
.mtb.active{color:var(--b);border-bottom-color:var(--b)}
.mtc{display:none}.mtc.active{display:block}

/* ── Fundamentals ── */
.fund-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px;margin-bottom:14px}
.fund-kv{background:#f5f5f7;border-radius:8px;padding:10px 14px}
.fund-kv .fk{font-size:10px;color:var(--sub);text-transform:uppercase;letter-spacing:.3px;margin-bottom:3px;font-weight:600}
.fund-kv .fv{font-size:16px;font-weight:700;line-height:1.2}
.fund-kv .fn{font-size:10px;color:var(--sub);margin-top:2px}
.fund-section{margin-bottom:16px}
.fund-section h4{font-size:11px;font-weight:700;color:var(--sub);text-transform:uppercase;
  letter-spacing:.4px;margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--bd)}

/* ── Valuation ── */
.val-box{background:linear-gradient(135deg,#f0f8ff,#e8f5e9);
  border-radius:10px;padding:14px 16px;margin-bottom:14px;border:1px solid rgba(0,120,255,.15)}
.val-box .vb-label{font-size:10px;color:var(--sub);text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px;font-weight:600}
.val-box .vb-price{font-size:24px;font-weight:700;margin-bottom:2px}
.val-box .vb-note{font-size:10px;color:var(--sub);line-height:1.5;margin-top:4px}

/* ── Fund Screener ── */
.fsc-row{display:flex;align-items:center;padding:10px 14px;border-bottom:1px solid var(--bd);gap:10px;flex-wrap:wrap}
.fsc-row:last-child{border-bottom:none}
.fsc-row:hover{background:#fafafa}
.fsc-info{flex:1;min-width:100px;cursor:pointer}
.fsc-info:hover .fsc-name{color:var(--b)}
.fsc-name{font-size:13px;font-weight:600}
.fsc-ticker{font-size:11px;color:var(--sub)}
.fsc-metrics{display:flex;gap:10px;flex-wrap:wrap}
.fsc-m{font-size:11px;color:var(--sub);white-space:nowrap}
.fsc-m b{color:var(--tx)}

/* ── Search Suggestions ── */
.sc-search-wrap{position:relative}
.sc-suggest{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#fff;
  border:1px solid var(--bd);border-radius:10px;
  box-shadow:0 8px 24px rgba(0,0,0,.13);z-index:300;
  max-height:340px;overflow-y:auto;display:none}
.sc-suggest.open{display:block}
.sc-sug-hd{padding:6px 14px 4px;font-size:10px;font-weight:700;color:var(--sub);
  text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--bd);
  background:#fafafa;border-radius:10px 10px 0 0}
.sc-sug-item{display:flex;align-items:center;gap:10px;padding:9px 14px;
  cursor:pointer;border-bottom:1px solid var(--bd)}
.sc-sug-item:last-child{border-bottom:none}
.sc-sug-item:hover,.sc-sug-item.hi{background:#f0f4ff}
.sc-sug-ticker{font-size:13px;font-weight:700;min-width:58px}
.sc-sug-name{font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sc-sug-cat{font-size:10px;color:var(--sub);white-space:nowrap;
  background:#f5f5f7;padding:2px 7px;border-radius:4px;flex-shrink:0}
.hl{color:var(--b);font-weight:700}

/* ── Responsive ── */
@media(max-width:600px){
  .wlg{grid-template-columns:1fr}
  .h-actions{gap:6px}
  header .sub{display:none}
  .sr-note{margin-left:0}
  .fund-grid{grid-template-columns:1fr 1fr}
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
  <!-- Stats Cards（クリックで銘柄フィルター） -->
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
      <button class="fb buy"    onclick="filterCards('buy')">🟢 BUY</button>
      <button class="fb sell"   onclick="filterCards('sell')">🔴 SELL</button>
      <button class="fb pts"    onclick="filterCards('pts')">⏰ PTS</button>
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
      <button class="tb" onclick="showTab('portfolio')">💼 ポートフォリオ</button>
      <button class="tb" onclick="showTab('alerts')">🔔 アラート</button>
      <button class="tb" onclick="showTab('agent')">🤖 エージェント</button>
      <button class="tb" onclick="showTab('settings')">⚙️ 設定</button>
    </div>

    <!-- シグナル履歴 -->
    <div id="tab-signals" class="tc active"><div id="signals-body"></div></div>

    <!-- 監視銘柄 -->
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

    <!-- スクリーナー -->
    <div id="tab-screener" class="tc">
      <!-- ファンダメンタルスクリーナー (監視銘柄) -->
      <div style="margin-bottom:18px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
          <span style="font-size:14px;font-weight:600">📊 ファンダメンタル スクリーナー</span>
          <span class="ts">監視銘柄のみ</span>
          <div style="margin-left:auto;display:flex;gap:5px;flex-wrap:wrap" id="fs-filters">
            <button class="fb active" data-ftype="sig" data-fval="all"  onclick="fscFilter('all','sig')">全シグナル</button>
            <button class="fb buy"    data-ftype="sig" data-fval="buy"  onclick="fscFilter('buy','sig')">🟢 BUY</button>
            <button class="fb sell"   data-ftype="sig" data-fval="sell" onclick="fscFilter('sell','sig')">🔴 SELL</button>
            <button class="fb"        data-ftype="cross" data-fval="golden" onclick="fscFilter('golden','cross')">✨ ゴールデン</button>
            <button class="fb"        data-ftype="cross" data-fval="dead"   onclick="fscFilter('dead','cross')">💀 デッド</button>
          </div>
        </div>
        <div id="fsc-body" style="background:var(--card);border-radius:8px;border:1px solid var(--bd)">
          <div class="empty"><span class="spinner"></span> 読み込み中...</div>
        </div>
      </div>
      <hr style="border:none;border-top:1px solid var(--bd);margin:0 0 16px">
      <!-- 銘柄スクリーナー (全銘柄リスト) -->
      <div style="margin-bottom:14px">
        <div class="sc-search-wrap">
          <input id="sc-search" type="text" autocomplete="off"
            placeholder="🔍 検索: ティッカー(AAPL / 7203) · 日本語名(トヨタ) · 英語名(toyota / apple)"
            oninput="onScSearch(event)" onkeydown="onScSearchKey(event)"
            onfocus="onScSearchFocus()" onblur="onScSearchBlur()"
            style="width:100%;padding:9px 14px;border:1px solid var(--bd);
                   border-radius:8px;font-size:13px;outline:none">
          <div id="sc-suggest" class="sc-suggest"></div>
        </div>
      </div>
      <div class="sc-region">
        <button class="sc-rb active" onclick="showRegion('JP')">🇯🇵 日本株</button>
        <button class="sc-rb" onclick="showRegion('US')">🇺🇸 米国株</button>
        <button class="sc-rb" onclick="showRegion('OTHER')">🌐 その他</button>
      </div>
      <div class="sc-cats" id="sc-cats"></div>
      <div id="sc-list"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>

    <!-- ポートフォリオ -->
    <div id="tab-portfolio" class="tc">
      <div class="pf-add">
        <div><label>ティッカー</label><input id="pf-tk" placeholder="7203.T / AAPL" style="width:140px"></div>
        <div><label>銘柄名</label><input id="pf-nm" placeholder="トヨタ自動車" style="width:130px"></div>
        <div><label>数量</label><input id="pf-qty" type="number" placeholder="100" style="width:90px;min-width:0"></div>
        <div><label>取得価格</label><input id="pf-price" type="number" placeholder="2500" style="width:120px;min-width:0"></div>
        <div><label>通貨</label>
          <select id="pf-cur">
            <option value="JPY">JPY (円)</option>
            <option value="USD">USD ($)</option>
          </select>
        </div>
        <button class="btn btn-b" onclick="addPortfolio()" style="align-self:flex-end">+ 追加</button>
      </div>
      <div class="pf-summary" id="pf-summary"></div>
      <div id="pf-body"></div>
    </div>

    <!-- 価格アラート -->
    <div id="tab-alerts" class="tc">
      <div class="al-add">
        <div><label>ティッカー</label><input id="al-tk" placeholder="7203.T / AAPL" style="width:140px"></div>
        <div><label>銘柄名</label><input id="al-nm" placeholder="トヨタ自動車" style="width:130px"></div>
        <div><label>目標価格</label><input id="al-price" type="number" placeholder="3000" style="width:120px;min-width:0"></div>
        <div><label>条件</label>
          <select id="al-dir">
            <option value="above">📈 上抜け（以上で通知）</option>
            <option value="below">📉 下抜け（以下で通知）</option>
          </select>
        </div>
        <div><label>通貨</label>
          <select id="al-cur">
            <option value="JPY">JPY (円)</option>
            <option value="USD">USD ($)</option>
          </select>
        </div>
        <button class="btn btn-b" onclick="addAlert()" style="align-self:flex-end">+ 追加</button>
      </div>
      <div style="font-size:12px;color:var(--sub);margin:-8px 0 14px">
        ⚠️ エージェントサイクル(10分ごと)にチェックします。Discord通知は設定タブで設定してください。
      </div>
      <div id="al-body"></div>
    </div>

    <!-- エージェント -->
    <div id="tab-agent" class="tc">
      <div class="alog-status" id="agent-status">読み込み中...</div>
      <div class="alog" id="agent-log"></div>
    </div>

    <!-- 設定 -->
    <div id="tab-settings" class="tc">
      <div id="settings-form"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>
  </div>
</div>

<!-- Stock Detail Modal -->
<div class="overlay" id="overlay" onclick="closeModal(event)">
  <div class="modal">
    <div class="modal-head">
      <div>
        <h2 id="modal-title"></h2>
        <div class="ts" id="modal-sub"></div>
      </div>
      <button class="close-btn" onclick="closeOverlay()">✕</button>
    </div>
    <div class="mtabs">
      <button class="mtb active" onclick="openModalTab('chart')">📈 チャート</button>
      <button class="mtb" onclick="openModalTab('fund')">📋 基本情報</button>
      <button class="mtb" onclick="openModalTab('news')">📰 ニュース</button>
      <button class="mtb" onclick="openModalTab('val')">💰 評価・分析</button>
      <button class="mtb" onclick="openModalTab('bt')">🧪 バックテスト</button>
    </div>
    <!-- Tab: チャート -->
    <div class="mtc active" id="mtc-chart">
      <div class="modal-kv" id="modal-stats"><span class="spinner"></span></div>
      <div id="modal-pts"></div>
      <div class="chart-label">価格 + 移動平均 + ボリンジャーバンド</div>
      <div class="chart-wrap"><canvas id="price-chart"></canvas></div>
      <div class="chart-label">MACD (12, 26, 9)</div>
      <div class="chart-wrap-md"><canvas id="macd-chart"></canvas></div>
      <div class="chart-label">RSI (14日)</div>
      <div class="chart-wrap-sm"><canvas id="rsi-chart"></canvas></div>
    </div>
    <!-- Tab: 基本情報 -->
    <div class="mtc" id="mtc-fund">
      <div id="modal-fund-body"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>
    <!-- Tab: ニュース -->
    <div class="mtc" id="mtc-news">
      <div id="modal-news-body"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>
    <!-- Tab: 評価・分析 -->
    <div class="mtc" id="mtc-val">
      <div id="modal-val-body"><div class="empty"><span class="spinner"></span> 読み込み中...</div></div>
    </div>
    <!-- Tab: バックテスト -->
    <div class="mtc" id="mtc-bt">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <span style="font-size:13px;font-weight:600">📊 バックテスト (過去1年 / RSI+MAクロス戦略)</span>
        <button class="btn btn-outline btn-sm" id="bt-btn" onclick="runBacktest()">実行</button>
      </div>
      <div id="modal-backtest">
        <div class="ts">「実行」ボタンで過去1年のシミュレーション結果を表示します</div>
      </div>
    </div>
  </div>
</div>

<script>
let curTab    = 'signals';
let autoFlag  = true;
let autoTimer = null;
let priceChart = null, rsiChart = null, macdChart = null;
let _btTicker  = null;
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

// ─── Stats（クリックでフィルター） ───
async function loadStats() {
  try {
    const s = await (await fetch('/api/stats')).json();
    const lastScan = s.last_scan
      ? new Date(s.last_scan).toLocaleTimeString('ja-JP')
      : '未実行';
    $('stats').innerHTML = `
      <div class="scard total" onclick="filterAndScroll('all')">
        <div class="sl">スキャン銘柄</div>
        <div class="sv">${s.scan_count || 0}</div>
        <div class="sc">→ 全銘柄を表示</div>
      </div>
      <div class="scard buy" onclick="filterAndScroll('buy')">
        <div class="sl">BUYシグナル</div>
        <div class="sv pos">${s.buy_count || 0}</div>
        <div class="sc pos">→ BUY銘柄を表示</div>
      </div>
      <div class="scard sell" onclick="filterAndScroll('sell')">
        <div class="sl">SELLシグナル</div>
        <div class="sv neg">${s.sell_count || 0}</div>
        <div class="sc neg">→ SELL銘柄を表示</div>
      </div>
      <div class="scard pts" onclick="filterAndScroll('pts')">
        <div class="sl">PTS更新</div>
        <div class="sv" style="color:var(--y)">${s.pts_count || 0}</div>
        <div class="sc">→ PTS銘柄を表示</div>
      </div>`;
    $('ts').textContent = '最終スキャン: ' + lastScan;
  } catch(e) {}
}

function filterAndScroll(f) {
  filterCards(f);
  const el = $('ag');
  if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
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
  const fbArr = document.querySelectorAll('.fb');
  const map = {all:0, buy:1, sell:2, pts:3};
  const idx = map[f] ?? 0;
  if (fbArr[idx]) fbArr[idx].classList.add('active');
  document.querySelectorAll('.ac').forEach(c => {
    const sig    = c.dataset.signal || 'HOLD';
    const hasPts = c.dataset.pts === '1';
    const hide   = f === 'buy'  ? sig !== 'BUY'  :
                   f === 'sell' ? sig !== 'SELL' :
                   f === 'pts'  ? !hasPts : false;
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
      const dispName = r.name || ticker;
      return `<div class="ac ${sigCls}" data-signal="${r.signal}" data-pts="${r.pts?'1':''}"
          onclick="openChart('${ticker}','${(r.name||ticker).replace(/'/g,'\\x27')}')">
        <div class="ac-head">
          <div style="min-width:0;flex:1;margin-right:8px">
            <div class="ac-ticker" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${dispName}</div>
            <div class="ac-name">${ticker}</div>
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
        <div class="ac-ma">MA ${maTrend} | ${r.reason.slice(0,18)}</div>
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
const TABS = ['signals','wl','screener','portfolio','alerts','agent','settings'];
function showTab(name) {
  document.querySelectorAll('.tb').forEach((b,i) =>
    b.classList.toggle('active', TABS[i] === name));
  document.querySelectorAll('.tc').forEach(c => c.classList.remove('active'));
  $('tab-'+name).classList.add('active');
  curTab = name;
  loadTab(name);
}
function loadTab(n) {
  if (n==='signals')   loadSignals();
  else if (n==='wl')   loadWatchlist();
  else if (n==='screener')  { loadScreener(); loadFundScreener(); }
  else if (n==='portfolio') loadPortfolio();
  else if (n==='alerts')    loadAlerts();
  else if (n==='agent')     loadAgentLog();
  else if (n==='settings')  loadSettings();
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
          <b style="cursor:pointer;color:var(--b)" onclick="openChart('${esc(s.ticker)}','${esc(s.name||s.ticker)}')">${s.name||s.ticker}</b>
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
    const upd    = analysis.updated ? new Date(analysis.updated).toLocaleTimeString('ja-JP') : '未実行';
    const mktUpd = mkt.updated ? new Date(mkt.updated).toLocaleTimeString('ja-JP') : '—';
    $('agent-status').innerHTML =
      `<span class="dot"></span> エージェント稼働中 &nbsp;|&nbsp; `+
      `最終分析スキャン: <b>${upd}</b> &nbsp;|&nbsp; `+
      `市場指数更新: <b>${mktUpd}</b> &nbsp;|&nbsp; スキャン間隔: 10分`;
    if (!logs.length) { $('agent-log').innerHTML = '<div class="empty">ログなし</div>'; return; }
    $('agent-log').innerHTML = [...logs].reverse().slice(0,100).map(l => `
      <div class="alog-item">
        <div class="alog-time">${(l.time||'').replace('T',' ').slice(0,16)}</div>
        <div class="alog-msg">${l.msg}</div>
      </div>`).join('');
  } catch(e) {}
}

// ─── Portfolio ───
async function loadPortfolio() {
  try {
    const [pf, analysis] = await Promise.all([
      (await fetch('/api/portfolio')).json(),
      (await fetch('/api/analysis')).json(),
    ]);
    const prices = analysis.data || {};
    let totalInvested = {JPY:0, USD:0}, totalCurrent = {JPY:0, USD:0};
    let hasPrice = {JPY:false, USD:false};

    const rows = pf.map((h, i) => {
      const ac       = prices[h.ticker];
      const currP    = ac ? ac.price : null;
      const invested = h.buy_price * h.qty;
      const current  = currP !== null ? currP * h.qty : null;
      const pnl      = current !== null ? current - invested : null;
      const pnlPct   = pnl !== null ? (pnl / invested * 100) : null;
      const cur      = h.currency;
      totalInvested[cur] = (totalInvested[cur]||0) + invested;
      if (current !== null) { totalCurrent[cur] = (totalCurrent[cur]||0) + current; hasPrice[cur] = true; }
      const fmt = v => cur === 'JPY' ? '¥' + Math.round(v).toLocaleString() : '$' + v.toFixed(2);
      const esc = v => (v||'').replace(/'/g,'\\x27');
      return `<tr>
        <td>
          <b style="cursor:pointer;color:var(--b)" onclick="openChart('${esc(h.ticker)}','${esc(h.name||h.ticker)}')">${h.name||h.ticker}</b>
          <div class="ts">${h.ticker}</div>
        </td>
        <td>${h.qty.toLocaleString()}</td>
        <td>${fmt(h.buy_price)}</td>
        <td>${currP !== null ? fmt(currP) : '<span class="ts">—</span>'}</td>
        <td>${pnl !== null ? `<span class="${pc(pnl)}">${pnl>=0?'+':''}${fmt(pnl)}</span>` : '<span class="ts">—</span>'}</td>
        <td>${pnlPct !== null ? `<span class="${pc(pnlPct)}">${pnlPct>=0?'+':''}${pnlPct.toFixed(2)}%</span>` : '<span class="ts">—</span>'}</td>
        <td class="ts">${h.date||''}</td>
        <td><button class="btn btn-r btn-sm" onclick="removePortfolio(${i})">削除</button></td>
      </tr>`;
    }).join('');

    const jPnl = hasPrice.JPY ? totalCurrent.JPY - totalInvested.JPY : null;
    const uPnl = hasPrice.USD ? totalCurrent.USD - totalInvested.USD : null;
    const jPct = jPnl !== null && totalInvested.JPY > 0 ? jPnl/totalInvested.JPY*100 : null;

    $('pf-summary').innerHTML = `
      <div class="pf-kv"><div class="pk">保有銘柄数</div><div class="pv">${pf.length}</div></div>
      <div class="pf-kv">
        <div class="pk">投資額 (JPY)</div>
        <div class="pv">¥${Math.round(totalInvested.JPY||0).toLocaleString()}</div>
      </div>
      ${jPnl !== null ? `<div class="pf-kv">
        <div class="pk">評価損益 (JPY)</div>
        <div class="pv ${pc(jPnl)}">${jPnl>=0?'+':''}¥${Math.round(Math.abs(jPnl)).toLocaleString()}</div>
      </div>` : ''}
      ${jPct !== null ? `<div class="pf-kv">
        <div class="pk">損益率 (JPY)</div>
        <div class="pv ${pc(jPct)}">${jPct>=0?'+':''}${jPct.toFixed(2)}%</div>
      </div>` : ''}
      ${totalInvested.USD > 0 ? `<div class="pf-kv">
        <div class="pk">投資額 (USD)</div>
        <div class="pv">$${totalInvested.USD.toFixed(2)}</div>
      </div>` : ''}
      ${uPnl !== null ? `<div class="pf-kv">
        <div class="pk">評価損益 (USD)</div>
        <div class="pv ${pc(uPnl)}">${uPnl>=0?'+':''}$${Math.abs(uPnl).toFixed(2)}</div>
      </div>` : ''}`;

    if (!pf.length) {
      $('pf-body').innerHTML = '<div class="empty">保有銘柄なし。上記フォームから追加してください</div>';
      return;
    }
    $('pf-body').innerHTML = `<table><thead><tr>
      <th>銘柄</th><th>数量</th><th>取得価格</th><th>現在価格</th>
      <th>評価損益</th><th>損益率</th><th>取得日</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table>`;
  } catch(e) {
    $('pf-body').innerHTML = '<div class="empty">データ取得失敗</div>';
  }
}
async function addPortfolio() {
  const ticker = $('pf-tk').value.trim().toUpperCase();
  const name   = $('pf-nm').value.trim();
  const qty    = parseFloat($('pf-qty').value);
  const price  = parseFloat($('pf-price').value);
  const cur    = $('pf-cur').value;
  if (!ticker || !qty || !price) { alert('ティッカー・数量・取得価格は必須です'); return; }
  const r = await (await fetch('/api/portfolio/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, name, qty, buy_price:price, currency:cur})
  })).json();
  if (r.ok) { $('pf-tk').value=$('pf-nm').value=$('pf-qty').value=$('pf-price').value=''; loadPortfolio(); }
  else alert(r.msg||'追加失敗');
}
async function removePortfolio(idx) {
  if (!confirm('この保有銘柄を削除しますか？')) return;
  await fetch('/api/portfolio/remove',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({index:idx})
  });
  loadPortfolio();
}

// ─── Alerts ───
async function loadAlerts() {
  try {
    const alerts = await (await fetch('/api/alerts')).json();
    const el = $('al-body');
    if (!alerts.length) {
      el.innerHTML = '<div class="empty">アラートなし。上記フォームから追加してください</div>'; return;
    }
    const esc = v => (v||'').replace(/'/g,'\\x27');
    el.innerHTML = `<table><thead><tr>
      <th>銘柄</th><th>目標価格</th><th>条件</th><th>通貨</th><th>状態</th><th></th>
    </tr></thead><tbody>${alerts.map((a,i) => `
      <tr class="${a.triggered?'al-triggered':''}">
        <td>
          <b style="cursor:pointer;color:var(--b)" onclick="openChart('${esc(a.ticker)}','${esc(a.name||a.ticker)}')">${a.name||a.ticker}</b>
          <div class="ts">${a.ticker}</div>
        </td>
        <td>${a.currency==='JPY'?'¥'+a.target_price.toLocaleString():'$'+a.target_price}</td>
        <td>${a.direction==='above'?'📈 上抜け':'📉 下抜け'}</td>
        <td class="ts">${a.currency}</td>
        <td>${a.triggered?'<span class="badge bs">発動済</span>':'<span class="badge bb">監視中</span>'}</td>
        <td style="display:flex;gap:4px;flex-wrap:wrap">
          ${a.triggered?`<button class="btn btn-outline btn-sm" onclick="resetAlert(${i})">↺ リセット</button>`:''}
          <button class="btn btn-r btn-sm" onclick="removeAlert(${i})">削除</button>
        </td>
      </tr>`).join('')}
    </tbody></table>`;
  } catch(e) {}
}
async function addAlert() {
  const ticker = $('al-tk').value.trim().toUpperCase();
  const name   = $('al-nm').value.trim();
  const price  = parseFloat($('al-price').value);
  const dir    = $('al-dir').value;
  const cur    = $('al-cur').value;
  if (!ticker || !price) { alert('ティッカーと目標価格は必須です'); return; }
  const r = await (await fetch('/api/alerts/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker, name, target_price:price, direction:dir, currency:cur})
  })).json();
  if (r.ok) { $('al-tk').value=$('al-nm').value=$('al-price').value=''; loadAlerts(); }
  else alert(r.msg||'追加失敗');
}
async function removeAlert(idx) {
  if (!confirm('このアラートを削除しますか？')) return;
  await fetch('/api/alerts/remove',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({index:idx})
  });
  loadAlerts();
}
async function resetAlert(idx) {
  await fetch('/api/alerts/reset',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({index:idx})
  });
  loadAlerts();
}

// ─── Settings ───
async function loadSettings() {
  try {
    const s = await (await fetch('/api/settings')).json();
    $('settings-form').innerHTML = `
      <div class="sg">
        <h4>🔔 Discord通知</h4>
        <div class="sr">
          <label>Webhook URL</label>
          <input type="url" id="s-webhook" value="${s.discord_webhook||''}"
            placeholder="https://discord.com/api/webhooks/...">
          <button class="btn btn-outline btn-sm" onclick="testDiscord()" style="flex-shrink:0">テスト送信</button>
        </div>
        <div class="sr-note">Discord → サーバー設定 → 連携サービス → ウェブフック で取得</div>
        <div class="sr">
          <label>通知を有効にする</label>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:400">
            <input type="checkbox" id="s-discord-en" ${s.discord_enabled!==false?'checked':''}>
            BUY / SELL / PTS / 価格アラートをDiscordに通知する
          </label>
        </div>
      </div>
      <div class="sg">
        <h4>📊 シグナル閾値</h4>
        <div class="sr">
          <label>RSI 買われすぎ（デフォルト: 70）</label>
          <input type="number" id="s-rsi-ob" value="${s.rsi_overbought||70}" min="50" max="95" style="max-width:90px;min-width:0">
          <span class="ts">ゴールデンクロス時にこの値以上だとBUYシグナルを抑制</span>
        </div>
        <div class="sr">
          <label>RSI 売られすぎ（デフォルト: 30）</label>
          <input type="number" id="s-rsi-os" value="${s.rsi_oversold||30}" min="5" max="50" style="max-width:90px;min-width:0">
          <span class="ts">デッドクロス時にこの値以下だとSELLシグナルを抑制</span>
        </div>
        <div class="sr">
          <label>PTS大変動アラート閾値（デフォルト: 3.0%）</label>
          <input type="number" id="s-pts-pct" value="${s.pts_alert_pct||3.0}" min="0.5" max="20" step="0.5" style="max-width:90px;min-width:0">
          <span class="ts">% 以上の変動でDiscord通知</span>
        </div>
        <div class="sr-note">閾値変更は次回スキャンサイクル（10分ごと）から反映されます</div>
      </div>
      <div style="text-align:right;margin-top:8px">
        <button class="btn btn-b" onclick="saveSettings()">💾 設定を保存</button>
      </div>`;
  } catch(e) {
    $('settings-form').innerHTML = '<div class="empty">設定の読み込み失敗</div>';
  }
}
async function saveSettings() {
  const data = {
    discord_webhook: $('s-webhook').value.trim(),
    discord_enabled: $('s-discord-en').checked,
    rsi_overbought:  parseInt($('s-rsi-ob').value) || 70,
    rsi_oversold:    parseInt($('s-rsi-os').value) || 30,
    pts_alert_pct:   parseFloat($('s-pts-pct').value) || 3.0,
  };
  const r = await (await fetch('/api/settings',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(data)
  })).json();
  if (r.ok) alert('✅ 設定を保存しました');
  else alert('❌ 保存失敗: ' + (r.msg||''));
}
async function testDiscord() {
  const url = $('s-webhook').value.trim();
  if (!url) { alert('Webhook URLを入力してください'); return; }
  const r = await (await fetch('/api/settings/test_discord',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({webhook:url})
  })).json();
  if (r.ok) alert('✅ テスト送信成功！Discordを確認してください');
  else alert('❌ 送信失敗: ' + (r.msg||''));
}

// ─── Chart Modal ───
let _modalTicker = null;
let _modalLoaded = {chart:false, fund:false, news:false, val:false};

function openModalTab(name) {
  const tabNames = ['chart','fund','news','val','bt'];
  document.querySelectorAll('.mtb').forEach((b,i) =>
    b.classList.toggle('active', tabNames[i] === name));
  document.querySelectorAll('.mtc').forEach(c => c.classList.remove('active'));
  const el = $('mtc-'+name);
  if (el) el.classList.add('active');
  if (name==='fund' && !_modalLoaded.fund) loadModalFundamentals();
  if (name==='news' && !_modalLoaded.news) loadModalNews();
  if (name==='val'  && !_modalLoaded.val)  loadModalValuation();
}

async function openChart(ticker, name) {
  _modalTicker = ticker;
  _btTicker    = ticker;
  _modalLoaded = {chart:false, fund:false, news:false, val:false};
  const dispName = name && name !== ticker ? name : ticker;
  $('modal-title').textContent = dispName;
  $('modal-sub').textContent   = ticker + ' | 分析ダッシュボード';
  $('modal-stats').innerHTML   = '<span class="spinner"></span>';
  $('modal-pts').innerHTML     = '';
  $('modal-fund-body').innerHTML = '<div class="empty"><span class="spinner"></span> 読み込み中...</div>';
  $('modal-news-body').innerHTML = '<div class="empty"><span class="spinner"></span> 読み込み中...</div>';
  $('modal-val-body').innerHTML  = '<div class="empty"><span class="spinner"></span> 読み込み中...</div>';
  $('modal-backtest').innerHTML  = '<div class="ts">「実行」ボタンで過去1年のシミュレーション結果を表示します</div>';
  const btn = $('bt-btn');
  if (btn) { btn.innerHTML = '実行'; btn.disabled = false; }
  document.querySelectorAll('.mtb').forEach((b,i) => b.classList.toggle('active', i===0));
  document.querySelectorAll('.mtc').forEach((c,i) => c.classList.toggle('active', i===0));
  $('overlay').classList.add('open');

  try {
    const [d, analysis] = await Promise.all([
      (await fetch('/api/chart/' + ticker)).json(),
      (await fetch('/api/analysis')).json(),
    ]);
    if (d.error) { $('modal-stats').textContent = d.error; return; }
    _modalLoaded.chart = true;

    const ac    = (analysis.data || {})[ticker] || {};
    const last  = (d.close  || []).filter(Boolean).slice(-1)[0] || 0;
    const first = (d.close  || []).filter(Boolean)[0]  || 1;
    const rLast = (d.rsi    || []).filter(Boolean).slice(-1)[0] || 0;
    const mLast = (d.macd   || []).filter(Boolean).slice(-1)[0] || 0;
    const msLast= (d.macd_signal||[]).filter(Boolean).slice(-1)[0] || 0;
    const totalChg = ((last/first-1)*100);
    const isJpy = ticker.endsWith('.T');
    const fmt = v => isJpy ? '¥'+Math.round(v).toLocaleString() : '$'+v.toFixed(2);

    const sigBadge = ac.signal==='BUY'
      ? '<span class="badge bb">🟢 BUY</span>'
      : ac.signal==='SELL'
      ? '<span class="badge bs">🔴 SELL</span>'
      : '<span class="badge bh">HOLD</span>';

    $('modal-stats').innerHTML = `
      <div class="kv"><div class="kl">現在値</div><div class="kv2">${fmt(last)}</div></div>
      <div class="kv"><div class="kl">60日騰落率</div>
        <div class="kv2 ${totalChg>=0?'pos':'neg'}">${totalChg>=0?'+':''}${totalChg.toFixed(2)}%</div></div>
      <div class="kv"><div class="kl">RSI (14)</div>
        <div class="kv2" style="color:${rsiColor(rLast)}">${rLast.toFixed(1)}</div></div>
      <div class="kv"><div class="kl">MACD</div>
        <div class="kv2 ${mLast>=msLast?'pos':'neg'}">${mLast>=0?'+':''}${mLast.toFixed(3)}</div></div>
      <div class="kv"><div class="kl">シグナル</div>${sigBadge}</div>`;

    if (ac.pts) {
      const p = ac.pts;
      $('modal-pts').innerHTML = `
        <div class="pts-bar">
          <span class="pts-label">⏰ PTS (${p.pts_type==='post'?'時間後':'時間前'})</span>
          <span>${fmt(p.pts_price)}</span>
          <span class="${p.pts_change_pct>=0?'pos':'neg'}" style="font-weight:700">
            ${p.pts_change_pct>=0?'+':''}${p.pts_change_pct.toFixed(2)}%</span>
          <span class="ts">通常: ${fmt(p.regular_price)}</span>
        </div>`;
    }

    if (priceChart) priceChart.destroy();
    priceChart = new Chart($('price-chart'), {
      type:'line', data:{labels:d.dates, datasets:[
        {label:'BB上限',data:d.bb_upper,borderColor:'rgba(175,82,222,.35)',borderWidth:1,pointRadius:0,tension:.1,fill:'+2',backgroundColor:'rgba(175,82,222,.04)'},
        {label:'BB中', data:d.bb_mid,  borderColor:'rgba(175,82,222,.5)', borderWidth:1,pointRadius:0,tension:.1,borderDash:[4,4]},
        {label:'BB下限',data:d.bb_lower,borderColor:'rgba(175,82,222,.35)',borderWidth:1,pointRadius:0,tension:.1},
        {label:'終値',  data:d.close,  borderColor:'#1d1d1f',borderWidth:2,pointRadius:0,tension:.1},
        {label:'MA5',   data:d.ma5,    borderColor:'#ff9f0a',borderWidth:1.5,pointRadius:0,tension:.1},
        {label:'MA25',  data:d.ma25,   borderColor:'#ff3b30',borderWidth:1.5,pointRadius:0,tension:.1},
      ]},
      options:{responsive:true,maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{font:{size:10},boxWidth:14}}},
        scales:{x:{ticks:{maxTicksLimit:8,font:{size:10}}},y:{ticks:{font:{size:10},callback:v=>fmt(v)}}}}
    });

    if (macdChart) macdChart.destroy();
    const histColors = (d.macd_hist||[]).map(v =>
      v==null?'transparent':v>=0?'rgba(52,199,89,.6)':'rgba(255,59,48,.6)');
    macdChart = new Chart($('macd-chart'), {
      data:{labels:d.dates, datasets:[
        {type:'bar', label:'ヒスト',data:d.macd_hist,backgroundColor:histColors,yAxisID:'y'},
        {type:'line',label:'MACD',  data:d.macd,  borderColor:'#007aff',borderWidth:1.5,pointRadius:0,tension:.2,yAxisID:'y'},
        {type:'line',label:'Signal',data:d.macd_signal,borderColor:'#ff9f0a',borderWidth:1.5,pointRadius:0,tension:.2,yAxisID:'y'},
      ]},
      options:{responsive:true,maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{font:{size:10},boxWidth:12}}},
        scales:{x:{ticks:{maxTicksLimit:8,font:{size:10}}},y:{ticks:{font:{size:10}},grid:{color:'rgba(0,0,0,.05)'}}}}
    });

    if (rsiChart) rsiChart.destroy();
    rsiChart = new Chart($('rsi-chart'), {
      type:'line', data:{labels:d.dates, datasets:[{
        label:'RSI',data:d.rsi,borderColor:'#007aff',borderWidth:1.5,pointRadius:0,fill:false,tension:.2,
      }]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false}},
        scales:{x:{ticks:{maxTicksLimit:8,font:{size:10}}},
          y:{min:0,max:100,ticks:{font:{size:10},callback:v=>[30,50,70].includes(v)?v:''},
            grid:{color:ctx=>ctx.tick.value===70?'rgba(255,59,48,.25)':ctx.tick.value===30?'rgba(52,199,89,.25)':'rgba(0,0,0,.04)'}}}}
    });
  } catch(e) {
    $('modal-stats').textContent = 'データ取得失敗: '+e.message;
  }
}

async function loadModalFundamentals() {
  if (!_modalTicker) return;
  const el = $('modal-fund-body');
  try {
    const f = await (await fetch('/api/fundamentals/'+_modalTicker)).json();
    if (!f || (!f.per && !f.eps && !f.market_cap && !f.pbr)) {
      el.innerHTML = '<div class="empty">基本情報データなし（yfinance未対応銘柄）<br><span class="ts">※ 投資信託・一部銘柄では取得不可</span></div>';
      _modalLoaded.fund = true; return;
    }
    const fv = (v, unit='') => v != null ? v + unit : '<span class="ts">—</span>';
    const fvCap = v => {
      if (v == null) return '<span class="ts">—</span>';
      if (v >= 1e12) return (v/1e12).toFixed(1) + 'T';
      if (v >= 1e9)  return (v/1e9).toFixed(1) + 'B';
      if (v >= 1e6)  return (v/1e6).toFixed(1) + 'M';
      return v.toLocaleString();
    };
    let html = '';
    html += '<div class="fund-section"><h4>バリュエーション</h4><div class="fund-grid">';
    html += `<div class="fund-kv"><div class="fk">PER (実績)</div><div class="fv">${fv(f.per,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">PER (予想)</div><div class="fv">${fv(f.forward_per,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">PBR</div><div class="fv">${fv(f.pbr,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">PSR</div><div class="fv">${fv(f.psr,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">時価総額</div><div class="fv">${fvCap(f.market_cap)}</div><div class="fn">${f.currency||''}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">ベータ</div><div class="fv">${fv(f.beta)}</div></div>`;
    html += '</div></div>';
    html += '<div class="fund-section"><h4>収益性</h4><div class="fund-grid">';
    html += `<div class="fund-kv"><div class="fk">ROE</div><div class="fv">${fv(f.roe,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">ROA</div><div class="fv">${fv(f.roa,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">売上総利益率</div><div class="fv">${fv(f.gross_margin,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">営業利益率</div><div class="fv">${fv(f.operating_margin,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">EPS (実績)</div><div class="fv">${fv(f.eps)}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">EPS (予想)</div><div class="fv">${fv(f.forward_eps)}</div></div>`;
    html += '</div></div>';
    html += '<div class="fund-section"><h4>配当・成長・レンジ</h4><div class="fund-grid">';
    html += `<div class="fund-kv"><div class="fk">配当利回り</div><div class="fv">${fv(f.dividend_yield,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">1株配当</div><div class="fv">${fv(f.dividend_per)}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">売上成長率</div><div class="fv">${fv(f.revenue_growth,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">利益成長率</div><div class="fv">${fv(f.earnings_growth,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">52週高値</div><div class="fv">${fv(f['52w_high'])}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">52週安値</div><div class="fv">${fv(f['52w_low'])}</div></div>`;
    html += '</div></div>';
    if (f.sector || f.industry) {
      html += '<div class="fund-section"><h4>属性</h4><div class="fund-grid">';
      if (f.sector)    html += `<div class="fund-kv"><div class="fk">セクター</div><div class="fv" style="font-size:13px">${f.sector}</div></div>`;
      if (f.industry)  html += `<div class="fund-kv"><div class="fk">業種</div><div class="fv" style="font-size:13px">${f.industry}</div></div>`;
      if (f.employees) html += `<div class="fund-kv"><div class="fk">従業員数</div><div class="fv" style="font-size:13px">${f.employees.toLocaleString()}人</div></div>`;
      html += '</div></div>';
    }
    html += '<div class="ts" style="margin-top:4px">※ yfinance遅延データ。投資助言ではありません。</div>';
    _modalLoaded.fund = true;
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="empty">基本情報取得失敗</div>';
  }
}

async function loadModalNews() {
  if (!_modalTicker) return;
  const el = $('modal-news-body');
  try {
    const data = await (await fetch('/api/news/'+_modalTicker)).json();
    const sent = data.sentiment || {};
    const news = data.news || [];
    let html = '';
    if (sent.label && sent.label !== 'N/A' && news.length > 0) {
      const color = sent.color || '#8e8e93';
      const pct = Math.min(100, Math.max(0, (sent.score+2)/4*100));
      html += `<div class="sent-panel" style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:13px;font-weight:600">感情分析</span>
          <span style="color:${color};font-weight:700;font-size:13px">${sent.label}（スコア: ${sent.score>=0?'+':''}${sent.score}）</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--sub);margin-bottom:4px">
          <span>弱気</span><span>中立</span><span>強気</span>
        </div>
        <div class="sent-score-bar"><div class="sent-score-fill" style="width:${pct}%;background:${color}"></div></div>
        <div class="ts" style="margin-top:4px">${news.length}件を「${sent.method||'—'}」で分析</div>
      </div>`;
    }
    if (!news.length) {
      html += '<div class="empty">ニュースなし</div>';
    } else {
      news.forEach(n => {
        html += `<div class="news-item">
          <div class="news-title"><a href="${n.link||'#'}" target="_blank" rel="noopener">${n.title||'—'}</a></div>
          <div class="news-meta">
            ${n.publisher ? n.publisher + ' &nbsp;·&nbsp; ' : ''}
            ${n.published ? n.published + ' &nbsp;·&nbsp; ' : ''}
            スコア: <span class="${n.score>0?'news-score-pos':n.score<0?'news-score-neg':''}">${n.score>=0?'+':''}${n.score}</span>
          </div>
        </div>`;
      });
    }
    _modalLoaded.news = true;
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="empty">ニュース取得失敗</div>';
  }
}

async function loadModalValuation() {
  if (!_modalTicker) return;
  const el = $('modal-val-body');
  try {
    const f = await (await fetch('/api/fundamentals/'+_modalTicker)).json();
    const isJp = _modalTicker.endsWith('.T');
    const fv = (v, unit='') => v != null ? v + unit : '—';
    let html = '';
    if (isJp && f.theoretical_price) {
      const upside = f.theoretical_upside_pct;
      html += `<div class="val-box">
        <div class="vb-label">理論株価（AI/簡易推定）</div>
        <div class="vb-price">¥${Math.round(f.theoretical_price).toLocaleString()}</div>
        ${upside != null ? `<div style="font-size:15px;font-weight:600;margin-top:4px" class="${upside>=0?'pos':'neg'}">
          現在値との乖離: ${upside>=0?'+':''}${upside}%</div>` : ''}
        <div class="vb-note">${f.theoretical_note||''}</div>
      </div>`;
    } else if (!isJp && f.target_mean) {
      const upside = f.target_upside_pct;
      html += `<div class="val-box">
        <div class="vb-label">アナリスト目標株価（平均）</div>
        <div class="vb-price">$${f.target_mean}</div>
        ${upside != null ? `<div style="font-size:15px;font-weight:600;margin-top:4px" class="${upside>=0?'pos':'neg'}">
          現在値との乖離: ${upside>=0?'+':''}${upside}%</div>` : ''}
        <div class="vb-note">※ アナリスト予測。投資助言ではありません。</div>
      </div>`;
    }
    if (!isJp && (f.target_high || f.target_low || f.recommendation || f.analyst_count)) {
      const recMap = {strongbuy:'強い買い',buy:'買い',hold:'中立',sell:'売り',strongsell:'強い売り'};
      html += '<div class="fund-section"><h4>アナリスト評価</h4><div class="fund-grid">';
      if (f.recommendation) html += `<div class="fund-kv"><div class="fk">推奨</div><div class="fv" style="font-size:14px">${recMap[f.recommendation]||f.recommendation}</div></div>`;
      if (f.analyst_count)  html += `<div class="fund-kv"><div class="fk">アナリスト数</div><div class="fv">${f.analyst_count}名</div></div>`;
      if (f.target_high)    html += `<div class="fund-kv"><div class="fk">目標高値</div><div class="fv">$${f.target_high}</div></div>`;
      if (f.target_low)     html += `<div class="fund-kv"><div class="fk">目標安値</div><div class="fv">$${f.target_low}</div></div>`;
      html += '</div></div>';
    }
    html += '<div class="fund-section"><h4>財務サマリー</h4><div class="fund-grid">';
    html += `<div class="fund-kv"><div class="fk">PER</div><div class="fv">${fv(f.per,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">PBR</div><div class="fv">${fv(f.pbr,'倍')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">ROE</div><div class="fv">${fv(f.roe,'%')}</div></div>`;
    html += `<div class="fund-kv"><div class="fk">配当利回り</div><div class="fv">${fv(f.dividend_yield,'%')}</div></div>`;
    html += '</div></div>';
    if (!html.includes('val-box') && !html.includes('アナリスト')) {
      html = '<div class="empty">評価データなし（yfinance未対応銘柄）</div>' + html;
    }
    html += '<div class="ts" style="margin-top:8px">※ yfinance遅延データ・AI/簡易推定。投資助言ではありません。</div>';
    _modalLoaded.val = true;
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<div class="empty">評価データ取得失敗</div>';
  }
}

function closeOverlay() { $('overlay').classList.remove('open'); }
function closeModal(e)  { if (e.target===$('overlay')) closeOverlay(); }

// ─── Fund Screener ───
let _fscSigFilter   = 'all';
let _fscCrossFilter = 'all';

function fscFilter(val, type) {
  if (type==='sig')   _fscSigFilter   = val;
  if (type==='cross') _fscCrossFilter = (_fscCrossFilter===val ? 'all' : val);
  renderFundScreener();
}

async function loadFundScreener() {
  try {
    const [analysis, wl] = await Promise.all([
      (await fetch('/api/analysis')).json(),
      (await fetch('/api/watchlist')).json(),
    ]);
    window._fscAnalysis = analysis.data || {};
    window._fscWl = [...(wl.jp||[]), ...(wl.us||[])];
    renderFundScreener();
  } catch(e) {
    $('fsc-body').innerHTML = '<div class="empty">読み込み失敗</div>';
  }
}

function renderFundScreener() {
  const analysis = window._fscAnalysis || {};
  const wl = window._fscWl || [];
  const el = $('fsc-body');
  if (!el) return;
  if (!wl.length) { el.innerHTML = '<div class="empty">監視銘柄なし</div>'; return; }

  let list = wl.filter(s => {
    const ac  = analysis[s.ticker] || {};
    const sig = (ac.signal || 'HOLD').toLowerCase();
    const cross = ac.cross || '';
    const sigOk   = _fscSigFilter==='all' || sig===_fscSigFilter;
    const crossOk = _fscCrossFilter==='all' || cross===_fscCrossFilter;
    return sigOk && crossOk;
  });

  // update filter button states
  document.querySelectorAll('#fs-filters .fb').forEach(b => {
    const ft = b.dataset.ftype, fv = b.dataset.fval;
    const active = ft==='sig'   ? _fscSigFilter===fv
                 : ft==='cross' ? _fscCrossFilter===fv
                 : false;
    b.classList.toggle('active', active);
    if (ft==='sig' && fv==='all' && _fscSigFilter!=='buy' && _fscSigFilter!=='sell') b.classList.add('active');
    if (ft==='sig' && fv!=='all') b.classList.toggle('active', _fscSigFilter===fv);
  });

  if (!list.length) { el.innerHTML = '<div class="empty">条件に一致する銘柄なし</div>'; return; }

  const fmt = (v, t) => {
    if (v == null) return '—';
    return t.endsWith('.T') ? '¥'+Math.round(v).toLocaleString() : '$'+v.toFixed(2);
  };
  let html = '';
  list.forEach(s => {
    const ac  = analysis[s.ticker] || {};
    const sig = ac.signal || 'HOLD';
    const sigBadge = sig==='BUY' ? '<span class="badge bb">BUY</span>'
      : sig==='SELL' ? '<span class="badge bs">SELL</span>'
      : '<span class="badge bh">HOLD</span>';
    const chg = ac.daily_change_pct;
    const crossLabel = ac.cross==='golden'
      ? '<span style="color:var(--g);font-size:10px;font-weight:600">✨ゴールデン</span>'
      : ac.cross==='dead'
      ? '<span style="color:var(--r);font-size:10px;font-weight:600">💀デッド</span>'
      : '';
    const esc = v => (v||'').replace(/'/g,'\\x27');
    html += `<div class="fsc-row">
      <div class="fsc-info" onclick="openChart('${esc(s.ticker)}','${esc(s.name||s.ticker)}')">
        <div class="fsc-name">${s.name||s.ticker}</div>
        <div class="fsc-ticker">${s.ticker}</div>
      </div>
      <div class="fsc-metrics">
        <div class="fsc-m">価格: <b>${fmt(ac.price,s.ticker)}</b></div>
        ${chg!=null?`<div class="fsc-m ${chg>=0?'pos':'neg'}">前日比: <b>${chg>=0?'+':''}${chg.toFixed(2)}%</b></div>`:''}
        <div class="fsc-m">RSI: <b style="color:${rsiColor(ac.rsi||50)}">${(ac.rsi||0).toFixed(0)}</b></div>
        ${crossLabel}
      </div>
      ${sigBadge}
    </div>`;
  });
  el.innerHTML = html;
}

// ─── Backtest ───
async function runBacktest() {
  if (!_btTicker) return;
  const btn = $('bt-btn');
  if (btn) { btn.innerHTML='<span class="spinner"></span>'; btn.disabled=true; }
  $('modal-backtest').innerHTML='<div class="ts"><span class="spinner"></span> 実行中（数秒〜15秒）...</div>';
  try {
    const d = await (await fetch('/api/backtest/'+_btTicker)).json();
    if (d.error) {
      $('modal-backtest').innerHTML=`<div class="ts" style="color:var(--r)">エラー: ${d.error}</div>`;
      return;
    }
    $('modal-backtest').innerHTML = `
      <div class="bt-summary">
        <div class="bt-kv"><div class="bk">トレード数</div><div class="bv">${d.trade_count}</div></div>
        <div class="bt-kv"><div class="bk">勝率</div>
          <div class="bv ${d.win_rate>=50?'pos':'neg'}">${d.win_rate}%</div></div>
        <div class="bt-kv"><div class="bk">合計リターン</div>
          <div class="bv ${d.total_return>=0?'pos':'neg'}">${d.total_return>=0?'+':''}${d.total_return}%</div></div>
        <div class="bt-kv"><div class="bk">平均リターン</div>
          <div class="bv ${d.avg_return>=0?'pos':'neg'}">${d.avg_return>=0?'+':''}${d.avg_return}%</div></div>
      </div>
      ${d.trades.length?`
      <div style="font-size:12px;color:var(--sub);margin-bottom:6px">直近${d.trades.length}件のトレード</div>
      <table><thead><tr>
        <th>買い日</th><th>売り日</th><th>買値</th><th>売値</th><th>損益率</th>
      </tr></thead><tbody>${[...d.trades].reverse().map(t=>`<tr>
        <td class="ts">${t.buy_date}</td><td class="ts">${t.sell_date}</td>
        <td>${t.buy_price}</td><td>${t.sell_price}</td>
        <td class="${t.pnl_pct>=0?'pos':'neg'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct}%</td>
      </tr>`).join('')}</tbody></table>`
      :'<div class="ts" style="padding:8px 0">対象期間内にトレードなし</div>'}`;
  } catch(e) {
    $('modal-backtest').innerHTML=`<div class="ts" style="color:var(--r)">取得失敗: ${e.message}</div>`;
  } finally {
    if (btn) { btn.innerHTML='再実行'; btn.disabled=false; }
  }
}

// ─── Manual Scan ───
async function manualScan() {
  const btn = $('scan-btn');
  btn.innerHTML = '<span class="spinner"></span> スキャン中...';
  btn.disabled = true;
  try {
    const r = await (await fetch('/api/scan',{method:'POST'})).json();
    const buy  = (r.signals||[]).filter(s=>s.signal==='BUY').length;
    const sell = (r.signals||[]).filter(s=>s.signal==='SELL').length;
    alert(`スキャン完了: ${r.count}銘柄\n🟢 BUY: ${buy}件  🔴 SELL: ${sell}件`);
    refreshAll();
  } catch(e) { alert('スキャン失敗: '+e.message); }
  finally { btn.innerHTML='🔄 今すぐスキャン'; btn.disabled=false; }
}

// ─── Watchlist CRUD ───
async function addStock() {
  const ticker = $('tk').value.trim().toUpperCase();
  const name   = $('nm').value.trim();
  const market = $('mkt').value;
  if (!ticker) { alert('ティッカーを入力してください'); return; }
  const r = await (await fetch('/api/watchlist/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker,name,market})
  })).json();
  if (r.ok) { $('tk').value=''; $('nm').value=''; loadWatchlist(); loadAnalysis(); }
  else alert(r.msg);
}
async function rmStock(ticker,market) {
  if (!confirm(ticker+' を削除しますか？')) return;
  await fetch('/api/watchlist/remove',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker,market})
  });
  loadWatchlist(); loadAnalysis();
}
async function editName(ticker,market,currentName) {
  const newName = prompt(ticker+' の銘柄名:',currentName);
  if (newName===null) return;
  const r = await (await fetch('/api/watchlist/rename',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker,name:newName.trim(),market})
  })).json();
  if (r.ok) { loadWatchlist(); loadAnalysis(); }
  else alert('更新失敗: '+(r.msg||''));
}

// ─── Screener ───
let screenerData=null, scRegion='JP', scCategory=null;
async function loadScreener() {
  if (!screenerData) {
    const r = await (await fetch('/api/screener')).json();
    screenerData = r;
  }
  renderScCategories(); renderScStocks();
}
function showRegion(region) {
  scRegion=region; scCategory=null;
  document.querySelectorAll('.sc-rb').forEach((b,i)=>
    b.classList.toggle('active',['JP','US','OTHER'][i]===region));
  $('sc-search').value=''; closeSuggest();
  renderScCategories(); renderScStocks();
}
function renderScCategories() {
  if (!screenerData) return;
  const cats=Object.keys(screenerData[scRegion]||{});
  if (!scCategory||!cats.includes(scCategory)) scCategory=cats[0];
  $('sc-cats').innerHTML=cats.map(cat=>{
    const n=((screenerData[scRegion]||{})[cat]||[]).length;
    return `<button class="sc-cat ${cat===scCategory?'active':''}"
      onclick="showCategory('${cat.replace(/'/g,'\\x27')}')">${cat} <span style="opacity:.6">${n}</span></button>`;
  }).join('');
}
function showCategory(cat) {
  scCategory=cat; $('sc-search').value=''; closeSuggest();
  document.querySelectorAll('.sc-cat').forEach(b=>
    b.classList.toggle('active',b.textContent.trim().startsWith(cat)));
  renderScStocks();
}
// ─── Screener search engine ───
let _scSugIdx  = -1;
let _scBlurTid = null;

function _scTokens(q) {
  return (q||'').toLowerCase().trim().split(/\s+/).filter(Boolean);
}
function _scScore(s, tokens) {
  const tk  = s.ticker.toLowerCase();
  const tkb = tk.replace('.t','');
  const nm  = s.name.toLowerCase();
  const en  = (s.en||'').toLowerCase();
  let score = 0;
  for (const t of tokens) {
    if (!t) continue;
    if (tk===t || tkb===t)               { score+=100; continue; }
    if (tk.startsWith(t)||tkb.startsWith(t)) { score+=60; continue; }
    if (tk.includes(t))                  { score+=30; continue; }
    if (nm.startsWith(t)||en.startsWith(t)) { score+=25; continue; }
    if (nm.includes(t))                  { score+=15; continue; }
    if (en.includes(t))                  { score+=12; continue; }
    score -= 50; // token matched nothing → exclude
  }
  return score;
}
function _scSearch(q) {
  if (!screenerData || !q.trim()) return [];
  const tokens = _scTokens(q);
  const seen = new Set(); const results = [];
  for (const [reg,cats] of Object.entries(screenerData))
    for (const [cat,arr] of Object.entries(cats))
      for (const s of arr) {
        if (seen.has(s.ticker)) continue;
        const score = _scScore(s, tokens);
        if (score > 0) { seen.add(s.ticker); results.push({...s,_reg:reg,_cat:cat,_score:score}); }
      }
  return results.sort((a,b)=>b._score-a._score);
}
function _hlText(text, tokens) {
  if (!tokens.length) return text;
  const re = new RegExp('('+tokens.map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')', 'gi');
  return text.replace(re,'<span class="hl">$1</span>');
}

function onScSearch(e) {
  const q = e.target.value;
  _scSugIdx = -1;
  if (!q.trim()) { closeSuggest(); renderScStocks(); return; }
  const results = _scSearch(q);
  showSuggest(results, q);
  renderScStocksFromList(results, q);
}
function onScSearchFocus() {
  if (_scBlurTid) { clearTimeout(_scBlurTid); _scBlurTid=null; }
  const q = ($('sc-search').value||'').trim();
  if (q) { const r=_scSearch(q); showSuggest(r,q); }
}
function onScSearchBlur() {
  _scBlurTid = setTimeout(closeSuggest, 180);
}
function onScSearchKey(e) {
  const sug = $('sc-suggest');
  const items = sug ? sug.querySelectorAll('.sc-sug-item') : [];
  if (e.key==='ArrowDown') {
    e.preventDefault(); _scSugIdx=Math.min(_scSugIdx+1,items.length-1);
    items.forEach((el,i)=>el.classList.toggle('hi',i===_scSugIdx));
  } else if (e.key==='ArrowUp') {
    e.preventDefault(); _scSugIdx=Math.max(_scSugIdx-1,0);
    items.forEach((el,i)=>el.classList.toggle('hi',i===_scSugIdx));
  } else if (e.key==='Enter') {
    if (_scSugIdx>=0 && items[_scSugIdx]) items[_scSugIdx].click();
    else { closeSuggest(); renderScStocks(); }
  } else if (e.key==='Escape') {
    closeSuggest(); $('sc-search').value=''; renderScStocks();
  }
}
function closeSuggest() {
  const el = $('sc-suggest');
  if (el) el.classList.remove('open');
}
function showSuggest(results, q) {
  const el = $('sc-suggest');
  if (!el) return;
  const tokens = _scTokens(q);
  const top = results.slice(0,10);
  if (!top.length) { el.classList.remove('open'); return; }
  const rows = top.map(s => {
    const esc = v=>(v||'').replace(/'/g,'\\x27');
    const mkt = s.ticker.endsWith('.T')?'JP':'US';
    const isFlag = mkt==='JP'?'🇯🇵':'🇺🇸';
    return `<div class="sc-sug-item" onmousedown="selectSuggest('${esc(s.ticker)}','${esc(s.name)}','${mkt}')">
      <span class="sc-sug-ticker">${isFlag} ${_hlText(s.ticker,tokens)}</span>
      <span class="sc-sug-name">${_hlText(s.name,tokens)}</span>
      <span class="sc-sug-cat">${s._cat||''}</span>
    </div>`;
  }).join('');
  el.innerHTML = `<div class="sc-sug-hd">候補 ${results.length}件${results.length>10?' (上位10件表示)':''}</div>${rows}`;
  el.classList.add('open');
}
function selectSuggest(ticker, name, market) {
  closeSuggest();
  $('sc-search').value = ticker + ' ' + name;
  const results = _scSearch(ticker);
  renderScStocksFromList(results, ticker);
}

async function renderScStocks(stocks) {
  if (!screenerData) return;
  const q = ($('sc-search').value||'').trim();
  if (q) {
    renderScStocksFromList(_scSearch(q), q);
    return;
  }
  const list = stocks || (screenerData[scRegion]||{})[scCategory] || [];
  await _renderList(list, null, scCategory + ' (' + list.length + '件)');
}
async function renderScStocksFromList(list, q) {
  const tokens = q ? _scTokens(q) : [];
  const label = q ? `🔍 検索結果: ${list.length}件` : (scCategory + ' (' + list.length + '件)');
  await _renderList(list, tokens, label);
}
async function _renderList(list, tokens, label) {
  const wl   = await (await fetch('/api/watchlist')).json();
  const wlSet = new Set([...wl.jp.map(s=>s.ticker),...wl.us.map(s=>s.ticker)]);
  if (!list.length) {
    $('sc-list').innerHTML = `<div style="font-size:12px;color:var(--sub);margin-bottom:8px">${label}</div><div class="empty">該当なし</div>`;
    return;
  }
  const hl = (t,tok) => tok&&tok.length ? _hlText(t,tok) : t;
  $('sc-list').innerHTML = `
    <div style="font-size:12px;color:var(--sub);margin-bottom:8px">${label}</div>
    <div class="sc-list-grid" style="background:var(--card);border-radius:8px;border:1px solid var(--bd)">
      ${list.map(s=>{
        const inWL = wlSet.has(s.ticker);
        const mkt  = s.ticker.endsWith('.T')?'JP':'US';
        const esc  = v=>(v||'').replace(/'/g,'\\x27');
        const catBadge = s._cat ? `<span class="ts" style="margin-left:8px">${s._cat}</span>` : '';
        return `<div class="sc-row">
          <div class="sc-info" onclick="openChart('${esc(s.ticker)}','${esc(s.name)}')">
            <div class="sc-name">${hl(s.name,tokens)}${catBadge}</div>
            <div class="sc-ticker">${hl(s.ticker,tokens)}</div>
          </div>
          ${inWL
            ?'<span class="badge bb" style="min-width:64px;text-align:center">追加済み</span>'
            :`<button class="btn btn-b btn-sm"
                onclick="addFromScreener('${esc(s.ticker)}','${esc(s.name)}','${mkt}')">+ 追加</button>`}
        </div>`;
      }).join('')}
    </div>`;
}
async function filterScreener() { await renderScStocks(); }
async function addFromScreener(ticker,name,market) {
  const r=await (await fetch('/api/watchlist/add',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ticker,name,market})
  })).json();
  if (r.ok) { renderScStocks(); loadAnalysis(); }
  else alert('追加失敗: '+(r.msg||''));
}

// ─── GitHub更新 ───
async function gitPull() {
  if (!confirm('GitHubから最新コードを取得してbotを再起動します。よろしいですか？')) return;
  const btn = $('pull-btn');
  btn.innerHTML = '<span class="spinner"></span> 更新中...';
  btn.disabled = true;
  try {
    const r = await (await fetch('/api/git/pull',{method:'POST'})).json();
    if (r.ok) {
      alert('✅ '+r.msg+'\nページを再読み込みします。');
      setTimeout(()=>location.reload(), 2000);
    } else alert('❌ エラー:\n'+r.msg);
  } catch(e) { alert('通信エラー: '+e.message); }
  finally { btn.innerHTML='⬇️ アップデート'; btn.disabled=false; }
}

// ─── Init ───
loadMarket(); loadStats(); loadAnalysis(); loadSignals();
startAuto();

</script>
</body>
</html>"""


def create_app(trader, watchlist_manager, notifier_mod=None, agent=None,
               settings_manager=None, portfolio_manager=None,
               alert_manager=None) -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)

    @app.route("/")
    def index():
        return _HTML

    @app.route("/api/stats")
    def api_stats():
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
        from sentiment import get_sentiment
        return jsonify(get_sentiment(ticker.upper()))

    # ── Settings ──

    @app.route("/api/settings")
    def api_settings_get():
        if settings_manager:
            return jsonify(settings_manager.all())
        return jsonify({})

    @app.route("/api/settings", methods=["POST"])
    def api_settings_post():
        if not settings_manager:
            return jsonify({"ok": False, "msg": "設定マネージャー未初期化"})
        settings_manager.update(request.get_json() or {})
        return jsonify({"ok": True})

    @app.route("/api/settings/test_discord", methods=["POST"])
    def api_test_discord():
        data = request.get_json() or {}
        url  = data.get("webhook", "").strip()
        if not url:
            return jsonify({"ok": False, "msg": "URLが空です"})
        try:
            import requests as req
            r = req.post(url, json={"content": "🧪 kabutobot テスト通知"}, timeout=5)
            if r.status_code in (200, 204):
                return jsonify({"ok": True})
            return jsonify({"ok": False, "msg": f"HTTP {r.status_code}"})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    # ── Portfolio ──

    @app.route("/api/portfolio")
    def api_portfolio():
        return jsonify(portfolio_manager.all() if portfolio_manager else [])

    @app.route("/api/portfolio/add", methods=["POST"])
    def api_portfolio_add():
        if not portfolio_manager:
            return jsonify({"ok": False, "msg": "未初期化"})
        data   = request.get_json() or {}
        ticker = (data.get("ticker") or "").strip().upper()
        if not ticker:
            return jsonify({"ok": False, "msg": "ティッカー必須"})
        portfolio_manager.add(
            ticker,
            (data.get("name") or "").strip(),
            data.get("qty", 1),
            data.get("buy_price", 0),
            data.get("currency", "JPY"),
        )
        return jsonify({"ok": True})

    @app.route("/api/portfolio/remove", methods=["POST"])
    def api_portfolio_remove():
        if not portfolio_manager:
            return jsonify({"ok": False, "msg": "未初期化"})
        portfolio_manager.remove(int((request.get_json() or {}).get("index", -1)))
        return jsonify({"ok": True})

    # ── Alerts ──

    @app.route("/api/alerts")
    def api_alerts():
        return jsonify(alert_manager.all() if alert_manager else [])

    @app.route("/api/alerts/add", methods=["POST"])
    def api_alerts_add():
        if not alert_manager:
            return jsonify({"ok": False, "msg": "未初期化"})
        data   = request.get_json() or {}
        ticker = (data.get("ticker") or "").strip().upper()
        if not ticker:
            return jsonify({"ok": False, "msg": "ティッカー必須"})
        alert_manager.add(
            ticker,
            (data.get("name") or "").strip(),
            data.get("target_price", 0),
            data.get("direction", "above"),
            data.get("currency", "JPY"),
        )
        return jsonify({"ok": True})

    @app.route("/api/alerts/remove", methods=["POST"])
    def api_alerts_remove():
        if not alert_manager:
            return jsonify({"ok": False, "msg": "未初期化"})
        alert_manager.remove(int((request.get_json() or {}).get("index", -1)))
        return jsonify({"ok": True})

    @app.route("/api/alerts/reset", methods=["POST"])
    def api_alerts_reset():
        if not alert_manager:
            return jsonify({"ok": False, "msg": "未初期化"})
        alert_manager.reset(int((request.get_json() or {}).get("index", -1)))
        return jsonify({"ok": True})

    # ── Fundamentals ──

    @app.route("/api/fundamentals/<ticker>")
    def api_fundamentals(ticker):
        from valuation import get_fundamentals
        return jsonify(get_fundamentals(ticker.upper()))

    # ── News + Sentiment ──

    @app.route("/api/news/<ticker>")
    def api_news(ticker):
        from news_fetcher import get_news
        from sentiment import get_sentiment_from_news
        t = ticker.upper()
        name = ""
        for s in watchlist_manager.get_jp() + watchlist_manager.get_us():
            if s["ticker"] == t:
                name = s.get("name", "")
                break
        news = get_news(t, name)
        sent = get_sentiment_from_news(news, t)
        return jsonify({"news": news, "sentiment": sent})

    # ── Backtest ──

    @app.route("/api/backtest/<ticker>")
    def api_backtest(ticker):
        from backtest import run_backtest
        return jsonify(run_backtest(ticker.upper()))

    # ── Git Pull / Scan / Log ──

    @app.route("/api/git/pull", methods=["POST"])
    def api_git_pull():
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
                import time, signal
                old_pid = os.getpid()
                # 旧プロセスを先に終了させてからポートを解放し、新プロセスを起動
                subprocess.Popen(
                    ["bash", "-c",
                     f"sleep 4 && cd {bot_dir} && nohup python main.py >> kabutobot.log 2>&1 &"],
                    start_new_session=True,
                )
                time.sleep(1)
                os.kill(old_pid, signal.SIGTERM)

            threading.Thread(target=_restart, daemon=True).start()
            return jsonify({"ok": True, "msg": msg})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    @app.route("/api/scan", methods=["POST"])
    def api_scan():
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
                        try: notifier_mod.notify_buy_signal(result)
                        except Exception: pass
                    elif result["signal"] == "SELL":
                        try: notifier_mod.notify_sell_signal(result)
                        except Exception: pass
            except Exception as e:
                log.warning(f"[Dashboard] {stock['ticker']}: {e}")

        if agent:
            import threading
            threading.Thread(target=agent.cycle, daemon=True).start()

        return jsonify({"ok": True, "count": len(results), "signals": results})

    @app.route("/api/log/view")
    def api_log_view():
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
