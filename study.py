#!/usr/bin/env python3
"""Daily vocabulary study — middle school multi-subject version."""

import json
import os
import random
import sys
import webbrowser
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR    = Path(__file__).parent
VOCAB_FILE    = SCRIPT_DIR / "vocab.json"
PROGRESS_FILE = SCRIPT_DIR / "progress.json"
HTML_FILE     = SCRIPT_DIR / "index.html"

BATCH_SIZE = 4
NO_BROWSER = "--no-browser" in sys.argv or os.environ.get("CI") == "true"

# 科目設定
#   unlimited=True  → 毎日プールを全単語にリセット（数量制限なし）
#   unlimited=False → DAILY_POOL_SIZE 件ずつローテーション
DAILY_POOL_SIZE = 20
SUBJECT_CONFIG = {
    "英語": {"emoji": "🇬🇧", "color": "#4f46e5", "light": "#eef2ff", "unlimited": True},
    "国語": {"emoji": "📖", "color": "#dc2626", "light": "#fef2f2", "unlimited": False},
    "社会": {"emoji": "🌍", "color": "#16a34a", "light": "#f0fdf4", "unlimited": False},
    "理科": {"emoji": "🔬", "color": "#d97706", "light": "#fffbeb", "unlimited": False},
    "数学": {"emoji": "📐", "color": "#7c3aed", "light": "#f5f3ff", "unlimited": False},
}
SUBJECT_ORDER = list(SUBJECT_CONFIG.keys())


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_streak(history):
    if not history:
        return 0
    today = date.today()
    dates = sorted([date.fromisoformat(h["date"]) for h in history], reverse=True)
    if (today - dates[0]).days > 1:
        return 0
    streak = 1
    for i in range(1, len(dates)):
        if (dates[i - 1] - dates[i]).days == 1:
            streak += 1
        else:
            break
    return streak


def get_today_pool(vocab_for_subject, subject_history, today_str, unlimited=False):
    existing = next((h for h in subject_history if h["date"] == today_str), None)
    if existing:
        return existing["pool"]

    if unlimited:
        # 全単語をそのまま今日のプールに（number順 → id順）
        pool = sorted([w["id"] for w in vocab_for_subject],
                      key=lambda wid: next((w.get("number", 99999) for w in vocab_for_subject if w["id"] == wid), 99999))
    else:
        introduced = {wid for h in subject_history for wid in h.get("pool", [])}
        remaining = [w for w in vocab_for_subject if w["id"] not in introduced]
        if not remaining:
            remaining = vocab_for_subject[:]
        random.shuffle(remaining)
        pool = [w["id"] for w in remaining[:DAILY_POOL_SIZE]]

    subject_history.append({"date": today_str, "pool": pool})
    return pool


def generate_html(vocab, today_pools, streaks, progress_stats, subjects, today_str):
    d = datetime.strptime(today_str, "%Y-%m-%d")
    today_display = f"{d.year}年{d.month}月{d.day}日"

    vocab_js   = json.dumps({str(w["id"]): w for w in vocab}, ensure_ascii=False)
    pools_js   = json.dumps(today_pools, ensure_ascii=False)
    streaks_js = json.dumps(streaks, ensure_ascii=False)
    stats_js   = json.dumps(progress_stats, ensure_ascii=False)
    subjects_js = json.dumps(subjects, ensure_ascii=False)
    config_js  = json.dumps(SUBJECT_CONFIG, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>語句学習</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --accent: #4f46e5; --accent-light: #eef2ff;
      --text: #1a202c; --text-sub: #718096;
      --border: #e2e8f0; --bg: #f7f8fc; --radius: 14px;
    }}
    body {{ font-family: -apple-system,'Hiragino Sans','Yu Gothic UI',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}

    /* Header */
    .header {{ background:linear-gradient(135deg,var(--accent) 0%,#6d28d9 100%); color:white; padding:14px 14px 0; transition:background .3s; }}
    .header-row {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
    .app-title {{ font-size:17px; font-weight:700; }}
    .date-text  {{ font-size:11px; opacity:.85; margin-top:2px; }}
    .streak-box {{ text-align:center; background:rgba(255,255,255,.2); border-radius:10px; padding:5px 11px; }}
    .streak-num {{ font-size:20px; font-weight:800; }}
    .streak-label {{ font-size:10px; opacity:.9; }}

    /* Subject tabs */
    .subject-tabs {{ display:flex; gap:5px; margin-bottom:10px; overflow-x:auto; }}
    .subject-tabs::-webkit-scrollbar {{ display:none; }}
    .subject-tab {{ flex-shrink:0; background:rgba(255,255,255,.2); border:none; color:rgba(255,255,255,.75); font-size:13px; font-weight:600; padding:6px 13px; border-radius:20px; cursor:pointer; transition:all .18s; }}
    .subject-tab.active {{ background:white; color:var(--accent); }}

    /* Progress */
    .progress-row {{ display:flex; align-items:center; gap:8px; margin-bottom:10px; }}
    .progress-bar  {{ flex:1; background:rgba(255,255,255,.3); border-radius:6px; height:6px; overflow:hidden; }}
    .progress-fill {{ background:white; height:100%; border-radius:6px; transition:width .4s; }}
    .progress-text {{ font-size:11px; opacity:.9; white-space:nowrap; }}

    /* View tabs */
    .view-tabs {{ display:flex; gap:2px; }}
    .view-tab {{ flex:1; background:transparent; border:none; color:rgba(255,255,255,.65); font-size:13px; font-weight:600; padding:9px 2px; cursor:pointer; position:relative; transition:color .18s; }}
    .view-tab.active {{ color:white; }}
    .view-tab.active::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:3px; background:white; border-radius:3px 3px 0 0; }}
    .badge {{ display:inline-flex; align-items:center; justify-content:center; background:#f59e0b; color:white; font-size:10px; font-weight:700; border-radius:10px; min-width:16px; height:16px; padding:0 4px; margin-left:3px; vertical-align:middle; }}

    /* Views */
    .view {{ display:none; padding:13px; }}
    .view.active {{ display:block; }}

    /* Study cards */
    .card {{ background:white; border-radius:var(--radius); padding:16px 18px; margin-bottom:11px; box-shadow:0 1px 4px rgba(0,0,0,.06); border:1.5px solid transparent; animation:slideIn .28s ease both; }}
    .card.marked {{ border-color:#f59e0b; background:#fffbeb; }}
    @keyframes slideIn {{ from{{opacity:0;transform:translateY(8px)}} to{{opacity:1;transform:translateY(0)}} }}
    @keyframes fadeOut {{ from{{opacity:1;transform:translateY(0)}} to{{opacity:0;transform:translateY(-8px)}} }}
    .card-header {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:9px; }}
    .word-block {{ flex:1; }}
    .word {{ font-size:26px; font-weight:800; }}
    .reading {{ font-size:12px; color:var(--text-sub); margin-top:3px; }}
    .cat-tag {{ display:inline-block; margin-top:4px; font-size:10px; font-weight:700; color:var(--accent); background:var(--accent-light); padding:2px 7px; border-radius:20px; }}
    .review-btn {{ flex-shrink:0; background:none; border:1.5px solid var(--border); border-radius:8px; padding:5px 9px; font-size:11px; font-weight:600; color:var(--text-sub); cursor:pointer; transition:all .18s; }}
    .review-btn:hover {{ border-color:#f59e0b; color:#f59e0b; }}
    .review-btn.marked {{ background:#f59e0b; border-color:#f59e0b; color:white; }}
    .meaning {{ font-size:14px; font-weight:600; background:#f7f8fc; border-radius:8px; padding:8px 11px; margin-bottom:9px; line-height:1.6; }}
    .card.marked .meaning {{ background:rgba(255,255,255,.7); }}
    .ex-label {{ font-size:10px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; }}
    .example {{ font-size:13px; color:#4a5568; line-height:1.7; }}
    .example-ja {{ color:#718096; font-style:italic; margin-top:2px; font-size:12px; }}
    .num-tag {{ font-size:10px; color:#a0aec0; margin-bottom:4px; }}

    /* Next batch */
    .next-wrap {{ text-align:center; padding:6px 0 18px; }}
    .next-btn {{ background:white; border:1.5px solid var(--accent); color:var(--accent); font-size:13px; font-weight:700; padding:10px 24px; border-radius:30px; cursor:pointer; transition:all .18s; }}
    .next-btn:hover {{ background:var(--accent); color:white; }}
    .next-btn:disabled {{ border-color:var(--border); color:var(--text-sub); cursor:default; }}
    .next-btn:disabled:hover {{ background:white; color:var(--text-sub); }}
    .pool-status {{ text-align:center; font-size:11px; color:var(--text-sub); margin-top:8px; }}

    /* Review list */
    .review-count {{ font-size:12px; font-weight:600; color:var(--text-sub); margin-bottom:12px; }}
    .review-empty {{ text-align:center; padding:50px 20px; color:var(--text-sub); }}
    .review-empty .icon {{ font-size:42px; margin-bottom:10px; }}
    .review-empty p {{ font-size:14px; line-height:1.7; }}
    .rcard {{ background:white; border-radius:var(--radius); padding:14px 16px; margin-bottom:11px; border-left:4px solid var(--accent); box-shadow:0 1px 4px rgba(0,0,0,.06); animation:slideIn .28s ease both; }}
    .rcard-header {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:7px; }}
    .rcard-word {{ font-size:20px; font-weight:800; }}
    .rcard-reading {{ font-size:11px; color:var(--text-sub); margin-top:2px; }}
    .done-btn {{ flex-shrink:0; background:white; border:1.5px solid #22c55e; color:#22c55e; font-size:11px; font-weight:700; padding:5px 10px; border-radius:8px; cursor:pointer; transition:all .18s; }}
    .done-btn:hover {{ background:#22c55e; color:white; }}
    .rcard-meaning {{ font-size:13px; font-weight:600; margin-bottom:7px; line-height:1.6; }}
    .rcard-example {{ font-size:12px; color:#4a5568; line-height:1.7; }}
    .rcard-exja {{ color:#718096; font-style:italic; margin-top:2px; }}
    .rcard-tag {{ display:inline-block; margin-top:7px; font-size:10px; font-weight:700; color:var(--accent); background:var(--accent-light); padding:2px 7px; border-radius:10px; }}

    /* ── Quiz mode ────────────────────────────────── */
    .quiz-setup {{ background:white; border-radius:var(--radius); padding:20px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
    .quiz-setup h3 {{ font-size:15px; font-weight:700; margin-bottom:14px; }}
    .range-row {{ display:flex; align-items:center; gap:8px; margin-bottom:14px; flex-wrap:wrap; }}
    .range-input {{ width:80px; border:1.5px solid var(--border); border-radius:8px; padding:8px 10px; font-size:15px; font-weight:700; text-align:center; }}
    .range-sep {{ color:var(--text-sub); font-weight:600; }}
    .start-btn {{ flex:1; background:var(--accent); color:white; border:none; border-radius:10px; padding:10px; font-size:14px; font-weight:700; cursor:pointer; min-width:100px; }}
    .quiz-hint {{ font-size:12px; color:var(--text-sub); line-height:1.6; }}

    /* Flashcard */
    .quiz-area {{ display:none; }}
    .quiz-progress-row {{ display:flex; align-items:center; gap:8px; margin-bottom:14px; }}
    .quiz-bar {{ flex:1; background:var(--border); border-radius:6px; height:6px; overflow:hidden; }}
    .quiz-bar-fill {{ background:var(--accent); height:100%; border-radius:6px; transition:width .3s; }}
    .quiz-count {{ font-size:12px; color:var(--text-sub); white-space:nowrap; }}

    .flashcard {{ background:white; border-radius:var(--radius); padding:24px 20px; box-shadow:0 2px 10px rgba(0,0,0,.08); margin-bottom:14px; min-height:200px; cursor:pointer; user-select:none; border:2px solid var(--border); transition:border-color .2s; }}
    .flashcard:active {{ border-color:var(--accent); }}
    .fc-front {{ text-align:center; }}
    .fc-word {{ font-size:32px; font-weight:800; margin-bottom:6px; }}
    .fc-reading {{ font-size:14px; color:var(--text-sub); margin-bottom:16px; }}
    .fc-tap-hint {{ font-size:12px; color:#a0aec0; margin-top:20px; }}
    .fc-back {{ display:none; }}
    .fc-divider {{ border:none; border-top:1.5px solid var(--border); margin:12px 0; }}
    .fc-meaning {{ font-size:15px; font-weight:700; color:var(--text); margin-bottom:10px; line-height:1.6; }}
    .fc-example {{ font-size:13px; color:#4a5568; line-height:1.7; }}
    .fc-exja {{ color:#718096; font-style:italic; font-size:12px; margin-top:3px; }}

    .quiz-btns {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px; }}
    .q-btn {{ border:none; border-radius:12px; padding:14px; font-size:14px; font-weight:700; cursor:pointer; transition:opacity .18s; }}
    .q-btn:active {{ opacity:.8; }}
    .q-btn.retry {{ background:#fef3c7; color:#d97706; }}
    .q-btn.ok    {{ background:#dcfce7; color:#16a34a; }}
    .quiz-skip {{ text-align:center; }}
    .skip-btn {{ background:none; border:none; color:#a0aec0; font-size:12px; cursor:pointer; padding:4px 8px; }}

    /* Results */
    .quiz-result {{ display:none; background:white; border-radius:var(--radius); padding:28px 20px; text-align:center; box-shadow:0 2px 10px rgba(0,0,0,.08); }}
    .result-emoji {{ font-size:52px; margin-bottom:10px; }}
    .result-title {{ font-size:18px; font-weight:800; margin-bottom:18px; }}
    .result-stats {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:20px; }}
    .result-stat {{ border-radius:10px; padding:12px; }}
    .result-stat.ok {{ background:#dcfce7; color:#16a34a; }}
    .result-stat.retry {{ background:#fef3c7; color:#d97706; }}
    .result-stat .stat-num {{ font-size:28px; font-weight:800; }}
    .result-stat .stat-label {{ font-size:11px; font-weight:600; }}
    .result-btns {{ display:flex; gap:10px; }}
    .result-btn {{ flex:1; border:none; border-radius:10px; padding:12px; font-size:13px; font-weight:700; cursor:pointer; }}
    .result-btn.again {{ background:var(--accent); color:white; }}
    .result-btn.add-review {{ background:#fef3c7; color:#d97706; }}

    .footer {{ text-align:center; font-size:12px; color:var(--text-sub); padding:8px 0 22px; }}
  </style>
</head>
<body>

<div class="header" id="header">
  <div class="header-row">
    <div>
      <div class="app-title">語句学習</div>
      <div class="date-text">{today_display}</div>
    </div>
    <div class="streak-box">
      <div class="streak-num" id="streak-num">0</div>
      <div class="streak-label">日連続</div>
    </div>
  </div>
  <div class="subject-tabs" id="subject-tabs"></div>
  <div class="progress-row">
    <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
    <div class="progress-text" id="progress-text"></div>
  </div>
  <div class="view-tabs">
    <button class="view-tab active" onclick="switchView('today')">今日の語句</button>
    <button class="view-tab" onclick="switchView('review')" id="review-tab">
      復習リスト<span class="badge" id="badge" style="display:none">0</span>
    </button>
    <button class="view-tab" onclick="switchView('quiz')">📝 テスト</button>
  </div>
</div>

<!-- 今日の語句 -->
<div id="today-view" class="view active">
  <div id="cards"></div>
  <div class="pool-status" id="pool-status"></div>
  <div class="next-wrap"><button class="next-btn" id="next-btn" onclick="showNextBatch()">次の語句を見る →</button></div>
  <div class="footer">毎日の積み重ねが力になる 💪</div>
</div>

<!-- 復習リスト -->
<div id="review-view" class="view">
  <div id="review-container"></div>
</div>

<!-- テストモード -->
<div id="quiz-view" class="view">
  <div class="quiz-setup" id="quiz-setup">
    <h3>📝 範囲テスト</h3>
    <div class="range-row">
      <input class="range-input" id="q-start" type="number" placeholder="400" min="1">
      <span class="range-sep">〜</span>
      <input class="range-input" id="q-end" type="number" placeholder="500" min="1">
      <button class="start-btn" onclick="startQuiz()">テスト開始</button>
    </div>
    <div class="quiz-hint">
      単語帳の番号で範囲を指定します。<br>
      URLに <code>?quiz=400-500</code> をつけると自動でテスト開始します。
    </div>
  </div>

  <div class="quiz-area" id="quiz-area">
    <div class="quiz-progress-row">
      <div class="quiz-bar"><div class="quiz-bar-fill" id="q-bar-fill"></div></div>
      <div class="quiz-count" id="q-count"></div>
    </div>
    <div class="flashcard" id="flashcard" onclick="flipCard()">
      <div class="fc-front" id="fc-front">
        <div class="fc-word" id="fc-word"></div>
        <div class="fc-reading" id="fc-reading"></div>
        <div class="fc-tap-hint">タップして意味を確認</div>
      </div>
      <div class="fc-back" id="fc-back">
        <div class="fc-word" id="fc-word2"></div>
        <div class="fc-reading" id="fc-reading2"></div>
        <hr class="fc-divider">
        <div class="fc-meaning" id="fc-meaning"></div>
        <div class="fc-example" id="fc-example"></div>
        <div class="fc-exja" id="fc-exja"></div>
      </div>
    </div>
    <div class="quiz-btns" id="quiz-btns" style="display:none">
      <button class="q-btn retry" onclick="answerQuiz(false)">🔄 もう一度</button>
      <button class="q-btn ok"    onclick="answerQuiz(true)">✓ 知ってた</button>
    </div>
    <div class="quiz-skip">
      <button class="skip-btn" onclick="skipCard()">スキップ →</button>
    </div>
  </div>

  <div class="quiz-result" id="quiz-result">
    <div class="result-emoji" id="result-emoji"></div>
    <div class="result-title" id="result-title"></div>
    <div class="result-stats">
      <div class="result-stat ok">
        <div class="stat-num" id="r-ok">0</div>
        <div class="stat-label">✓ 知ってた</div>
      </div>
      <div class="result-stat retry">
        <div class="stat-num" id="r-retry">0</div>
        <div class="stat-label">🔄 もう一度</div>
      </div>
    </div>
    <div class="result-btns">
      <button class="result-btn again" onclick="restartQuiz()">もう一度</button>
      <button class="result-btn add-review" onclick="addRetryToReview()">「もう一度」を復習リストへ</button>
    </div>
  </div>
</div>

<script>
// ── Embedded data ─────────────────────────────────────────────
const ALL_VOCAB   = {vocab_js};
const TODAY_POOLS = {pools_js};
const STREAKS     = {streaks_js};
const STATS       = {stats_js};
const SUBJECTS    = {subjects_js};
const SUBJECT_CFG = {config_js};
const TODAY_DATE  = '{today_str}';
const BATCH_SIZE  = {BATCH_SIZE};
const DEFAULT_CFG = {{color:"#6b7280",light:"#f9fafb",emoji:"📚",unlimited:false}};

// ── Helpers ───────────────────────────────────────────────────
let currentSubject = localStorage.getItem('jr_subject') || SUBJECTS[0];
if (!SUBJECTS.includes(currentSubject)) currentSubject = SUBJECTS[0];

const cfg = s => SUBJECT_CFG[s] || DEFAULT_CFG;
const reviewKey = s => `jr_review_${{s}}_v1`;
const shownKey  = s => `jr_shown_${{s}}_v1`;
const dateKey   = s => `jr_date_${{s}}_v1`;

function getReview(s) {{ return new Set(JSON.parse(localStorage.getItem(reviewKey(s))||'[]')); }}
function saveReview(s,set) {{ localStorage.setItem(reviewKey(s),JSON.stringify([...set])); }}
function getShown(s) {{
  if (localStorage.getItem(dateKey(s)) !== TODAY_DATE) {{
    localStorage.setItem(dateKey(s), TODAY_DATE);
    localStorage.setItem(shownKey(s), '0');
    return 0;
  }}
  return parseInt(localStorage.getItem(shownKey(s))||'0');
}}
function setShown(s,n) {{ localStorage.setItem(shownKey(s),String(n)); }}

// ── Theme ─────────────────────────────────────────────────────
function applyTheme(s) {{
  const c = cfg(s);
  document.documentElement.style.setProperty('--accent', c.color);
  document.documentElement.style.setProperty('--accent-light', c.light);
  document.getElementById('header').style.background =
    `linear-gradient(135deg,${{c.color}} 0%,${{shade(c.color,-30)}} 100%)`;
}}
function shade(hex, p) {{
  const n=parseInt(hex.replace('#',''),16);
  return '#'+[n>>16,(n>>8)&0xFF,n&0xFF]
    .map(x=>Math.min(255,Math.max(0,x+p)).toString(16).padStart(2,'0')).join('');
}}

// ── Subject tabs ──────────────────────────────────────────────
function buildSubjectTabs() {{
  const c = document.getElementById('subject-tabs');
  SUBJECTS.forEach(s => {{
    const b = document.createElement('button');
    b.className = 'subject-tab'+(s===currentSubject?' active':'');
    b.textContent = (cfg(s).emoji||'')+ ' ' +s;
    b.onclick = ()=>switchSubject(s);
    c.appendChild(b);
  }});
}}
function switchSubject(s) {{
  currentSubject = s;
  localStorage.setItem('jr_subject',s);
  document.querySelectorAll('.subject-tab').forEach((b,i)=>b.classList.toggle('active',SUBJECTS[i]===s));
  applyTheme(s);
  updateHeader();
  document.getElementById('cards').innerHTML='';
  shownCount = getShown(s);
  if (shownCount>0) {{
    (TODAY_POOLS[s]||[]).slice(0,shownCount).forEach(id=>{{
      const card=makeCard(id,s); if(card){{card.style.animation='none';document.getElementById('cards').appendChild(card);}}}});
  }} else {{ showNextBatch(); }}
  updatePoolStatus();
  updateBadge();
  if (document.getElementById('review-view').classList.contains('active')) renderReview();
}}

// ── Header ────────────────────────────────────────────────────
function updateHeader() {{
  const s=currentSubject;
  document.getElementById('streak-num').textContent = STREAKS[s]||0;
  const st=STATS[s]||{{introduced:0,total:1}};
  const pct=Math.round(st.introduced/st.total*100);
  document.getElementById('progress-fill').style.width=pct+'%';
  document.getElementById('progress-text').textContent=`${{st.introduced}}/${{st.total}}語 (${{pct}}%)`;
}}

// ── View tabs ─────────────────────────────────────────────────
function switchView(v) {{
  document.querySelectorAll('.view-tab').forEach((b,i)=>b.classList.toggle('active',['today','review','quiz'][i]===v));
  ['today','review','quiz'].forEach(n=>document.getElementById(n+'-view').classList.toggle('active',n===v));
  if (v==='review') renderReview();
  if (v==='quiz') initQuizView();
}}
function updateBadge() {{
  const n=getReview(currentSubject).size;
  const badge=document.getElementById('badge');
  badge.textContent=n; badge.style.display=n>0?'inline-flex':'none';
}}

// ── Study cards ───────────────────────────────────────────────
function makeCard(id,subj) {{
  const w=ALL_VOCAB[String(id)]; if(!w) return null;
  const rev=getReview(subj), marked=rev.has(id);
  const el=document.createElement('div');
  el.className='card'+(marked?' marked':''); el.id='card-'+id;
  const numTag = w.number ? `<div class="num-tag">#${{w.number}}</div>` : '';
  const exJa = w.example_ja ? `<div class="example-ja">${{w.example_ja}}</div>` : '';
  el.innerHTML=`
    ${{numTag}}
    <div class="card-header">
      <div class="word-block">
        <div class="word">${{w.word}}</div>
        <div class="reading">${{w.reading||''}}</div>
        <div class="cat-tag">${{w.category||''}}</div>
      </div>
      <button class="review-btn ${{marked?'marked':''}}" id="rbtn-${{id}}" onclick="toggleReview(${{id}})">
        ${{marked?'📌 復習中':'＋ 要復習'}}
      </button>
    </div>
    <div class="meaning">${{w.meaning}}</div>
    <div class="ex-label">使用例</div>
    <div class="example">${{w.example}}${{exJa}}</div>`;
  return el;
}}
function toggleReview(id) {{
  const s=currentSubject, rev=getReview(s);
  const btn=document.getElementById('rbtn-'+id), card=document.getElementById('card-'+id);
  if(rev.has(id)){{rev.delete(id);btn.className='review-btn';btn.textContent='＋ 要復習';card.classList.remove('marked');}}
  else{{rev.add(id);btn.className='review-btn marked';btn.textContent='📌 復習中';card.classList.add('marked');}}
  saveReview(s,rev); updateBadge();
}}

// ── Batch display ─────────────────────────────────────────────
let shownCount=0;
function showNextBatch() {{
  const s=currentSubject, pool=TODAY_POOLS[s]||[];
  const batch=pool.slice(shownCount,shownCount+BATCH_SIZE);
  if(!batch.length) return;
  const con=document.getElementById('cards');
  batch.forEach((id,i)=>{{const card=makeCard(id,s);if(card){{card.style.animationDelay=(i*.07)+'s';con.appendChild(card);}}}});
  shownCount+=batch.length; setShown(s,shownCount); updatePoolStatus();
}}
function updatePoolStatus() {{
  const s=currentSubject, pool=TODAY_POOLS[s]||[];
  const rem=pool.length-shownCount;
  const statusEl=document.getElementById('pool-status');
  const btn=document.getElementById('next-btn');
  if(shownCount>0) statusEl.textContent=`${{shownCount}} / ${{pool.length}} 語 表示済み`;
  if(rem<=0){{btn.disabled=true;btn.textContent='すべて表示しました';
    if(pool.length>0) statusEl.textContent=`${{pool.length}} / ${{pool.length}} 語 — お疲れさま！`;
  }}else{{btn.disabled=false;btn.textContent=`次の語句を見る (${{Math.min(BATCH_SIZE,rem)}}語) →`;}}
}}

// ── Review list ───────────────────────────────────────────────
function renderReview() {{
  const s=currentSubject, con=document.getElementById('review-container');
  con.innerHTML='';
  const rev=getReview(s);
  if(!rev.size){{con.innerHTML=`<div class="review-empty"><div class="icon">📖</div><p>復習リストはまだ空です。<br>語句カードの「＋ 要復習」ボタンで追加しよう！</p></div>`;return;}}
  const cnt=document.createElement('div');cnt.className='review-count';cnt.textContent=`復習リスト: ${{rev.size}} 語`;con.appendChild(cnt);
  rev.forEach(id=>{{
    const w=ALL_VOCAB[String(id)];if(!w)return;
    const exJa=w.example_ja?`<div class="rcard-exja">${{w.example_ja}}</div>`:'';
    const el=document.createElement('div');el.className='rcard';el.id='rcard-'+id;
    el.style.borderColor=cfg(s).color;
    el.innerHTML=`<div class="rcard-header"><div><div class="rcard-word">${{w.word}}</div><div class="rcard-reading">${{w.reading||''}}</div></div>
      <button class="done-btn" onclick="markDone(${{id}})">覚えた ✓</button></div>
      <div class="rcard-meaning">${{w.meaning}}</div>
      <div class="rcard-example">${{w.example}}${{exJa}}</div>
      <div class="rcard-tag">${{w.category||''}}</div>`;
    con.appendChild(el);
  }});
}}
function markDone(id) {{
  const el=document.getElementById('rcard-'+id);
  el.style.animation='fadeOut .28s ease forwards';
  setTimeout(()=>{{
    const s=currentSubject,rev=getReview(s);rev.delete(id);saveReview(s,rev);updateBadge();
    const btn=document.getElementById('rbtn-'+id),card=document.getElementById('card-'+id);
    if(btn){{btn.className='review-btn';btn.textContent='＋ 要復習';}}
    if(card)card.classList.remove('marked');
    renderReview();
  }},260);
}}

// ── Quiz mode ─────────────────────────────────────────────────
let quizWords=[], quizIdx=0, quizOk=0, quizRetry=[], quizFlipped=false;
let quizStartRange=[null,null];

function initQuizView() {{
  // URLパラメータ ?quiz=400-500 の自動処理
  const params=new URLSearchParams(location.search);
  const qp=params.get('quiz');
  if(qp && !document.getElementById('quiz-area').style.display.includes('block')) {{
    const parts=qp.split('-');
    if(parts.length===2){{
      document.getElementById('q-start').value=parts[0];
      document.getElementById('q-end').value=parts[1];
      startQuiz();
    }}
  }}
}}

function getQuizWords(start,end) {{
  return Object.values(ALL_VOCAB).filter(w=>{{
    const n=w.number; return n!=null && n>=start && n<=end;
  }}).sort((a,b)=>a.number-b.number);
}}

function startQuiz() {{
  const s=parseInt(document.getElementById('q-start').value);
  const e=parseInt(document.getElementById('q-end').value);
  if(!s||!e||s>e){{alert('番号を正しく入力してください');return;}}
  quizWords=getQuizWords(s,e);
  if(!quizWords.length){{alert(`#${{s}}〜#${{e}} の範囲に単語が見つかりません`);return;}}
  quizStartRange=[s,e];
  quizIdx=0;quizOk=0;quizRetry=[];
  document.getElementById('quiz-setup').style.display='none';
  document.getElementById('quiz-result').style.display='none';
  document.getElementById('quiz-area').style.display='block';
  showQuizCard();
}}

function showQuizCard() {{
  if(quizIdx>=quizWords.length){{showQuizResult();return;}}
  const w=quizWords[quizIdx];
  quizFlipped=false;
  document.getElementById('fc-front').style.display='block';
  document.getElementById('fc-back').style.display='none';
  document.getElementById('quiz-btns').style.display='none';
  document.getElementById('fc-word').textContent=w.word;
  document.getElementById('fc-reading').textContent=w.reading||'';
  document.getElementById('fc-word2').textContent=w.word;
  document.getElementById('fc-reading2').textContent=w.reading||'';
  document.getElementById('fc-meaning').textContent=w.meaning;
  document.getElementById('fc-example').textContent=w.example||'';
  document.getElementById('fc-exja').textContent=w.example_ja||'';
  const pct=Math.round(quizIdx/quizWords.length*100);
  document.getElementById('q-bar-fill').style.width=pct+'%';
  document.getElementById('q-count').textContent=`${{quizIdx+1}} / ${{quizWords.length}}`;
}}

function flipCard() {{
  if(quizFlipped)return;
  quizFlipped=true;
  document.getElementById('fc-front').style.display='none';
  document.getElementById('fc-back').style.display='block';
  document.getElementById('quiz-btns').style.display='grid';
}}

function answerQuiz(known) {{
  if(known){{quizOk++;}}
  else{{quizRetry.push(quizWords[quizIdx].id);}}
  quizIdx++; showQuizCard();
}}

function skipCard() {{
  quizRetry.push(quizWords[quizIdx].id);
  quizIdx++; showQuizCard();
}}

function showQuizResult() {{
  document.getElementById('quiz-area').style.display='none';
  const res=document.getElementById('quiz-result');
  res.style.display='block';
  const pct=Math.round(quizOk/quizWords.length*100);
  document.getElementById('r-ok').textContent=quizOk;
  document.getElementById('r-retry').textContent=quizRetry.length;
  document.getElementById('result-emoji').textContent=pct>=80?'🎉':pct>=50?'💪':'📚';
  document.getElementById('result-title').textContent=
    pct>=80?`すごい！正解率 ${{pct}}%`:`正解率 ${{pct}}% — もう一度チャレンジ！`;
}}

function restartQuiz() {{
  document.getElementById('quiz-result').style.display='none';
  quizIdx=0;quizOk=0;quizRetry=[];
  document.getElementById('quiz-area').style.display='block';
  showQuizCard();
}}

function addRetryToReview() {{
  const s=currentSubject, rev=getReview(s);
  quizRetry.forEach(id=>rev.add(id));
  saveReview(s,rev); updateBadge();
  alert(`${{quizRetry.length}}語を復習リストに追加しました！`);
  quizRetry=[];
  document.getElementById('r-retry').textContent=0;
}}

// ── Init ──────────────────────────────────────────────────────
buildSubjectTabs();
applyTheme(currentSubject);
updateHeader();
shownCount=getShown(currentSubject);
if(shownCount>0){{
  (TODAY_POOLS[currentSubject]||[]).slice(0,shownCount).forEach(id=>{{
    const card=makeCard(id,currentSubject);if(card){{card.style.animation='none';document.getElementById('cards').appendChild(card);}}}});
  updatePoolStatus();
}}else{{showNextBatch();}}
updateBadge();

// URLパラメータで直接テストモードに
const _p=new URLSearchParams(location.search);
if(_p.get('quiz')){{switchView('quiz');}}
</script>
</body>
</html>"""


def main():
    today_str = date.today().isoformat()
    vocab = load_json(VOCAB_FILE, [])
    if not vocab:
        print("vocab.json が空です。"); return

    progress = load_json(PROGRESS_FILE, {"subjects": {}})
    if "subjects" not in progress:
        progress["subjects"] = {}

    subjects_in_vocab = sorted(
        {w["subject"] for w in vocab if "subject" in w},
        key=lambda s: SUBJECT_ORDER.index(s) if s in SUBJECT_ORDER else 99
    )

    today_pools, streaks, progress_stats = {}, {}, {}
    for subj in subjects_in_vocab:
        if subj not in progress["subjects"]:
            progress["subjects"][subj] = {"history": []}
        subj_vocab   = [w for w in vocab if w.get("subject") == subj]
        subj_history = progress["subjects"][subj].setdefault("history", [])
        unlimited    = SUBJECT_CONFIG.get(subj, {}).get("unlimited", False)
        pool = get_today_pool(subj_vocab, subj_history, today_str, unlimited)
        today_pools[subj]    = pool
        streaks[subj]        = calculate_streak(subj_history)
        introduced = {wid for h in subj_history for wid in h.get("pool", [])}
        progress_stats[subj] = {"introduced": len(introduced), "total": len(subj_vocab)}

    save_json(PROGRESS_FILE, progress)
    html = generate_html(vocab, today_pools, streaks, progress_stats, subjects_in_vocab, today_str)
    HTML_FILE.write_text(html, encoding="utf-8")

    if NO_BROWSER:
        print(f"生成完了: {HTML_FILE}")
    else:
        webbrowser.open(HTML_FILE.as_uri())
        print(f"本日の語句ページを開きました: {HTML_FILE}")
    for s in subjects_in_vocab:
        st=progress_stats[s]
        mode = "（全件）" if SUBJECT_CONFIG.get(s,{}).get("unlimited") else ""
        print(f"  [{s}]{mode} 連続{streaks[s]}日 プール{len(today_pools[s])}語 紹介済み{st['introduced']}/{st['total']}語")


if __name__ == "__main__":
    main()
