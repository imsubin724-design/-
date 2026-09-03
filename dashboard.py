import csv
import calendar
import html
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup

st.set_page_config(page_title="컬러렌즈 글로벌 트렌드 대시보드", layout="wide")

COLOR_OPTIONS = [
    "브라운",
    "카키브라운",
    "애쉬브라운",
    "골드브라운",
    "오렌지브라운",
    "로즈브라운",
    "다크브라운",
    "블랙",
    "그레이",
    "다크그레이",
    "라이트그레이",
    "핑크",
    "블루",
    "기타",
]
MOOD_OPTIONS = ["네추럴/소프트", "글로우/하이라이트", "화려함/컬러풀", "딥/클래식", "기타"]
EDGE_OPTIONS = ["볼드링", "블러 엣지", "슬림링", "중간 엣지", "노 엣지", "라인 엣지", "기타"]
TREND_HISTORY_FILE = "trend_history.csv"
TREND_HISTORY_FIELDS = [
    "date",
    "country",
    "source",
    "rank",
    "product",
    "href",
    "color",
    "color_other",
    "mood",
    "mood_other",
    "edge",
    "edge_other",
]

COUNTRIES = {
    "japan": {
        "key": "japan",
        "label": "일본",
        "source": "Morecon",
        "subtitle": "모어콘 원데이 컬러렌즈 TOP 6 랭킹 기반 트렌드 분석",
        "search_url": "https://morecon.jp/",
        "script": "app.py",
        "today_file": "today.csv",
        "yesterday_file": "yesterday.csv",
        "tag_file": "manual_tags.csv",
        "archive_prefix": "ranking",
        "host": "https://morecon.jp",
        "show_specs": True,
    },
    "thailand": {
        "key": "thailand",
        "label": "태국",
        "source": "Shopee Thailand",
        "subtitle": "Shopee Thailand color lens 판매순 검색 TOP 6 기반 트렌드 분석",
        "empty_message": (
            "태국 Shopee는 비로그인 자동 접속에서 검색 결과를 바로 보여주지 않습니다. "
            "오늘 데이터 업데이트를 누르면 브라우저가 열리니, Shopee에 로그인한 뒤 검색 결과 화면이 보일 때까지 기다려 주세요. "
            "로그인 세션은 shopee_thailand_profile 폴더에 저장되어 다음 수집부터 재사용됩니다."
        ),
        "search_url": "https://shopee.co.th/search?keyword=color%20lens&page=0&sortBy=sales",
        "script": "app_thailand.py",
        "today_file": "thailand_today.csv",
        "yesterday_file": "thailand_yesterday.csv",
        "tag_file": "thailand_manual_tags.csv",
        "archive_prefix": "ranking_thailand",
        "host": "https://shopee.co.th",
        "show_specs": False,
    },
    "queen_eyes": {
        "key": "queen_eyes",
        "label": "일본",
        "title": "일본 Queen Eyes",
        "source": "Queen Eyes",
        "subtitle": "Queen Eyes 1day 컬러렌즈 인기 TOP 6 랭킹 기반 트렌드 분석",
        "search_url": "https://www.queen-eyes.com/",
        "script": "app_queen_eyes.py",
        "today_file": "queen_eyes_today.csv",
        "yesterday_file": "queen_eyes_yesterday.csv",
        "tag_file": "queen_eyes_manual_tags.csv",
        "archive_prefix": "ranking_queen_eyes",
        "host": "https://www.queen-eyes.com",
        "show_specs": True,
    },
}


st.markdown(
    """
<style>
:root {
    --paper:#f8f9fb;
    --panel:#fffdfb;
    --ink:#263044;
    --muted:#747f8f;
    --peach:#eead8a;
    --peach-deep:#d98262;
    --peach-soft:#fff1e8;
    --peach-line:#f0d1c2;
    --shadow:0 14px 32px rgba(176,104,72,0.11);
}
.stApp,
[data-testid="stAppViewContainer"] { background:var(--paper); }
.block-container { padding-top:2.1rem; padding-left:1.4rem; padding-right:1.4rem; }
.page-head {
    padding:2rem 2.2rem;
    margin-bottom:1.5rem;
    border-radius:8px;
    background:linear-gradient(135deg, #eda886 0%, #efb99f 100%);
    box-shadow:var(--shadow);
    border:1px solid rgba(255,255,255,0.42);
}
.page-head-home {
    background:transparent;
    border:0;
    box-shadow:none;
    padding:1.2rem 0.15rem 1.35rem;
}
.page-head-home .main-title {
    color:#6f83b7;
    font-size:54px;
    line-height:1.18;
}
.page-head-row {
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap:1.2rem;
}
.page-head-thailand { background:linear-gradient(135deg, #d7a85a 0%, #edd6a0 100%); }
.page-head-queen_eyes {
    background:linear-gradient(135deg, #f5b8ca 0%, #f9d3de 100%);
    border-color:rgba(255,255,255,0.54);
    box-shadow:0 14px 32px rgba(191,103,132,0.13);
}
.home-head-copy { min-width:0; }
.home-guide {
    display:flex;
    align-items:center;
    gap:0;
    margin-left:1.1rem;
    margin-top:0.85rem;
    color:#5f6877;
    font-size:0.92rem;
    font-weight:700;
    line-height:1.4;
}
.home-guide strong { color:#6f83b7; font-weight:900; }
.source-grid {
    display:grid;
    grid-template-columns:minmax(0, 1fr);
    gap:0.85rem;
    margin-top:0.6rem;
    width:50%;
    margin-left:25%;
}
.source-card {
    display:flex;
    align-items:center;
    gap:1.4rem;
    min-height:126px;
    padding:1.15rem 1.3rem;
    border:1px solid var(--peach-line);
    border-radius:8px;
    background:var(--panel);
    box-shadow:0 8px 18px rgba(176,104,72,0.07);
}
.source-card.active { border-color:#e8b195; background:#fffaf6; }
.source-card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; flex:0 0 290px; }
.source-index { color:var(--peach-deep); font-size:0.75rem; font-weight:900; letter-spacing:0.08em; }
.source-name { margin:0.25rem 0 0.35rem; color:var(--ink); font-size:1.25rem; font-weight:900; }
.source-url { color:#7b8492; font-size:0.76rem; overflow-wrap:anywhere; }
.source-status { flex:0 0 auto; padding:0.28rem 0.55rem; border-radius:999px; background:#f9e5d9; color:#a95e43; font-size:0.7rem; font-weight:900; }
.source-status.pending { background:#eef1f5; color:#697386; }
.source-description { flex:1; margin:0; color:#5f6877; font-size:0.9rem; line-height:1.55; }
.source-action { flex:0 0 auto; display:inline-block; padding:0.48rem 0.72rem; border:1px solid #e5b49e; border-radius:6px; color:#a45b43; font-size:0.8rem; font-weight:900; text-decoration:none; white-space:nowrap; }
.source-action:hover { background:#fff0e7; }
@media (max-width: 760px) {
    .home-layout { grid-template-columns:1fr !important; gap:1rem !important; }
    .home-layout > div:first-child { min-height:0 !important; padding:0 0 1.5rem !important; border-right:0 !important; border-bottom:1px solid #dfe5ef; }
    .home-layout > div:first-child > div:nth-child(2) { white-space:normal !important; font-size:38px !important; }
    .source-grid { width:100% !important; margin-left:0 !important; }
    .source-card { display:block; }
    .source-card-top { margin-bottom:0.7rem; }
    .source-description { margin-bottom:0.75rem; }
}
.main-title { font-size:42px; font-weight:800; line-height:1.38; color:#ffffff; margin:0 0 0.35rem 0; padding-top:0.25rem; overflow:visible; }
.main-subtitle { font-size:1rem; color:rgba(255,255,255,0.9); margin-bottom:0; }
.header-update {
    flex:0 0 auto;
    align-self:flex-start;
    min-width:230px;
    margin-top:0.35rem;
    padding:0.8rem 0.95rem;
    border-radius:8px;
    border:1px solid rgba(255,255,255,0.46);
    background:rgba(255,255,255,0.22);
    color:#ffffff;
    text-align:right;
    box-shadow:0 10px 22px rgba(128,74,48,0.10);
}
.header-update-label { font-size:0.78rem; font-weight:800; color:rgba(255,255,255,0.78); margin-bottom:0.18rem; }
.header-update-time { font-size:1rem; font-weight:900; line-height:1.35; color:#ffffff; }
.section-title {
    font-size:1.35rem;
    font-weight:800;
    color:var(--ink);
    margin-top:1.1rem;
    margin-bottom:0.9rem;
    padding-left:0.75rem;
    border-left:4px solid var(--peach-deep);
}
.country-panel { border:1px solid var(--peach-line); border-radius:8px; padding:1rem; background:var(--panel); min-height:138px; box-shadow:0 8px 18px rgba(176,104,72,0.07); }
.country-name { font-size:1.25rem; font-weight:800; color:var(--ink); margin-bottom:0.25rem; }
.country-source { font-size:0.9rem; color:#5f6877; margin-bottom:0.55rem; }
.country-desc { font-size:0.9rem; line-height:1.55; color:var(--muted); }
.country-orb-grid { display:grid; grid-template-columns:repeat(7, minmax(120px, 1fr)); gap:0.95rem; align-items:start; }
.country-orb-rail { display:grid; gap:0.55rem; align-content:start; justify-items:center; }
.country-orb-card { text-align:center; padding:0.45rem 0.2rem 0.2rem; }
.country-orb {
    width:86px;
    height:86px;
    border-radius:999px;
    margin:0 auto 0.65rem;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    color:#1f2937;
    box-shadow:0 10px 20px rgba(176,104,72,0.10);
    border:1px solid rgba(217,130,98,0.22);
}
.country-orb.japan { background:radial-gradient(circle at 30% 24%, #fff8f5 0%, #f7d4c5 58%, #efb496 100%); }
.country-orb.thailand { background:radial-gradient(circle at 30% 24%, #fffaf2 0%, #f4dfbd 58%, #e9c58f 100%); }
.country-orb.korea { background:radial-gradient(circle at 30% 24%, #f8fffd 0%, #d6eee7 58%, #a6cfc5 100%); }
.country-orb.china { background:radial-gradient(circle at 30% 24%, #fff8f4 0%, #ecd6cd 58%, #d4b4a6 100%); }
.country-orb.southeast { background:radial-gradient(circle at 30% 24%, #fffaf0 0%, #f1dbab 58%, #d8b15e 100%); }
.country-orb.usa { background:radial-gradient(circle at 30% 24%, #f8fbff 0%, #d4e0ed 58%, #9eb4cb 100%); }
.country-orb.soon-a { background:radial-gradient(circle at 30% 24%, #fbfbf6 0%, #dfebd9 58%, #bfd7bb 100%); }
.country-orb.soon-b { background:radial-gradient(circle at 30% 24%, #fff7f2 0%, #ead5cb 58%, #d5b8aa 100%); }
.country-orb.soon-c { background:radial-gradient(circle at 30% 24%, #f7fbfb 0%, #d3e6e5 58%, #bad2d1 100%); }
.country-orb.soon-d { background:radial-gradient(circle at 30% 24%, #fbf9ff 0%, #ded7ea 58%, #c7bfd8 100%); }
.country-orb.soon-e { background:radial-gradient(circle at 30% 24%, #fff9ee 0%, #efd9aa 58%, #dfbd7c 100%); }
.country-orb-icon { font-size:1rem; line-height:1; margin-bottom:0.22rem; font-weight:900; }
.country-orb-title { font-size:0.78rem; font-weight:900; letter-spacing:0; }
.country-orb-source { font-size:0.54rem; font-weight:700; opacity:0.78; margin-top:0.1rem; }
.country-orb-desc { color:#4b5563; font-size:0.78rem; line-height:1.45; min-height:2.4rem; max-width:180px; margin:0 auto 0.55rem; }
.country-soon-label {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:86px;
    min-height:32px;
    border:1px solid var(--peach-line);
    border-radius:999px;
    padding:0.18rem 0.55rem;
    font-size:0.72rem;
    font-weight:800;
    color:#8a6a5e;
    background:#fff8f4;
}
.country-action {
    width:86px;
    margin:-0.28rem auto 0.22rem;
}
.country-action div.stButton > button {
    min-height:32px;
    padding:0.18rem 0.55rem;
    border-radius:999px;
    font-size:0.78rem;
}
.country-action div[data-testid="stLinkButton"] a,
.country-action-link {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:86px;
    min-height:32px !important;
    padding:0.18rem 0.55rem !important;
    border-radius:999px !important;
    font-size:0.72rem !important;
    font-weight:700;
    text-decoration:none;
    border:1px solid var(--peach-line);
    background:#fffaf7;
    color:var(--ink);
}
.country-action-link:hover {
    border-color:#6f83b7;
    color:#485f9d;
    background:#f1f4fb;
}
div[class*="st-key-open_japan_map"],
div[class*="st-key-open_thailand_map"] {
    width:96px !important;
    margin:-0.28rem auto 0.22rem !important;
}
div[class*="st-key-open_japan_map"] button,
div[class*="st-key-open_thailand_map"] button {
    min-height:32px !important;
    padding:0.18rem 0.55rem !important;
    border-radius:999px !important;
    font-size:0.78rem !important;
}
@media (max-width: 1200px) { .country-orb-grid { grid-template-columns:repeat(4, minmax(120px, 1fr)); } }
@media (max-width: 760px) { .country-orb-grid { grid-template-columns:repeat(2, minmax(120px, 1fr)); } }
.map-shell { display:grid; grid-template-columns:minmax(0, 1.75fr) minmax(320px, 0.8fr); gap:1.2rem; align-items:stretch; margin-bottom:1.2rem; }
.map-stage { position:relative; min-height:470px; border:1px solid var(--peach-line); border-radius:12px; background:#fffaf7; overflow:hidden; box-shadow:var(--shadow); }
.map-stage svg { position:absolute; inset:0; width:100%; height:100%; }
.map-land { fill:#d1d5db; stroke:#ffffff; stroke-width:1.5; }
.map-grid { stroke:#e5e7eb; stroke-width:1; opacity:0.75; }
.map-ocean-label { fill:#9ca3af; font-size:13px; font-weight:700; letter-spacing:0.02em; }
.map-pin { position:absolute; transform:translate(-50%, -100%); text-decoration:none; color:#111827; }
.map-pin-dot { width:18px; height:18px; border-radius:999px; background:#ef4444; border:3px solid #ffffff; box-shadow:0 8px 20px rgba(17,24,39,0.24); margin:0 auto 0.35rem; }
.map-pin-card { min-width:132px; border:1px solid #d1d5db; border-radius:8px; background:rgba(255,255,255,0.95); padding:0.55rem 0.65rem; box-shadow:0 12px 30px rgba(17,24,39,0.11); }
.map-pin-country { font-size:0.95rem; font-weight:800; line-height:1.2; }
.map-pin-source { font-size:0.76rem; color:#6b7280; margin-top:0.12rem; }
.map-pin:hover .map-pin-card { border-color:#111827; }
.map-side { border:1px solid var(--peach-line); border-radius:12px; background:var(--panel); padding:1.15rem; box-shadow:var(--shadow); }
.map-side-title { font-size:1rem; font-weight:800; color:#111827; margin-bottom:0.45rem; }
.home-map-side-title { color:#36446c; font-size:1.05rem; margin-bottom:0.65rem; }
.home-section-title {
    font-size:1.35rem;
    font-weight:900;
    color:#36446c;
    margin-top:1.1rem;
    margin-bottom:0.9rem;
    padding-left:0.75rem;
    border-left:4px solid #6f83b7;
}
.map-side-text { color:#6b7280; font-size:0.9rem; line-height:1.65; margin-bottom:1rem; }
.map-list { display:grid; gap:0.7rem; }
.map-list-item { display:block; border:1px solid var(--peach-line); border-radius:8px; padding:0.8rem 0.9rem; text-decoration:none; color:#111827; background:#fff8f4; }
.map-list-item:hover { border-color:var(--peach-deep); background:#ffffff; }
.map-list-title { font-size:1rem; font-weight:800; margin-bottom:0.15rem; }
.map-list-meta { font-size:0.82rem; color:#6b7280; }
.rank-badge { font-size:1.7rem; font-weight:800; color:#111827; margin-bottom:0.4rem; }
.product-name { font-size:1rem; font-weight:700; color:#111827; line-height:1.35; margin-top:0.5rem; margin-bottom:0.4rem; min-height:2.7rem; }
.spec-box { border:1px solid #f1ddd3; border-radius:8px; padding:0.55rem 0.7rem; background:#fffaf7; font-size:0.88rem; color:#111827; margin-bottom:0.35rem; }
.spec-label { color:#6b7280; font-size:0.78rem; display:block; margin-bottom:0.1rem; }
.status-up { color:#15803d; font-weight:700; }
.status-down { color:#b91c1c; font-weight:700; }
.status-new { color:#b45309; font-weight:700; }
.status-keep { color:#6b7280; font-weight:700; }
.card-status-marker { display:none; }
.card-status-row { display:flex; align-items:center; justify-content:space-between; gap:0.7rem; margin-bottom:0.65rem; }
.status-pill { display:inline-flex; align-items:center; border-radius:999px; padding:0.22rem 0.65rem; font-size:0.86rem; font-weight:800; }
.status-pill-up { color:#166534; background:#dcfce7; border:1px solid #86efac; }
.status-pill-down { color:#991b1b; background:#fee2e2; border:1px solid #fca5a5; }
.status-pill-new { color:#92400e; background:#fef3c7; border:1px solid #fcd34d; }
.status-pill-keep { color:#374151; background:#f3f4f6; border:1px solid #d1d5db; }
div[class*="st-key-rank-card-up"],
div[class*="st-key-rank-card-up"] div[data-testid="stVerticalBlockBorderWrapper"] {
    border:3px solid #bbdfc0 !important;
    box-shadow:0 0 0 1px #dff1e2 inset !important;
    background:#fbfffc !important;
}
div[class*="st-key-rank-card-down"],
div[class*="st-key-rank-card-down"] div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color:rgba(49,51,63,0.2) !important;
    box-shadow:none !important;
    background:#ffffff !important;
}
div[class*="st-key-rank-card-new"],
div[class*="st-key-rank-card-new"] div[data-testid="stVerticalBlockBorderWrapper"] {
    border:3px solid #f1d28a !important;
    box-shadow:0 0 0 1px #fef0c7 inset !important;
    background:#fffdf6 !important;
}
div[class*="st-key-rank-card-keep"],
div[class*="st-key-rank-card-keep"] div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color:rgba(49,51,63,0.2) !important;
    box-shadow:none !important;
    background:#ffffff !important;
}
.metric-card { background:#fff8f4; border:1px solid var(--peach-line); border-radius:8px; padding:16px 18px; margin-bottom:12px; box-shadow:0 8px 18px rgba(176,104,72,0.06); }
.metric-label { font-size:14px; color:#6b7280; font-weight:600; margin-bottom:6px; }
.metric-value { font-size:32px; color:#111827; font-weight:800; line-height:1; }
.summary-box { border:1px solid var(--peach-line); border-radius:8px; padding:1rem 1.1rem; background:var(--panel); margin-bottom:1rem; box-shadow:0 8px 18px rgba(176,104,72,0.06); }
.summary-title { font-size:0.95rem; font-weight:700; color:#111827; margin-bottom:0.45rem; }
.summary-text { font-size:0.95rem; line-height:1.7; color:#374151; }
.calendar-top { display:grid; grid-template-columns:56px 1fr 56px; align-items:center; width:78%; margin:0 auto 2.2rem; }
.calendar-nav { color:#9b5d52; text-decoration:none; font-size:1.25rem; font-weight:400; text-align:center; line-height:1; }
.calendar-nav.is-disabled { color:#dfd3ce; pointer-events:none; }
.calendar-title { text-align:center; }
.calendar-selected-day { font-size:5.8rem; line-height:0.86; color:#454545; font-weight:700; }
.calendar-selected-rule { width:110px; height:1px; background:#b77772; margin:0.52rem auto 0.38rem; }
.calendar-month-name { font-size:1.75rem; line-height:1; color:#454545; font-weight:900; letter-spacing:0.02em; }
.calendar-grid { display:grid; grid-template-columns:repeat(7, 1fr); row-gap:2rem; column-gap:0.45rem; align-items:center; width:78%; margin:0 auto; }
.calendar-weekday { text-align:center; font-size:0.95rem; font-weight:900; color:#454545; }
.calendar-weekday.is-sun { color:#a55757; }
.calendar-day,
.calendar-empty {
    min-height:3.75rem;
    display:flex;
    align-items:flex-start;
    justify-content:center;
}
.calendar-day a,
.calendar-day span {
    display:inline-block;
    min-width:2rem;
    padding-top:0.08rem;
    text-align:center;
    font-size:1.34rem;
    line-height:1;
    text-decoration:none;
}
.calendar-day a { color:#565656; }
.calendar-day.is-sun a,
.calendar-day.is-sun span { color:#a55757; }
.calendar-day.is-selected a {
    color:#a55757;
    border-bottom:1px solid #b77772;
    padding-bottom:0.12rem;
}
.calendar-day.is-unavailable span { color:#d6ccc8; }
div[class*="st-key-snapshot_calendar"] {
    max-width:none !important;
    width:100% !important;
    border:1px solid var(--peach-line) !important;
    border-radius:8px !important;
    background:var(--panel) !important;
    box-shadow:0 8px 18px rgba(176,104,72,0.06) !important;
    min-height:560px !important;
    padding:1.4rem 1.25rem 2.6rem !important;
}
div[class*="st-key-snapshot_calendar"] div[data-testid="stHorizontalBlock"] {
    width:78% !important;
    margin-left:auto !important;
    margin-right:auto !important;
    margin-bottom:0.85rem !important;
}
div[class*="st-key-snapshot_calendar"] div[data-testid="stHorizontalBlock"]:first-of-type {
    width:86% !important;
    margin-bottom:1.6rem !important;
}
div[class*="st-key-calendar_nav"] button,
div[class*="st-key-calendar_day_text"] button {
    width:100% !important;
    min-height:0 !important;
    padding:0 !important;
    border:0 !important;
    border-radius:0 !important;
    background:transparent !important;
    box-shadow:none !important;
    color:#565656 !important;
    line-height:1 !important;
}
div[class*="st-key-calendar_nav"] button {
    font-size:1.45rem !important;
    color:#9b5d52 !important;
}
div[class*="st-key-calendar_day_text"] button {
    font-size:1.34rem !important;
    font-weight:800 !important;
    text-decoration:underline !important;
    text-underline-offset:0.22rem !important;
    text-decoration-thickness:1px !important;
    display:flex !important;
    justify-content:center !important;
    align-items:flex-start !important;
}
div[class*="st-key-calendar_day_text"] button * {
    font-size:1.34rem !important;
    font-weight:800 !important;
}
div[class*="st-key-calendar_day_sun"] button {
    color:#a55757 !important;
}
div[class*="st-key-calendar_day_active"] button p {
    color:#a55757 !important;
}
div[class*="st-key-calendar_nav"] button p,
div[class*="st-key-calendar_day_text"] button p {
    width:100% !important;
    text-align:center !important;
    font-weight:inherit !important;
    line-height:1 !important;
}
div[class*="st-key-calendar_day_text"] button p {
    font-size:1.34rem !important;
}
div[class*="st-key-calendar_nav"] button p {
    font-size:1.45rem !important;
}
.change-item { display:flex; gap:0.65rem; align-items:center; padding:0.55rem 0; border-top:1px solid #f1ddd3; }
.change-item:first-of-type { border-top:0; padding-top:0; }
.change-thumb { width:52px; height:52px; border-radius:8px; object-fit:cover; border:1px solid #e5e7eb; background:#f9fafb; flex:0 0 auto; }
.change-info { min-width:0; }
.change-name { font-size:0.9rem; line-height:1.45; font-weight:700; color:#111827; text-decoration:none; }
.change-meta { font-size:0.82rem; color:#6b7280; margin-top:0.15rem; }
.repeat-panel {
    border:1px solid var(--peach-line);
    border-radius:8px;
    background:var(--panel);
    box-shadow:0 8px 18px rgba(176,104,72,0.06);
    padding:0.85rem;
}
.repeat-list { display:grid; gap:0.55rem; }
.repeat-item {
    display:grid;
    grid-template-columns:30px 64px minmax(0, 1fr);
    gap:0.7rem;
    align-items:center;
    border:1px solid #f0ded5;
    border-radius:8px;
    padding:0.55rem;
    background:#fffdfb;
}
.repeat-rank {
    width:30px;
    height:30px;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:999px;
    background:#fff1e8;
    color:#9b5d52;
    font-size:0.82rem;
    font-weight:900;
}
.repeat-thumb {
    width:64px;
    height:64px;
    border-radius:8px;
    object-fit:cover;
    border:1px solid #eadbd4;
    background:#fff8f4;
}
.repeat-name {
    display:block;
    color:#111827;
    font-size:0.86rem;
    font-weight:800;
    line-height:1.35;
    text-decoration:none;
    margin-bottom:0.35rem;
}
.repeat-meta { display:flex; flex-wrap:wrap; gap:0.3rem; }
.repeat-pill {
    display:inline-flex;
    align-items:center;
    border-radius:999px;
    padding:0.16rem 0.5rem;
    background:#fff1e8;
    border:1px solid #efd2c4;
    color:#6b4f45;
    font-size:0.72rem;
    font-weight:800;
}
.trend-box { border:1px solid var(--peach-line); border-radius:8px; padding:1.15rem; background:var(--panel); box-shadow:var(--shadow); }
.trend-text,
.trend-text * {
    font-size:0.98rem !important;
    line-height:1.6 !important;
    color:#1f2937 !important;
    font-weight:600 !important;
    white-space:pre-line;
}
.trend-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:0.75rem; }
.trend-grid-vertical { grid-template-columns:1fr; }
.trend-card {
    border:1px solid #f0ded5;
    border-radius:8px;
    background:#fffdfb;
    padding:0.9rem 0.95rem;
    min-height:150px;
}
.trend-label {
    display:block;
    margin-bottom:0.55rem;
    color:#9b5d52 !important;
    font-weight:900 !important;
    font-size:0.9rem !important;
}
.trend-body { display:grid; gap:0.42rem; }
.trend-body-line { margin:0; }
.trend-chip-row { display:flex; flex-wrap:wrap; align-items:center; gap:0.35rem; margin-top:0.1rem; }
.trend-chip-label {
    color:#1f2937 !important;
    font-weight:900 !important;
    margin-right:0.08rem;
}
.trend-chip {
    display:inline-flex;
    align-items:center;
    border-radius:999px;
    padding:0.18rem 0.55rem;
    background:#fff1e8;
    border:1px solid #efd2c4;
    color:#6b4f45 !important;
    font-size:0.82rem !important;
    font-weight:800 !important;
}
@media (max-width: 1100px) {
    .trend-grid { grid-template-columns:1fr; }
}
div[role="radiogroup"] {
    gap:1.6rem !important;
}
div[role="radiogroup"] label {
    font-size:1.55rem !important;
    font-weight:800 !important;
    color:var(--ink) !important;
    padding:0.6rem 0.25rem !important;
    min-height:2.8rem !important;
    align-items:center !important;
}
div[role="radiogroup"] label p {
    font-size:1.55rem !important;
    font-weight:800 !important;
}
div[data-baseweb="radio"] > div:first-child {
    width:1.75rem !important;
    height:1.75rem !important;
    border-color:#d7b5a7 !important;
    border-width:3px !important;
    margin-right:0.55rem !important;
}
div[data-baseweb="radio"] div[aria-checked="true"] {
    border-color:var(--peach-deep) !important;
}
div[data-baseweb="radio"] div[aria-checked="true"] > div {
    width:0.75rem !important;
    height:0.75rem !important;
}
div[data-testid="stDataFrame"] {
    border:1px solid var(--peach-line);
    border-radius:8px;
    overflow:hidden;
    box-shadow:0 8px 18px rgba(176,104,72,0.06);
}
div[data-testid="stDataFrame"] [role="columnheader"] {
    background:#f7f1ed !important;
    color:#5d6470 !important;
    font-weight:700 !important;
}
div[data-testid="stDataFrame"] [role="gridcell"] {
    background:#fffdfb !important;
    color:var(--ink) !important;
    border-color:#eee1db !important;
}
div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
    background:#fff8f4 !important;
}
div.stButton > button {
    border-radius:8px;
    font-weight:700;
    border:1px solid var(--peach-line);
    background:#fffaf7;
    color:var(--ink);
}
div.stButton > button:hover {
    border-color:var(--peach-deep);
    color:#a65f45;
    background:var(--peach-soft);
}
div[class*="st-key-calendar_day_selected"] button {
    border-color:#dd5b5b !important;
    background:#fff1ee !important;
    color:#d95353 !important;
    font-weight:900 !important;
}
div[class*="st-key-calendar_day_available"] button {
    font-weight:800 !important;
}
@media (max-width: 900px) {
    .page-head-row { flex-direction:column; gap:0.9rem; }
    .home-head-row { flex-direction:column; align-items:flex-start; gap:0.9rem; }
    .home-guide { display:flex; margin-left:0; margin-top:0.45rem; }
    .header-update { min-width:0; width:100%; text-align:left; }
    .map-shell { grid-template-columns:1fr; }
    .map-stage { min-height:360px; }
    .map-pin-card { min-width:110px; padding:0.45rem 0.55rem; }
    .country-orb {
        width:112px;
        height:112px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


def get_query_country():
    value = st.query_params.get("country")
    return value if value in COUNTRIES else ""


def format_last_update(path):
    if not os.path.exists(path):
        return "업데이트 기록 없음"

    updated_at = datetime.fromtimestamp(os.path.getmtime(path))
    return updated_at.strftime("%Y.%m.%d %H:%M")


def set_country(country_key):
    st.query_params["country"] = country_key
    st.rerun()


def seed_country_back_history(country_key):
    components.html(
        f"""
        <script>
        (function() {{
            const targetSearch = "?country={country_key}";
            const parentWindow = window.parent;
            const location = parentWindow.location;
            const state = parentWindow.history.state || {{}};

            if (!parentWindow.__lensBackToMapInstalled) {{
                parentWindow.__lensBackToMapInstalled = true;
                parentWindow.addEventListener("popstate", function() {{
                    if (!parentWindow.location.search.includes("country=")) {{
                        parentWindow.setTimeout(function() {{
                            parentWindow.location.reload();
                        }}, 0);
                    }}
                }});
            }}

            if (location.search === targetSearch && !state.lensBackSeeded) {{
                parentWindow.history.replaceState({{lensHomeSeed: true}}, "", location.pathname || "/");
                parentWindow.history.pushState({{lensBackSeeded: true}}, "", (location.pathname || "/") + targetSearch);
            }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def load_rows(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean_url(url, config):
    url = str(url or "").strip()
    if not url or url.lower() == "nan":
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{config['host']}{url}"
    return url


def normalize_href(href, config):
    return clean_url(href, config)


def derive_eye_image_url(image_url, config):
    image_url = clean_url(image_url, config)
    if "thum_640x640.jpg" in image_url:
        return image_url.replace("thum_640x640.jpg", "thum_640x360_eye.jpg")
    return ""


def short_name(product, max_len=38):
    product = str(product)
    return product if len(product) <= max_len else product[:max_len] + "..."


def trend_product_name(product, max_len=30):
    product = str(product or "").strip()
    if not product:
        return "해당 제품"

    parenthesized = re.findall(r"\(([^()]*)\)", product)
    english_candidates = []
    for candidate in parenthesized:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        alpha_count = len(re.findall(r"[A-Za-z]", candidate))
        if alpha_count >= 4 and candidate.upper() != "NEW":
            english_candidates.append(candidate)

    if english_candidates:
        best = max(english_candidates, key=len)
        return short_name(best, max_len)

    ascii_parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’./&+ -]{2,}", product)
    ascii_name = re.sub(r"\s+", " ", " ".join(ascii_parts)).strip(" -/|")
    if len(re.findall(r"[A-Za-z]", ascii_name)) >= 4:
        return short_name(ascii_name, max_len)

    return short_name(product, 18)


def load_manual_tags(config):
    tags = {}
    tag_file = config["tag_file"]
    if not os.path.exists(tag_file):
        return tags

    with open(tag_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            href = normalize_href(row.get("href", ""), config)
            mood = row.get("mood", "")
            edge = row.get("edge", "")
            mood_other = row.get("mood_other", "")
            edge_other = row.get("edge_other", "")

            if not mood and not edge:
                mood, edge = migrate_legacy_style(row.get("style", ""))
            else:
                mood = normalize_mood_label(mood)
                edge = normalize_edge_label(edge)

            tags[href] = {
                "color": row.get("color", ""),
                "color_other": row.get("color_other", ""),
                "mood": mood,
                "mood_other": mood_other,
                "edge": edge,
                "edge_other": edge_other,
                "style": row.get("style", ""),
                "style_other": row.get("style_other", ""),
            }
    return tags


def migrate_legacy_style(style):
    style = str(style or "").strip()
    mood_map = {
        "내추럴": "네추럴/소프트",
        "물광": "글로우/하이라이트",
        "하이라이트": "글로우/하이라이트",
        "화려함": "화려함/컬러풀",
    }
    edge_map = {
        "볼드링": "볼드링",
        "또렷함": "라인 엣지",
    }
    return mood_map.get(style, ""), edge_map.get(style, "")


def normalize_mood_label(mood):
    return {"글러우/하이라이트": "글로우/하이라이트"}.get(mood, mood)


def normalize_edge_label(edge):
    return {"중간엣지": "중간 엣지", "라인엣지": "라인 엣지"}.get(edge, edge)


def save_manual_tags(tags, config):
    with open(config["tag_file"], "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "href",
                "color",
                "color_other",
                "mood",
                "mood_other",
                "edge",
                "edge_other",
                "style",
                "style_other",
            ]
        )
        for href, info in tags.items():
            writer.writerow(
                [
                    href,
                    info.get("color", ""),
                    info.get("color_other", ""),
                    info.get("mood", ""),
                    info.get("mood_other", ""),
                    info.get("edge", ""),
                    info.get("edge_other", ""),
                    info.get("style", ""),
                    info.get("style_other", ""),
                ]
            )


def load_trend_history():
    if not os.path.exists(TREND_HISTORY_FILE):
        return pd.DataFrame(columns=TREND_HISTORY_FIELDS)

    df = pd.read_csv(TREND_HISTORY_FILE, encoding="utf-8-sig")
    for field in TREND_HISTORY_FIELDS:
        if field not in df.columns:
            df[field] = ""
    return df[TREND_HISTORY_FIELDS]


def save_trend_snapshot(config, df_today, manual_tags):
    if df_today.empty:
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    history = load_trend_history()

    rows = []
    for _, row in df_today.head(6).iterrows():
        href = row["href"]
        tag = manual_tags.get(href, {})
        rows.append(
            {
                "date": today,
                "country": config["label"],
                "source": config["source"],
                "rank": int(row["rank"]),
                "product": row.get("product", ""),
                "href": href,
                "color": display_color_value(tag),
                "color_other": tag.get("color_other", ""),
                "mood": display_mood_value(tag),
                "mood_other": tag.get("mood_other", ""),
                "edge": display_edge_value(tag),
                "edge_other": tag.get("edge_other", ""),
            }
        )

    snapshot = pd.DataFrame(rows, columns=TREND_HISTORY_FIELDS)
    if history.empty:
        combined = snapshot
    else:
        same_day_country_hrefs = set(zip(snapshot["date"], snapshot["country"], snapshot["href"]))
        keep_mask = ~history.apply(
            lambda r: (r["date"], r["country"], r["href"]) in same_day_country_hrefs,
            axis=1,
        )
        combined = pd.concat([history[keep_mask], snapshot], ignore_index=True)

    combined.to_csv(TREND_HISTORY_FILE, index=False, encoding="utf-8-sig")
    return len(rows)


@st.cache_data(show_spinner=False)
def get_japan_product_spec(url):
    if not url:
        return {"DIA": "-", "G.DIA": "-", "BC": "-", "PERIOD": "-"}

    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # The page header contains search-filter choices such as DIA 14.0mm and
        # colored diameter 11.2mm. Restrict parsing to the product-spec section
        # so those filter values are not mistaken for the current product.
        spec_heading = soup.find(
            lambda tag: tag.name in {"h1", "h2", "h3", "h4"}
            and "商品スペック" in tag.get_text(" ", strip=True)
        )
        if spec_heading:
            spec_start = text.find("商品スペック")
            spec_text = text[spec_start : spec_start + 2000]
        else:
            spec_text = text

        def find_mm(keywords):
            for kw in keywords:
                pattern = rf"{re.escape(kw)}[^0-9]{{0,15}}([0-9]+(?:\.[0-9]+)?)\s*mm"
                m = re.search(pattern, spec_text, re.IGNORECASE)
                if m:
                    return f"{m.group(1)} mm"
            return "-"

        def find_plain(keywords):
            for kw in keywords:
                pattern = rf"{re.escape(kw)}[^0-9A-Za-zぁ-んァ-ヶ一-龥]{{0,15}}([0-9]+(?:\.[0-9]+)?)"
                m = re.search(pattern, spec_text, re.IGNORECASE)
                if m:
                    return m.group(1)
            return "-"

        dia = find_mm(["レンズ直径", "DIA"])
        gdia = find_mm(["着色直径", "G.DIA"])
        bc = find_plain(["レンズBC", "ベースカーブ", "BC"])
        if bc != "-":
            bc = f"{bc} mm"

        low = spec_text.lower()
        period = "원데이" if ("ワンデー" in spec_text or "1day" in low or "원데이" in spec_text) else "-"

        return {"DIA": dia, "G.DIA": gdia, "BC": bc, "PERIOD": period}
    except Exception:
        return {"DIA": "-", "G.DIA": "-", "BC": "-", "PERIOD": "-"}


def spec_cell(label, value):
    st.markdown(
        f"""
        <div class="spec-box">
            <span class="spec-label">{label}</span>
            {html.escape(str(value))}
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_status_map(df_today, df_yesterday):
    status_map = {}
    if df_today.empty:
        return status_map

    yesterday_rank_map = {}
    if not df_yesterday.empty:
        yesterday_rank_map = dict(zip(df_yesterday["href"], df_yesterday["rank"]))

    for _, row in df_today.iterrows():
        href = row["href"]
        rank = int(row["rank"])

        if href not in yesterday_rank_map:
            status = "신규"
        else:
            old_rank = int(yesterday_rank_map[href])
            if rank < old_rank:
                status = "상승"
            elif rank > old_rank:
                status = "하락"
            else:
                status = "유지"

        status_map[href] = status
    return status_map


def build_rank_change_rows(df_today, df_yesterday, status_map, target_status):
    if df_today.empty:
        return []

    yesterday_rank_map = {}
    if not df_yesterday.empty:
        yesterday_rank_map = dict(zip(df_yesterday["href"], df_yesterday["rank"]))

    rows = []
    for _, row in df_today.iterrows():
        href = row["href"]
        status = status_map.get(href, "유지")
        if status != target_status:
            continue

        rank = int(row["rank"])
        old_rank = yesterday_rank_map.get(href)
        if old_rank:
            movement = f"{int(old_rank)}위 → {rank}위"
        else:
            movement = f"{rank}위 신규 진입"

        rows.append(
            {
                "rank": rank,
                "old_rank": int(old_rank) if old_rank else None,
                "movement": movement,
                "product": row.get("product", ""),
                "href": href,
                "image_url": row.get("image_url", ""),
            }
        )

    return rows


def render_change_summary(title, rows):
    if not rows:
        body = '<div class="summary-text">해당 제품 없음</div>'
    else:
        body = ""
        for row in rows:
            name = html.escape(short_name(row["product"], 44))
            href = html.escape(row["href"], quote=True)
            image_url = html.escape(str(row.get("image_url", "")), quote=True)
            movement = html.escape(row["movement"])
            thumb = f'<img class="change-thumb" src="{image_url}" alt="">' if image_url else '<div class="change-thumb"></div>'
            body += (
                '<div class="change-item">'
                f"{thumb}"
                '<div class="change-info">'
                f'<a class="change-name" href="{href}" target="_blank">{name}</a>'
                f'<div class="change-meta">{movement}</div>'
                "</div>"
                "</div>"
            )

    st.markdown(
        f'<div class="summary-box"><div class="summary-title">{html.escape(title)}</div>{body}</div>',
        unsafe_allow_html=True,
    )


def render_status(status):
    class_name = {
        "상승": "status-pill-up",
        "하락": "status-pill-down",
        "신규": "status-pill-new",
        "유지": "status-pill-keep",
    }.get(status, "status-pill-keep")
    marker_class = {
        "상승": "card-status-up",
        "하락": "card-status-down",
        "신규": "card-status-new",
        "유지": "card-status-keep",
    }.get(status, "card-status-keep")
    st.markdown(
        f"""
        <div class="card-status-marker {marker_class}"></div>
        <div class="card-status-row">
            <span class="status-pill {class_name}">{html.escape(status)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_color_value(tag):
    if tag.get("color") == "기타":
        return tag.get("color_other") or "기타"
    return tag.get("color") or "미입력"


def display_mood_value(tag):
    if tag.get("mood") == "기타":
        return tag.get("mood_other") or "기타"
    return tag.get("mood") or "미입력"


def display_edge_value(tag):
    if tag.get("edge") == "기타":
        return tag.get("edge_other") or "기타"
    return tag.get("edge") or "미입력"


def count_values(tags, value_func):
    counts = {}
    for tag in tags:
        value = value_func(tag)
        if value and value != "미입력":
            counts[value] = counts.get(value, 0) + 1
    return counts


def format_counts(counts):
    if not counts:
        return "입력값 없음"
    ordered = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return " / ".join([f"{name} {count}개" for name, count in ordered])


def clean_trend_value(value):
    value = str(value or "").strip()
    return "" if value in ["", "미입력", "nan", "None"] else value


def join_feature_phrase(row):
    features = [
        clean_trend_value(row.get("color")),
        clean_trend_value(row.get("mood")),
        clean_trend_value(row.get("edge")),
    ]
    features = [value for value in features if value]
    return " / ".join(features)


def get_rank_movement_notes(config):
    history = load_trend_history()
    if history.empty:
        return []

    history = history[
        (history["country"] == config["label"])
        & (history["source"] == config["source"])
    ].copy()
    if history.empty:
        return []

    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["rank"] = pd.to_numeric(history["rank"], errors="coerce")
    history = history.dropna(subset=["date", "rank"])
    saved_dates = sorted(history["date"].dropna().dt.date.unique())
    if len(saved_dates) < 2:
        return []

    previous_date = saved_dates[-2]
    latest_date = saved_dates[-1]
    previous = history[history["date"].dt.date == previous_date].copy()
    latest = history[history["date"].dt.date == latest_date].copy()
    if previous.empty or latest.empty:
        return []

    previous_map = {
        row["href"]: row
        for _, row in previous.iterrows()
        if clean_trend_value(row.get("href"))
    }
    rising = []
    falling = []
    new_entries = []

    for _, row in latest.sort_values("rank").iterrows():
        href = clean_trend_value(row.get("href"))
        prev_row = previous_map.get(href)
        current_rank = int(row["rank"])
        feature_phrase = join_feature_phrase(row)
        product = trend_product_name(row.get("product", ""))

        if prev_row is None:
            new_entries.append((current_rank, product, feature_phrase))
            continue

        previous_rank = int(prev_row["rank"])
        move = previous_rank - current_rank
        if move > 0:
            rising.append((move, previous_rank, current_rank, product, feature_phrase))
        elif move < 0:
            falling.append((abs(move), previous_rank, current_rank, product, feature_phrase))

    notes = []
    if new_entries:
        rank, product, features = new_entries[0]
        feature_text = f" ({features})" if features else ""
        notes.append(f"신규 진입한 {product}가 {rank}위에 올라오며 새로운 선택 흐름을 만들고 있습니다{feature_text}.")

    if rising:
        _, old_rank, new_rank, product, features = sorted(rising, reverse=True)[0]
        feature_text = f" {features} 조합이" if features else " 해당 제품의 디자인이"
        notes.append(f"{product}는 {old_rank}위에서 {new_rank}위로 상승해,{feature_text} 상위권에서 더 강하게 반응하고 있습니다.")

    if falling:
        _, old_rank, new_rank, product, features = sorted(falling, reverse=True)[0]
        feature_text = f" {features} 조합은" if features else " 해당 제품은"
        notes.append(f"{product}는 {old_rank}위에서 {new_rank}위로 내려가,{feature_text} 이전보다 선택 강도가 약해진 흐름입니다.")

    return notes


def generate_trend_text(top_tags, config, date_label=None):
    if date_label:
        today_text = date_label
    else:
        now = datetime.now()
        today_text = f"{now.year}년 {now.month}월 {now.day}일"

    color_counts = count_values(top_tags, display_color_value)
    mood_counts = count_values(top_tags, display_mood_value)
    edge_counts = count_values(top_tags, display_edge_value)
    label = config["label"]
    source = config["source"]

    if not color_counts and not mood_counts and not edge_counts:
        return (
            f"{today_text} 기준 {label} {source} 컬러렌즈 TOP 6 랭킹의 컬러, 무드, 엣지를 입력하면, "
            "입력값을 기반으로 디자인 트렌드 문장이 자동으로 생성됩니다."
        )

    main_color = max(color_counts, key=color_counts.get) if color_counts else None
    main_color_count = color_counts.get(main_color, 0) if main_color else 0
    mood_summary = format_counts(mood_counts)
    edge_summary = format_counts(edge_counts)
    color_summary = format_counts(color_counts)
    soft_count = mood_counts.get("네추럴/소프트", 0)
    point_moods = [s for s in ["글로우/하이라이트", "화려함/컬러풀", "딥/클래식"] if s in mood_counts]
    point_edges = [s for s in ["볼드링", "라인 엣지", "슬림링"] if s in edge_counts]
    movement_notes = get_rank_movement_notes(config)

    if main_color:
        paragraph_1 = f"컬러|TOP 6에서는 {main_color} 계열이 가장 눈에 띕니다.\n컬러 구성: {color_summary}"
    else:
        paragraph_1 = f"컬러|{today_text} 기준 {label} TOP 6에서 컬러 입력값은 아직 충분하지 않습니다."

    color_forecast = ""
    if main_color and main_color_count >= 2:
        color_forecast = f"최근 상위권 흐름에서는 {main_color}처럼 부담 없이 쓰기 좋은 컬러가 안정적으로 선택되고 있습니다."
    elif main_color:
        color_forecast = f"컬러가 한쪽으로 크게 쏠리지는 않아, 여러 색상이 함께 선택되는 흐름으로 볼 수 있습니다."

    paragraph_2 = ""
    if mood_counts or edge_counts:
        paragraph_2 = f"디자인|무드: {mood_summary}\n엣지: {edge_summary}\n"
        if soft_count > 0 and (point_moods or point_edges):
            paragraph_2 += (
                "자연스러운 데일리 스타일이 기본입니다.\n"
                f"{'·'.join((point_moods + point_edges)[:4])} 같은 포인트 요소도 함께 보입니다."
            )
        elif soft_count > 0:
            paragraph_2 += "전반적으로 자연스럽고 부드러운 인상이 선호되고 있습니다."
        elif point_moods or point_edges:
            paragraph_2 += f"{'·'.join((point_moods + point_edges)[:4])}처럼 눈매를 또렷하게 보여주는 디자인이 주요 흐름입니다."

    forecast_parts = [part for part in [color_forecast] if part]
    forecast_parts.extend(movement_notes)
    if soft_count > 0 and (point_moods or point_edges):
        forecast_parts.append("최근 흐름상 자연스러운 베이스에 은은한 하이라이트나 또렷한 라인을 더한 제품이 계속 주목받을 가능성이 있습니다.")
    elif soft_count > 0:
        forecast_parts.append("최근 흐름상 일상에서 쓰기 쉬운 자연스러운 렌즈가 안정적으로 선호될 가능성이 있습니다.")
    elif point_moods or point_edges:
        forecast_parts.append("최근 흐름상 색감이나 라인이 조금 더 분명한 포인트형 렌즈가 주목받을 가능성이 있습니다.")
    else:
        forecast_parts.append("최근 흐름상 상위권에 반복해서 등장하는 컬러와 디자인이 다음 트렌드의 기준이 될 가능성이 있습니다.")

    paragraph_3 = "트렌드|" + "\n".join(forecast_parts)

    return f"{paragraph_1}\n\n{paragraph_2}\n\n{paragraph_3}"


def format_trend_html(trend_text, vertical=False):
    cards = []
    for block in str(trend_text).split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if "|" in block:
            label, body = block.split("|", 1)
            body_lines = []
            chip_html = ""
            for line in body.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if ":" in line and "/" in line:
                    prefix, values = line.split(":", 1)
                    chips = [
                        f'<span class="trend-chip">{html.escape(item.strip())}</span>'
                        for item in values.split("/")
                        if item.strip()
                    ]
                    chip_html += (
                        '<div class="trend-chip-row">'
                        f'<span class="trend-chip-label">{html.escape(prefix.strip())} :</span>'
                        f'{"".join(chips)}'
                        '</div>'
                    )
                else:
                    body_lines.append(f'<p class="trend-body-line">{html.escape(line)}</p>')
            cards.append(
                '<div class="trend-card">'
                f'<span class="trend-label">{html.escape(label.strip())}</span>'
                f'<div class="trend-body">{"".join(body_lines)}{chip_html}</div>'
                '</div>'
            )
        else:
            cards.append(f'<div class="trend-card"><div class="trend-body">{html.escape(block).replace(chr(10), "<br>")}</div></div>')
    grid_class = "trend-grid trend-grid-vertical" if vertical else "trend-grid"
    return f'<div class="{grid_class}">{"".join(cards)}</div>'


def prepare_dataframe(filename, config):
    df = pd.DataFrame(load_rows(filename))
    if df.empty:
        return df

    df["rank"] = df["rank"].astype(int)
    df["href"] = df["href"].astype(str).apply(lambda href: normalize_href(href, config))
    return df.sort_values("rank").reset_index(drop=True)


def render_country_home():
    japan = COUNTRIES["japan"]
    sources = [
        ("01", "Morecon", "https://morecon.jp/", "기존 분석 연결", "모어콘 원데이 TOP 6와 디자인 태그, 순위 변화를 확인합니다.", "?country=japan", "대시보드 열기", True),
        ("02", "Queen Eyes", "https://www.queen-eyes.com/", "분석 연결", "Queen Eyes 1day 인기 TOP 6와 디자인 태그, 순위 변화를 확인합니다.", "?country=queen_eyes", "대시보드 열기", True),
        ("03", "Hotel Lovers", "https://hotellovers.jp/", "수집 준비", "일본 컬러렌즈 상품 랭킹과 신상품 흐름을 수집할 예정입니다.", "https://hotellovers.jp/", "사이트 열기", False),
        ("04", "Rakuten Daily", "https://ranking.rakuten.co.jp/daily/408099/", "수집 준비", "라쿠텐 데일리 랭킹을 추가해 대형몰 기준의 변화를 비교할 예정입니다.", "https://ranking.rakuten.co.jp/daily/408099/", "사이트 열기", False),
    ]
    cards = []
    for index, name, url, status, description, href, action, active in sources:
        status_class = "" if active else " pending"
        active_class = " active" if active else ""
        cards.append(
            f"""
            <div class="source-card{active_class}" style="display:flex; align-items:center; gap:1.2rem; min-width:0; min-height:132px; padding:1.35rem 0; border:0; border-bottom:1px solid #dfe5ef; border-radius:0; background:transparent; box-shadow:none;">
                <div class="source-card-top" style="display:flex; align-items:center; justify-content:space-between; gap:1rem; flex:0 1 275px; min-width:0;">
                    <div>
                        <div class="source-index" style="color:#3e77d3; font-size:.86rem; font-weight:900; letter-spacing:.06em;">SOURCE {index}</div>
                        <div class="source-name" style="margin:.25rem 0 .35rem; color:#263044; font-size:1.25rem; font-weight:900;">{name}</div>
                        <a class="source-url" href="{url}" target="_blank" rel="noopener noreferrer" style="display:inline-block; color:#7b8492; font-size:.76rem; overflow-wrap:anywhere; text-decoration:none; border-bottom:1px solid transparent;">{url}</a>
                    </div>
                    <span class="source-status{status_class}" style="flex:0 0 auto; padding:.28rem .55rem; border-radius:999px; background:{'#eaf1ff' if active else '#eef1f5'}; color:{'#3e6db8' if active else '#697386'}; font-size:.7rem; font-weight:900;">{status}</span>
                </div>
                <div class="source-description" style="flex:1 1 auto; min-width:0; margin:0; color:#5f6877; font-size:.9rem; line-height:1.55;">{description}</div>
                <a class="source-action" style="flex:0 0 auto; display:inline-block; min-width:88px; padding:.48rem .72rem; border:1px solid #c7d3e8; border-radius:4px; color:#46669a; font-size:.8rem; font-weight:900; text-align:center; text-decoration:none; white-space:nowrap;" href="{href}" target="{'_self' if active else '_blank'}">{action}</a>
            </div>
            """.strip()
        )
    st.markdown(
        f"""
        <div class="home-layout" style="display:grid; grid-template-columns:40% minmax(0,1fr); gap:3.5rem; align-items:stretch;">
            <div style="min-height:850px; padding:125px 2.8rem 3.2rem; background:#eaf0ff; border-radius:8px; display:flex; flex-direction:column; justify-content:flex-start;">
                <div style="margin-bottom:1.2rem; color:#3e77d3; font-size:0.78rem; font-weight:900; letter-spacing:0.12em;">JAPAN / DAILY RESEARCH</div>
                <div style="color:#536eaf; font-size:44px; font-weight:800; line-height:1.18; word-break:keep-all;">일본 컬러렌즈 트렌드</div>
                <div style="margin-top:0.8rem; color:#66738d; font-size:0.86rem; font-weight:700;">온라인 랭킹 수집</div>
                <div style="width:3.5rem; height:3px; margin-top:2rem; background:#5e82d1;"></div>
            </div>
            <div style="min-width:0; padding-top:2.2rem;">
                <div style="margin-bottom:1.4rem; color:#263044; font-size:1.35rem; font-weight:900; letter-spacing:0.02em;">Contents</div>
                <div class="source-grid" style="display:grid; grid-template-columns:minmax(0,1fr); gap:0; width:100%; margin-left:0;">{"".join(cards)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_update(config):
    if os.path.exists(config["today_file"]):
        shutil.copy(config["today_file"], config["yesterday_file"])

    return subprocess.run(
        [sys.executable, config["script"]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def render_collection_help(config):
    if config["label"] != "태국":
        st.info("아직 수집된 데이터가 없습니다. 오늘 데이터 업데이트를 눌러 주세요.")
        return

    st.warning(config["empty_message"])
    st.markdown(
        """
        **태국 Shopee 수집 순서**

        1. `오늘 데이터 업데이트`를 누릅니다.
        2. 열린 Shopee 브라우저에서 로그인합니다.
        3. `color lens` 검색 결과가 보이면 그대로 기다립니다.
        4. 수집이 끝나면 `thailand_today.csv`가 생성되고 화면에 TOP 6이 표시됩니다.
        """
    )

    if os.path.exists("debug_thailand_shopee_area.png"):
        with st.expander("마지막 Shopee 수집 화면 확인"):
            st.image("debug_thailand_shopee_area.png", use_container_width=True)


def summarize_series(df, column):
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "count"])

    clean = df[df[column].fillna("").astype(str).str.strip().ne("")]
    clean = clean[clean[column] != "미입력"]
    if clean.empty:
        return pd.DataFrame(columns=[column, "count"])

    return clean.groupby(column).size().reset_index(name="count").sort_values("count", ascending=False)


def render_count_table(title, df, column):
    st.markdown(f'<div class="summary-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    counts = summarize_series(df, column)
    if counts.empty:
        st.caption("누적된 입력값이 없습니다.")
        return
    st.dataframe(counts, use_container_width=True, hide_index=True)


def first_count_label(df, column):
    counts = summarize_series(df, column)
    if counts.empty:
        return "입력값 없음"
    first = counts.iloc[0]
    return f"{first[column]} {int(first['count'])}건"


def render_trend_summary(config, period_label, period_df, start_date, end_date):
    color_top = first_count_label(period_df, "color")
    mood_top = first_count_label(period_df, "mood")
    edge_top = first_count_label(period_df, "edge")
    snapshot_count = period_df["date"].nunique()
    product_count = len(period_df)

    repeated_text = "반복 노출 제품 없음"
    if not period_df.empty:
        product_counts = (
            period_df.groupby("product")
            .size()
            .reset_index(name="count")
            .sort_values(["count", "product"], ascending=[False, True])
        )
        if not product_counts.empty:
            top_product = product_counts.iloc[0]
            repeated_text = f"{short_name(top_product['product'], 34)} {int(top_product['count'])}회"

    st.markdown(
        f"""
        <div class="summary-box">
            <div class="summary-title">{config['label']} {period_label} Summary</div>
            <div class="summary-text">
                기간 {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} / 저장 스냅샷 {snapshot_count}일 / 상품 기록 {product_count}건<br>
                대표 컬러: {html.escape(color_top)}<br>
                대표 무드: {html.escape(mood_top)}<br>
                대표 엣지: {html.escape(edge_top)}<br>
                반복 노출: {html.escape(repeated_text)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_snapshot_calendar(config, date_options):
    available_dates = set(date_options)
    min_date = min(date_options)
    max_date = max(date_options)
    month_key = f"{config['key']}_calendar_month"
    popup_key = f"{config['key']}_calendar_popup_date"

    if month_key not in st.session_state:
        st.session_state[month_key] = max_date.replace(day=1)

    current_month = st.session_state[month_key]

    min_month = min_date.replace(day=1)
    max_month = max_date.replace(month=12, day=1)
    if current_month < min_month:
        current_month = min_month
    if current_month > max_month:
        current_month = max_month

    def month_shift(month, offset):
        month_number = month.month + offset
        year = month.year + (month_number - 1) // 12
        month_number = (month_number - 1) % 12 + 1
        return month.replace(year=year, month=month_number)

    prev_month = month_shift(current_month, -1)
    next_month = month_shift(current_month, 1)

    month_names = [
        "JANUARY",
        "FEBRUARY",
        "MARCH",
        "APRIL",
        "MAY",
        "JUNE",
        "JULY",
        "AUGUST",
        "SEPTEMBER",
        "OCTOBER",
        "NOVEMBER",
        "DECEMBER",
    ]

    with st.container(key=f"snapshot_calendar_{config['key']}"):
        prev_col, title_col, next_col = st.columns([0.12, 0.76, 0.12])
        with prev_col:
            if st.button("‹", key=f"calendar_nav_prev_{config['key']}", disabled=current_month <= min_month, use_container_width=True):
                st.session_state[month_key] = prev_month
                st.rerun()
        with title_col:
            st.markdown(
                f"""
                <div class="calendar-title">
                    <div class="calendar-selected-day">{current_month.month}</div>
                    <div class="calendar-selected-rule"></div>
                    <div class="calendar-month-name">{month_names[current_month.month - 1]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with next_col:
            if st.button("›", key=f"calendar_nav_next_{config['key']}", disabled=current_month >= max_month, use_container_width=True):
                st.session_state[month_key] = next_month
                st.rerun()

        weekday_cols = st.columns(7)
        for index, label in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
            sun_class = " is-sun" if index == 0 else ""
            with weekday_cols[index]:
                st.markdown(f'<div class="calendar-weekday{sun_class}">{label}</div>', unsafe_allow_html=True)

        month_calendar = calendar.Calendar(firstweekday=6)
        for week_index, week in enumerate(month_calendar.monthdayscalendar(current_month.year, current_month.month)):
            day_cols = st.columns(7)
            for day_index, day in enumerate(week):
                with day_cols[day_index]:
                    if day == 0:
                        st.markdown('<div class="calendar-empty"></div>', unsafe_allow_html=True)
                        continue

                    day_date = current_month.replace(day=day)
                    is_available = day_date in available_dates
                    popup_date = st.session_state.get(popup_key)
                    active = day_date == popup_date
                    if is_available:
                        key_parts = ["calendar_day_text"]
                        if day_index == 0:
                            key_parts.append("sun")
                        if active:
                            key_parts.append("active")
                        key_parts.extend([config["key"], current_month.strftime("%Y_%m"), str(week_index), str(day)])
                        if st.button(str(day), key="_".join(key_parts), use_container_width=True):
                            st.session_state[popup_key] = day_date
                    else:
                        st.markdown(f'<div class="calendar-day is-unavailable"><span>{day}</span></div>', unsafe_allow_html=True)

    return max_date, st.session_state.get(popup_key)


def render_daily_snapshot(config, selected_date, daily_df):
    date_label = f"{selected_date.year}년 {selected_date.month}월 {selected_date.day}일"
    st.markdown(f'<div class="section-title">선택 날짜 일일 트렌드</div>', unsafe_allow_html=True)

    if daily_df.empty:
        st.info(f"{selected_date.strftime('%Y-%m-%d')}에 저장된 일일 트렌드 스냅샷이 없습니다.")
        return

    daily_df = daily_df.sort_values("rank").copy()
    st.markdown(
        f"""
        <div class="trend-box">
            <div class="trend-text">{format_trend_html(generate_trend_text(daily_df.to_dict("records"), config, date_label))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rank_summary = daily_df[["rank", "product", "color", "mood", "edge"]].copy()
    rank_summary["product"] = rank_summary["product"].apply(lambda value: short_name(value, 54))
    rank_summary = rank_summary.rename(
        columns={
            "rank": "순위",
            "product": "제품",
            "color": "컬러",
            "mood": "무드",
            "edge": "엣지",
        }
    )
    st.markdown('<div class="summary-title">간략 순위</div>', unsafe_allow_html=True)
    st.dataframe(rank_summary, use_container_width=True, hide_index=True)


def render_daily_snapshot_popup(config, selected_date, daily_df):
    @st.dialog(f"{selected_date.strftime('%Y-%m-%d')} 일일 트렌드", width="large")
    def popup():
        render_daily_snapshot(config, selected_date, daily_df)
        if st.button("닫기", use_container_width=True):
            popup_key = f"{config['key']}_calendar_popup_date"
            if popup_key in st.session_state:
                del st.session_state[popup_key]
            st.rerun()

    popup()


def build_product_image_map(config):
    image_map = {}
    target_files = [config["today_file"], config["yesterday_file"]]
    archive_prefix = f"{config['archive_prefix']}_"
    target_files.extend(
        sorted(
            filename
            for filename in os.listdir(".")
            if filename.startswith(archive_prefix) and filename.endswith(".csv")
        )
    )

    for filename in target_files:
        for row in load_rows(filename):
            href = normalize_href(row.get("href", ""), config)
            image_url = clean_url(row.get("image_url", ""), config)
            if href and image_url and href not in image_map:
                image_map[href] = image_url

    return image_map


def render_repeated_products(config, history, end_date):
    st.markdown('<div class="section-title">상위권 반복 노출 제품</div>', unsafe_allow_html=True)
    st.caption("선택한 기준일까지 저장된 전체 일별 스냅샷을 누적해서 계산합니다.")

    cumulative_product_df = history[history["date"] <= end_date].copy()
    if cumulative_product_df.empty:
        st.info("선택한 기준일까지 누적된 제품 기록이 없습니다.")
        return

    product_counts = (
        cumulative_product_df.groupby(["product", "href"])
        .agg(노출횟수=("href", "size"), 평균순위=("rank", "mean"), 최고순위=("rank", "min"))
        .reset_index()
        .sort_values(["노출횟수", "최고순위"], ascending=[False, True])
    )
    product_counts["평균순위"] = product_counts["평균순위"].round(1)

    image_map = build_product_image_map(config)
    body = '<div class="repeat-panel"><div class="repeat-list">'
    for index, (_, row) in enumerate(product_counts.head(8).iterrows(), start=1):
        href = str(row["href"])
        image_url = image_map.get(href, "")
        thumb = (
            f'<img class="repeat-thumb" src="{html.escape(image_url, quote=True)}" alt="">'
            if image_url
            else '<div class="repeat-thumb"></div>'
        )
        body += (
            '<div class="repeat-item">'
            f'<div class="repeat-rank">{index}</div>'
            f"{thumb}"
            '<div>'
            f'<a class="repeat-name" href="{html.escape(href, quote=True)}" target="_blank">{html.escape(short_name(row["product"], 48))}</a>'
            '<div class="repeat-meta">'
            f'<span class="repeat-pill">노출 {int(row["노출횟수"])}회</span>'
            f'<span class="repeat-pill">평균 {row["평균순위"]}위</span>'
            f'<span class="repeat-pill">최고 {int(row["최고순위"])}위</span>'
            '</div>'
            '</div>'
            '</div>'
        )
    body += '</div></div>'
    st.markdown(body, unsafe_allow_html=True)


def render_period_analysis(config, history, selected_date, end_date):
    st.markdown('<div class="section-title">누적 분석</div>', unsafe_allow_html=True)
    st.caption("`컬러/무드/엣지 저장` 버튼으로 저장된 일별 스냅샷 기준으로 업데이트됩니다.")

    period_label = st.segmented_control("분석 기간", ["일일", "주간", "월간", "분기", "년간"], default="일일")

    if period_label == "일일":
        start_date = pd.Timestamp(selected_date)
        period_df = history[history["date"].dt.date == selected_date].copy()
    else:
        days = {"주간": 7, "월간": 30, "분기": 90, "년간": 365}[period_label]
        start_date = end_date - timedelta(days=days - 1)
        period_df = history[(history["date"] >= start_date) & (history["date"] <= end_date)].copy()

    st.markdown(
        f"""
        <div class="summary-box">
            <div class="summary-title">{config['label']} {period_label} 누적 기준</div>
            <div class="summary-text">
                {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}<br>
                저장 스냅샷 {period_df['date'].nunique()}일 / 상품 기록 {len(period_df)}건
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if period_df.empty:
        st.info("선택한 기간에 누적된 데이터가 없습니다.")
        return

    top_tags = period_df.to_dict("records")
    if period_label != "일일":
        st.markdown(f'<div class="section-title">{period_label} 트렌드</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="trend-box">
                <div class="trend-text">{format_trend_html(generate_trend_text(top_tags, config), vertical=True)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_trend_summary(config, period_label, period_df, start_date, end_date)

    render_count_table("컬러 트렌드", period_df, "color")
    render_count_table("무드 트렌드", period_df, "mood")
    render_count_table("엣지 트렌드", period_df, "edge")


def render_period_trend(config):
    history = load_trend_history()
    if history.empty:
        st.info("아직 누적된 트렌드 데이터가 없습니다. 오늘 랭킹에서 컬러/무드/엣지를 저장하면 이곳에 쌓입니다.")
        return

    history = history[
        (history["country"] == config["label"])
        & (history["source"] == config["source"])
    ].copy()
    if history.empty:
        st.info(f"{config['label']} 누적 데이터가 아직 없습니다. 오늘 랭킹에서 컬러/무드/엣지를 저장해 주세요.")
        return

    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history = history.dropna(subset=["date"])
    if history.empty:
        st.info("누적 데이터의 날짜를 읽을 수 없습니다.")
        return

    date_options = sorted(history["date"].dt.date.unique())
    date_col, analysis_col = st.columns([0.61, 0.39], gap="small")
    with date_col:
        st.markdown('<div class="section-title">날짜 선택</div>', unsafe_allow_html=True)
        selected_date, popup_date = render_snapshot_calendar(config, date_options)
        end_date = pd.Timestamp(selected_date)
        render_repeated_products(config, history, end_date)
    with analysis_col:
        render_period_analysis(config, history, selected_date, end_date)

    if popup_date:
        popup_df = history[history["date"].dt.date == popup_date].copy()
        render_daily_snapshot_popup(config, popup_date, popup_df)


def render_card(row, config, manual_tags, status_map):
    product = row["product"]
    rank = int(row["rank"])
    image = clean_url(row.get("image_url", ""), config)
    eye_image = clean_url(row.get("eye_image_url", ""), config) or derive_eye_image_url(image, config)
    href = normalize_href(row.get("href", ""), config)
    status = status_map.get(href, "유지")
    status_key = {
        "상승": "up",
        "하락": "down",
        "신규": "new",
        "유지": "keep",
    }.get(status, "keep")
    spec = get_japan_product_spec(href) if config["show_specs"] else {}

    tag = manual_tags.get(
        href,
        {
            "color": "",
            "color_other": "",
            "mood": "",
            "mood_other": "",
            "edge": "",
            "edge_other": "",
        },
    )

    with st.container(border=True, key=f"rank-card-{status_key}-{config['key']}-{rank}"):
        render_status(status)
        st.markdown(f'<div class="rank-badge">#{rank}</div>', unsafe_allow_html=True)

        img_col, info_col = st.columns([1.05, 0.95], gap="small")

        with img_col:
            if image:
                st.image(image, use_container_width=True)
            if eye_image:
                st.image(eye_image, caption="착용 눈 이미지", use_container_width=True)

        with info_col:
            if config["show_specs"]:
                spec_cell("DIA", spec["DIA"])
                spec_cell("G.DIA", spec["G.DIA"])
                spec_cell("BC", spec["BC"])
                spec_cell("사용기간", spec["PERIOD"])
            else:
                spec_cell("국가", config["label"])
                spec_cell("소스", config["source"])
                spec_cell("기준", "판매순")
                spec_cell("키워드", "color lens")

        st.markdown(f'<div class="product-name">{html.escape(short_name(product))}</div>', unsafe_allow_html=True)

        color_index = COLOR_OPTIONS.index(tag["color"]) if tag.get("color") in COLOR_OPTIONS else 0
        selected_color = st.selectbox("렌즈 컬러", COLOR_OPTIONS, index=color_index, key=f"color_{config['label']}_{href}")

        color_other = tag.get("color_other", "")
        if selected_color == "기타":
            color_other = st.text_input("기타 컬러 입력", value=color_other, key=f"color_other_{config['label']}_{href}")

        mood_index = MOOD_OPTIONS.index(tag["mood"]) if tag.get("mood") in MOOD_OPTIONS else 0
        selected_mood = st.selectbox("무드", MOOD_OPTIONS, index=mood_index, key=f"mood_{config['label']}_{href}")

        mood_other = tag.get("mood_other", "")
        if selected_mood == "기타":
            mood_other = st.text_input("기타 무드 입력", value=mood_other, key=f"mood_other_{config['label']}_{href}")

        edge_index = EDGE_OPTIONS.index(tag["edge"]) if tag.get("edge") in EDGE_OPTIONS else 0
        selected_edge = st.selectbox("엣지", EDGE_OPTIONS, index=edge_index, key=f"edge_{config['label']}_{href}")

        edge_other = tag.get("edge_other", "")
        if selected_edge == "기타":
            edge_other = st.text_input("기타 엣지 입력", value=edge_other, key=f"edge_other_{config['label']}_{href}")

        manual_tags[href] = {
            "color": selected_color,
            "color_other": color_other,
            "mood": selected_mood,
            "mood_other": mood_other,
            "edge": selected_edge,
            "edge_other": edge_other,
            "style": tag.get("style", ""),
            "style_other": tag.get("style_other", ""),
        }

        st.link_button("상품 페이지 이동", href, use_container_width=True)


def render_country_dashboard(country_key):
    config = COUNTRIES[country_key]

    if country_key == "queen_eyes":
        st.markdown(
            """
            <style>
            :root {
                --paper:#fff9fb;
                --panel:#fffcfd;
                --ink:#342633;
                --muted:#877380;
                --peach:#efb3c5;
                --peach-deep:#cb7894;
                --peach-soft:#fff0f5;
                --peach-line:#f2d3dc;
                --shadow:0 14px 32px rgba(191,103,132,0.09);
            }
            .stApp,
            [data-testid="stAppViewContainer"] { background:#fff9fb; }
            .trend-chip,
            .repeat-pill { background:#fff0f5 !important; border-color:#f0cfda !important; color:#805064 !important; }
            .metric-card,
            .summary-box { background:#fffafd; }
            div.stButton > button:hover { color:#b84670; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    manual_tags = load_manual_tags(config)
    header_class = f"page-head-{country_key}"
    last_update = format_last_update(config["today_file"])
    seed_country_back_history(country_key)

    st.markdown(
        f"""
        <div class="page-head {header_class}">
            <div class="page-head-row">
                <div class="page-head-copy">
                <div class="main-title">{config.get("title", config["label"])} 컬러렌즈 트렌드 대시보드</div>
                    <div class="main-subtitle">{config["subtitle"]}</div>
                </div>
                <div class="header-update">
                    <div class="header-update-label">최근 업데이트</div>
                    <div class="header-update-time">{html.escape(last_update)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_col, update_col, _ = st.columns([0.16, 0.18, 0.66])
    with nav_col:
        st.link_button("온라인몰 선택", "/", use_container_width=True)

    with update_col:
        if st.button("오늘 데이터 업데이트", use_container_width=True):
            if config["label"] == "태국":
                st.info("Shopee 브라우저가 열리면 로그인 후 검색 결과 화면이 보일 때까지 기다려 주세요.")
            with st.spinner("데이터를 수집하는 중입니다."):
                result = run_update(config)
                if result.returncode == 0:
                    updated_df = prepare_dataframe(config["today_file"], config)
                    saved_count = save_trend_snapshot(config, updated_df, manual_tags)
                    st.success("업데이트 완료")
                    if saved_count:
                        st.caption(f"오늘 트렌드 스냅샷 {saved_count}건도 누적 페이지에 저장했습니다.")
                    st.rerun()
                else:
                    st.error("업데이트 중 오류가 발생했습니다.")
                    st.text((result.stdout + "\n" + result.stderr).strip())
                    if config["label"] == "태국" and os.path.exists("debug_thailand_shopee_area.png"):
                        st.image("debug_thailand_shopee_area.png", caption="마지막 Shopee 수집 화면", use_container_width=True)

    df_today = prepare_dataframe(config["today_file"], config)
    df_yesterday = prepare_dataframe(config["yesterday_file"], config)
    status_map = build_status_map(df_today, df_yesterday)

    view_mode = st.radio("보기", ["오늘 랭킹", "누적 트렌드"], horizontal=True, label_visibility="collapsed")
    if view_mode == "누적 트렌드":
        render_period_trend(config)
        return

    top_tags = []
    if not df_today.empty:
        for _, row in df_today.head(6).iterrows():
            top_tags.append(manual_tags.get(row["href"], {}))

    color_counts = count_values(top_tags, display_color_value)
    mood_counts = count_values(top_tags, display_mood_value)
    edge_counts = count_values(top_tags, display_edge_value)
    trend_text = generate_trend_text(top_tags, config)

    if not df_today.empty:
        st.markdown('<div class="section-title">디자인 트렌드</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="trend-box">
                <div class="trend-text">
                    {format_trend_html(trend_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    left, right = st.columns([2.3, 1.0], gap="large")

    with left:
        st.markdown('<div class="section-title">TOP 6 순위</div>', unsafe_allow_html=True)
        top_rows = df_today.head(6).to_dict("records") if not df_today.empty else []

        if not top_rows:
            render_collection_help(config)
        else:
            row1 = st.columns(3, gap="medium")
            row2 = st.columns(3, gap="medium")

            for i, row in enumerate(top_rows[:3]):
                with row1[i]:
                    render_card(row, config, manual_tags, status_map)

            for i, row in enumerate(top_rows[3:6]):
                with row2[i]:
                    render_card(row, config, manual_tags, status_map)

    with right:
        st.markdown('<div class="section-title">요약</div>', unsafe_allow_html=True)

        def metric_card(label, value):
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        a, b = st.columns(2)
        with a:
            metric_card("상승", sum(1 for s in status_map.values() if s == "상승"))
        with b:
            metric_card("하락", sum(1 for s in status_map.values() if s == "하락"))

        c, d = st.columns(2)
        with c:
            metric_card("유지", sum(1 for s in status_map.values() if s == "유지"))
        with d:
            metric_card("신규", sum(1 for s in status_map.values() if s == "신규"))

        render_change_summary("상승 제품", build_rank_change_rows(df_today, df_yesterday, status_map, "상승"))
        render_change_summary("하락 제품", build_rank_change_rows(df_today, df_yesterday, status_map, "하락"))
        render_change_summary("신규 제품", build_rank_change_rows(df_today, df_yesterday, status_map, "신규"))

        st.markdown("")
        st.markdown('<div class="section-title">입력값 저장</div>', unsafe_allow_html=True)

        if st.button("컬러/무드/엣지 저장", use_container_width=True):
            save_manual_tags(manual_tags, config)
            saved_count = save_trend_snapshot(config, df_today, manual_tags)
            st.success(f"입력값이 저장되었습니다. 오늘 트렌드 스냅샷 {saved_count}건을 누적했습니다.")
            st.rerun()

        st.markdown(
            f"""
            <div class="summary-box">
                <div class="summary-title">컬러 요약</div>
                <div class="summary-text">{format_counts(color_counts)}</div>
            </div>
            <div class="summary-box">
                <div class="summary-title">무드 요약</div>
                <div class="summary-text">{format_counts(mood_counts)}</div>
            </div>
            <div class="summary-box">
                <div class="summary-title">엣지 요약</div>
                <div class="summary-text">{format_counts(edge_counts)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


country = get_query_country()
if country:
    render_country_dashboard(country)
else:
    render_country_home()
