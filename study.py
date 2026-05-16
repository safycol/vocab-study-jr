#!/usr/bin/env python3
"""Daily vocabulary study — middle school multi-subject version."""

import json
import os
import random
import sys
import webbrowser
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
VOCAB_FILE  = SCRIPT_DIR / "vocab.json"
PROGRESS_FILE = SCRIPT_DIR / "progress.json"
HTML_FILE   = SCRIPT_DIR / "index.html"

BATCH_SIZE = 4
DAILY_POOL_SIZE = 20
NO_BROWSER = "--no-browser" in sys.argv or os.environ.get("CI") == "true"

# 科目の表示順・カラー設定
SUBJECT_CONFIG = {
    "英語": {"emoji": "🇬🇧", "color": "#4f46e5", "light": "#eef2ff"},
    "国語": {"emoji": "📖", "color": "#dc2626", "light": "#fef2f2"},
    "社会": {"emoji": "🌍", "color": "#16a34a", "light": "#f0fdf4"},
    "理科": {"emoji": "🔬", "color": "#d97706", "light": "#fffbeb"},
    "数学": {"emoji": "📐", "color": "#7c3aed", "light": "#f5f3ff"},
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


def get_today_pool(vocab_for_subject, subject_history, today_str):
    existing = next((h for h in subject_history if h["date"] == today_str), None)
    if existing:
        return existing["pool"]

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

    vocab_js        = json.dumps({str(w["id"]): w for w in vocab}, ensure_ascii=False)
    pools_js        = json.dumps(today_pools, ensure_ascii=False)
    streaks_js      = json.dumps(streaks, ensure_ascii=False)
    stats_js        = json.dumps(progress_stats, ensure_ascii=False)
    subjects_js     = json.dumps(subjects, ensure_ascii=False)
    config_js       = json.dumps(SUBJECT_CONFIG, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>語句学習</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --accent:       #4f46e5;
      --accent-light: #eef2ff;
      --text:         #1a202c;
      --text-sub:     #718096;
      --border:       #e2e8f0;
      --bg:           #f7f8fc;
      --radius:       14px;
    }}
    body {{
      font-family: -apple-system, 'Hiragino Sans', 'Yu Gothic UI', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}

    /* ── Header ─── */
    .header {{
      background: linear-gradient(135deg, var(--accent) 0%, #6d28d9 100%);
      color: white;
      padding: 16px 16px 0;
      transition: background 0.3s;
    }}
    .header-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .app-title {{ font-size: 17px; font-weight: 700; }}
    .date-text  {{ font-size: 12px; opacity: 0.85; margin-top: 2px; }}
    .streak-box {{
      text-align: center;
      background: rgba(255,255,255,0.2);
      border-radius: 10px;
      padding: 6px 12px;
    }}
    .streak-num   {{ font-size: 20px; font-weight: 800; }}
    .streak-label {{ font-size: 10px; opacity: 0.9; }}

    /* ── Subject tabs ─── */
    .subject-tabs {{
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}
    .subject-tabs::-webkit-scrollbar {{ display: none; }}
    .subject-tab {{
      flex-shrink: 0;
      background: rgba(255,255,255,0.2);
      border: none;
      color: rgba(255,255,255,0.75);
      font-size: 13px;
      font-weight: 600;
      padding: 7px 14px;
      border-radius: 20px;
      cursor: pointer;
      transition: all 0.18s;
    }}
    .subject-tab.active {{
      background: white;
      color: var(--accent);
    }}

    /* ── Progress ─── */
    .progress-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .progress-bar  {{ flex: 1; background: rgba(255,255,255,0.3); border-radius: 6px; height: 6px; overflow: hidden; }}
    .progress-fill {{ background: white; height: 100%; border-radius: 6px; transition: width 0.4s; }}
    .progress-text {{ font-size: 12px; opacity: 0.9; white-space: nowrap; }}

    /* ── View tabs ─── */
    .view-tabs {{ display: flex; gap: 4px; }}
    .view-tab {{
      flex: 1;
      background: transparent;
      border: none;
      color: rgba(255,255,255,0.65);
      font-size: 14px;
      font-weight: 600;
      padding: 10px 4px;
      cursor: pointer;
      position: relative;
      transition: color 0.18s;
    }}
    .view-tab.active {{ color: white; }}
    .view-tab.active::after {{
      content: '';
      position: absolute;
      bottom: 0; left: 0; right: 0;
      height: 3px;
      background: white;
      border-radius: 3px 3px 0 0;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: #f59e0b;
      color: white;
      font-size: 10px;
      font-weight: 700;
      border-radius: 10px;
      min-width: 17px;
      height: 17px;
      padding: 0 4px;
      margin-left: 4px;
      vertical-align: middle;
    }}

    /* ── Views ─── */
    .view {{ display: none; padding: 14px; }}
    .view.active {{ display: block; }}

    /* ── Cards ─── */
    .card {{
      background: white;
      border-radius: var(--radius);
      padding: 18px 20px;
      margin-bottom: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      border: 1.5px solid transparent;
      animation: slideIn 0.28s ease both;
    }}
    .card.marked {{ border-color: #f59e0b; background: #fffbeb; }}
    @keyframes slideIn {{
      from {{ opacity: 0; transform: translateY(8px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes fadeOut {{
      from {{ opacity: 1; transform: translateY(0); }}
      to   {{ opacity: 0; transform: translateY(-8px); }}
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .word-block {{ flex: 1; }}
    .word     {{ font-size: 26px; font-weight: 800; }}
    .reading  {{ font-size: 13px; color: var(--text-sub); margin-top: 3px; font-family: monospace; }}
    .cat-tag  {{
      display: inline-block;
      margin-top: 5px;
      font-size: 10px;
      font-weight: 700;
      color: var(--accent);
      background: var(--accent-light);
      padding: 2px 8px;
      border-radius: 20px;
    }}
    .review-btn {{
      flex-shrink: 0;
      background: none;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-sub);
      cursor: pointer;
      transition: all 0.18s;
    }}
    .review-btn:hover {{ border-color: #f59e0b; color: #f59e0b; }}
    .review-btn.marked {{ background: #f59e0b; border-color: #f59e0b; color: white; }}
    .meaning {{
      font-size: 15px;
      font-weight: 600;
      background: #f7f8fc;
      border-radius: 8px;
      padding: 9px 12px;
      margin-bottom: 10px;
      line-height: 1.6;
    }}
    .card.marked .meaning {{ background: rgba(255,255,255,0.7); }}
    .ex-label {{ font-size: 10px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }}
    .example  {{ font-size: 13px; color: #4a5568; line-height: 1.7; }}
    .example-ja {{ color: #718096; font-style: italic; margin-top: 3px; font-size: 12px; }}

    /* ── Next batch ─── */
    .next-wrap {{ text-align: center; padding: 6px 0 20px; }}
    .next-btn {{
      background: white;
      border: 1.5px solid var(--accent);
      color: var(--accent);
      font-size: 14px;
      font-weight: 700;
      padding: 11px 26px;
      border-radius: 30px;
      cursor: pointer;
      transition: all 0.18s;
    }}
    .next-btn:hover {{ background: var(--accent); color: white; }}
    .next-btn:disabled {{ border-color: var(--border); color: var(--text-sub); cursor: default; }}
    .next-btn:disabled:hover {{ background: white; color: var(--text-sub); }}
    .pool-status {{ text-align: center; font-size: 12px; color: var(--text-sub); margin-top: 10px; }}

    /* ── Review list ─── */
    .review-count {{ font-size: 12px; font-weight: 600; color: var(--text-sub); margin-bottom: 14px; }}
    .review-empty {{ text-align: center; padding: 50px 20px; color: var(--text-sub); }}
    .review-empty .icon {{ font-size: 44px; margin-bottom: 10px; }}
    .review-empty p {{ font-size: 14px; line-height: 1.7; }}
    .rcard {{
      background: white;
      border-radius: var(--radius);
      padding: 16px 18px;
      margin-bottom: 12px;
      border-left: 4px solid var(--accent);
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      animation: slideIn 0.28s ease both;
    }}
    .rcard-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 8px; }}
    .rcard-word    {{ font-size: 22px; font-weight: 800; }}
    .rcard-reading {{ font-size: 12px; color: var(--text-sub); margin-top: 2px; }}
    .done-btn {{
      flex-shrink: 0;
      background: white;
      border: 1.5px solid #22c55e;
      color: #22c55e;
      font-size: 12px;
      font-weight: 700;
      padding: 5px 11px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.18s;
    }}
    .done-btn:hover {{ background: #22c55e; color: white; }}
    .rcard-meaning  {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; line-height: 1.6; }}
    .rcard-example  {{ font-size: 12px; color: #4a5568; line-height: 1.7; }}
    .rcard-exja     {{ color: #718096; font-style: italic; margin-top: 3px; }}
    .rcard-tag      {{
      display: inline-block;
      margin-top: 8px;
      font-size: 10px;
      font-weight: 700;
      color: var(--accent);
      background: var(--accent-light);
      padding: 2px 8px;
      border-radius: 10px;
    }}
    .footer {{ text-align: center; font-size: 12px; color: var(--text-sub); padding: 8px 0 24px; }}
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
  </div>
</div>

<div id="today-view" class="view active">
  <div id="cards"></div>
  <div class="pool-status" id="pool-status"></div>
  <div class="next-wrap"><button class="next-btn" id="next-btn" onclick="showNextBatch()">次の語句を見る →</button></div>
  <div class="footer">毎日の積み重ねが力になる 💪</div>
</div>

<div id="review-view" class="view">
  <div id="review-container"></div>
</div>

<script>
// ── Embedded data ────────────────────────────────────────────────
const ALL_VOCAB    = {vocab_js};
const TODAY_POOLS  = {pools_js};
const STREAKS      = {streaks_js};
const STATS        = {stats_js};
const SUBJECTS     = {subjects_js};
const SUBJECT_CFG  = {config_js};
const TODAY_DATE   = '{today_str}';
const BATCH_SIZE   = {BATCH_SIZE};

const DEFAULT_CFG  = {{color:"#6b7280", light:"#f9fafb", emoji:"📚"}};

// ── State ────────────────────────────────────────────────────────
let currentSubject = localStorage.getItem('jr_subject') || SUBJECTS[0];
if (!SUBJECTS.includes(currentSubject)) currentSubject = SUBJECTS[0];

function cfg(s) {{ return SUBJECT_CFG[s] || DEFAULT_CFG; }}

function reviewKey(s) {{ return `jr_review_${{s}}_v1`; }}
function shownKey(s)  {{ return `jr_shown_${{s}}_v1`; }}
function dateKey(s)   {{ return `jr_date_${{s}}_v1`; }}

function getReview(s) {{
  return new Set(JSON.parse(localStorage.getItem(reviewKey(s)) || '[]'));
}}
function saveReview(s, set) {{
  localStorage.setItem(reviewKey(s), JSON.stringify([...set]));
}}
function getShown(s) {{
  if (localStorage.getItem(dateKey(s)) !== TODAY_DATE) {{
    localStorage.setItem(dateKey(s), TODAY_DATE);
    localStorage.setItem(shownKey(s), '0');
    return 0;
  }}
  return parseInt(localStorage.getItem(shownKey(s)) || '0');
}}
function setShown(s, n) {{
  localStorage.setItem(shownKey(s), String(n));
}}

// ── Theme ─────────────────────────────────────────────────────────
function applyTheme(s) {{
  const c = cfg(s);
  document.documentElement.style.setProperty('--accent',       c.color);
  document.documentElement.style.setProperty('--accent-light', c.light);
  document.getElementById('header').style.background =
    `linear-gradient(135deg, ${{c.color}} 0%, ${{shadeColor(c.color, -30)}} 100%)`;
}}
function shadeColor(hex, pct) {{
  const num = parseInt(hex.replace('#',''), 16);
  const r = Math.min(255, Math.max(0, (num>>16) + pct));
  const g = Math.min(255, Math.max(0, ((num>>8)&0xFF) + pct));
  const b = Math.min(255, Math.max(0, (num&0xFF) + pct));
  return '#' + [r,g,b].map(x=>x.toString(16).padStart(2,'0')).join('');
}}

// ── Subject selector ─────────────────────────────────────────────
function buildSubjectTabs() {{
  const container = document.getElementById('subject-tabs');
  SUBJECTS.forEach(s => {{
    const btn = document.createElement('button');
    btn.className = 'subject-tab' + (s === currentSubject ? ' active' : '');
    btn.textContent = (cfg(s).emoji || '') + ' ' + s;
    btn.onclick = () => switchSubject(s);
    container.appendChild(btn);
  }});
}}
function switchSubject(s) {{
  currentSubject = s;
  localStorage.setItem('jr_subject', s);
  document.querySelectorAll('.subject-tab').forEach((b,i) => {{
    b.classList.toggle('active', SUBJECTS[i] === s);
  }});
  applyTheme(s);
  updateHeader();
  document.getElementById('cards').innerHTML = '';
  shownCountForSubject = getShown(s);
  if (shownCountForSubject > 0) {{
    const ids = (TODAY_POOLS[s] || []).slice(0, shownCountForSubject);
    ids.forEach((id, i) => {{
      const card = makeCard(id, s);
      if (card) {{ card.style.animation='none'; document.getElementById('cards').appendChild(card); }}
    }});
  }} else {{
    showNextBatch();
  }}
  updatePoolStatus();
  updateBadge();
  if (document.getElementById('review-view').classList.contains('active')) renderReview();
}}

// ── Header info ──────────────────────────────────────────────────
function updateHeader() {{
  const s = currentSubject;
  document.getElementById('streak-num').textContent = STREAKS[s] || 0;
  const st = STATS[s] || {{introduced:0, total:1}};
  const pct = Math.round(st.introduced / st.total * 100);
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-text').textContent =
    `${{st.introduced}}/${{st.total}}語 (${{pct}}%)`;
}}

// ── View tabs ────────────────────────────────────────────────────
function switchView(v) {{
  document.querySelectorAll('.view-tab').forEach((b,i) => b.classList.toggle('active', i===(v==='today'?0:1)));
  document.getElementById('today-view').classList.toggle('active', v==='today');
  document.getElementById('review-view').classList.toggle('active', v==='review');
  if (v === 'review') renderReview();
}}
function updateBadge() {{
  const n = getReview(currentSubject).size;
  const badge = document.getElementById('badge');
  badge.textContent = n;
  badge.style.display = n > 0 ? 'inline-flex' : 'none';
}}

// ── Card factory ─────────────────────────────────────────────────
function makeCard(id, subj) {{
  const w = ALL_VOCAB[String(id)];
  if (!w) return null;
  const rev = getReview(subj);
  const marked = rev.has(id);
  const el = document.createElement('div');
  el.className = 'card' + (marked ? ' marked' : '');
  el.id = 'card-' + id;
  const exJa = w.example_ja ? `<div class="example-ja">${{w.example_ja}}</div>` : '';
  el.innerHTML = `
    <div class="card-header">
      <div class="word-block">
        <div class="word">${{w.word}}</div>
        <div class="reading">${{w.reading || ''}}</div>
        <div class="cat-tag">${{w.category || ''}}</div>
      </div>
      <button class="review-btn ${{marked?'marked':''}}" id="rbtn-${{id}}" onclick="toggleReview(${{id}})">
        ${{marked ? '📌 復習中' : '＋ 要復習'}}
      </button>
    </div>
    <div class="meaning">${{w.meaning}}</div>
    <div class="ex-label">使用例</div>
    <div class="example">${{w.example}}${{exJa}}</div>`;
  return el;
}}
function toggleReview(id) {{
  const s = currentSubject;
  const rev = getReview(s);
  const btn = document.getElementById('rbtn-' + id);
  const card = document.getElementById('card-' + id);
  if (rev.has(id)) {{
    rev.delete(id);
    btn.className = 'review-btn'; btn.textContent = '＋ 要復習';
    card.classList.remove('marked');
  }} else {{
    rev.add(id);
    btn.className = 'review-btn marked'; btn.textContent = '📌 復習中';
    card.classList.add('marked');
  }}
  saveReview(s, rev);
  updateBadge();
}}

// ── Batch ────────────────────────────────────────────────────────
let shownCountForSubject = 0;
function showNextBatch() {{
  const s = currentSubject;
  const pool = TODAY_POOLS[s] || [];
  const batch = pool.slice(shownCountForSubject, shownCountForSubject + BATCH_SIZE);
  if (!batch.length) return;
  const container = document.getElementById('cards');
  batch.forEach((id, i) => {{
    const card = makeCard(id, s);
    if (card) {{ card.style.animationDelay = (i * 0.07) + 's'; container.appendChild(card); }}
  }});
  shownCountForSubject += batch.length;
  setShown(s, shownCountForSubject);
  updatePoolStatus();
}}
function updatePoolStatus() {{
  const s = currentSubject;
  const pool = TODAY_POOLS[s] || [];
  const remaining = pool.length - shownCountForSubject;
  const statusEl = document.getElementById('pool-status');
  const nextBtn  = document.getElementById('next-btn');
  if (shownCountForSubject > 0) statusEl.textContent = `本日の語句: ${{shownCountForSubject}} / ${{pool.length}} 語 表示済み`;
  if (remaining <= 0) {{
    nextBtn.disabled = true;
    nextBtn.textContent = '本日分はすべて表示しました';
    statusEl.textContent = `${{pool.length}} / ${{pool.length}} 語 表示済み — 明日も続けよう！`;
  }} else {{
    nextBtn.disabled = false;
    nextBtn.textContent = `次の語句を見る (${{Math.min(BATCH_SIZE, remaining)}}語) →`;
  }}
}}

// ── Review list ──────────────────────────────────────────────────
function renderReview() {{
  const s = currentSubject;
  const container = document.getElementById('review-container');
  container.innerHTML = '';
  const rev = getReview(s);
  if (!rev.size) {{
    container.innerHTML = `<div class="review-empty"><div class="icon">📖</div>
      <p>復習リストはまだ空です。<br>語句カードの「＋ 要復習」ボタンで<br>気になった語句を追加しよう！</p></div>`;
    return;
  }}
  const count = document.createElement('div');
  count.className = 'review-count';
  count.textContent = `復習リスト: ${{rev.size}} 語`;
  container.appendChild(count);
  rev.forEach(id => {{
    const w = ALL_VOCAB[String(id)]; if (!w) return;
    const exJa = w.example_ja ? `<div class="rcard-exja">${{w.example_ja}}</div>` : '';
    const el = document.createElement('div');
    el.className = 'rcard'; el.id = 'rcard-' + id;
    el.style.borderColor = cfg(s).color;
    el.innerHTML = `
      <div class="rcard-header">
        <div><div class="rcard-word">${{w.word}}</div><div class="rcard-reading">${{w.reading||''}}</div></div>
        <button class="done-btn" onclick="markDone(${{id}})">覚えた ✓</button>
      </div>
      <div class="rcard-meaning">${{w.meaning}}</div>
      <div class="rcard-example">${{w.example}}${{exJa}}</div>
      <div class="rcard-tag">${{w.category||''}}</div>`;
    container.appendChild(el);
  }});
}}
function markDone(id) {{
  const el = document.getElementById('rcard-' + id);
  el.style.animation = 'fadeOut 0.28s ease forwards';
  setTimeout(() => {{
    const s = currentSubject;
    const rev = getReview(s); rev.delete(id); saveReview(s, rev);
    updateBadge();
    const btn  = document.getElementById('rbtn-' + id);
    const card = document.getElementById('card-' + id);
    if (btn)  {{ btn.className = 'review-btn'; btn.textContent = '＋ 要復習'; }}
    if (card) card.classList.remove('marked');
    renderReview();
  }}, 260);
}}

// ── Init ─────────────────────────────────────────────────────────
buildSubjectTabs();
applyTheme(currentSubject);
updateHeader();
shownCountForSubject = getShown(currentSubject);
if (shownCountForSubject > 0) {{
  (TODAY_POOLS[currentSubject]||[]).slice(0, shownCountForSubject).forEach(id => {{
    const card = makeCard(id, currentSubject);
    if (card) {{ card.style.animation='none'; document.getElementById('cards').appendChild(card); }}
  }});
  updatePoolStatus();
}} else {{
  showNextBatch();
}}
updateBadge();
</script>
</body>
</html>"""


def main():
    today_str = date.today().isoformat()
    vocab = load_json(VOCAB_FILE, [])
    if not vocab:
        print("vocab.json が空です。")
        return

    progress = load_json(PROGRESS_FILE, {"subjects": {}})
    if "subjects" not in progress:
        progress["subjects"] = {}

    # 科目ごとに今日のプールを作成
    subjects_in_vocab = sorted(
        {w["subject"] for w in vocab if "subject" in w},
        key=lambda s: SUBJECT_ORDER.index(s) if s in SUBJECT_ORDER else 99
    )

    today_pools   = {}
    streaks       = {}
    progress_stats = {}

    for subj in subjects_in_vocab:
        if subj not in progress["subjects"]:
            progress["subjects"][subj] = {"history": []}

        subj_vocab   = [w for w in vocab if w.get("subject") == subj]
        subj_history = progress["subjects"][subj].setdefault("history", [])
        pool = get_today_pool(subj_vocab, subj_history, today_str)

        today_pools[subj] = pool
        streaks[subj]     = calculate_streak(subj_history)

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
        st = progress_stats[s]
        print(f"  [{s}] 連続{streaks[s]}日 プール{len(today_pools[s])}語 紹介済み{st['introduced']}/{st['total']}語")


if __name__ == "__main__":
    main()
