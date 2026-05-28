import csv
import os
import re
import shutil
import subprocess
import sys

import requests
import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(
    page_title="일본 컬러렌즈 대시보드",
    layout="wide"
)

# -------------------------------
# 스타일
# -------------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1.5rem;
    padding-left: 1.4rem;
    padding-right: 1.4rem;
}

.main-title {
    font-size: 2.2rem;
    font-weight: 800;
    color: #1f2937;
    margin-bottom: 0.15rem;
    letter-spacing: -0.02em;
}

.main-subtitle {
    font-size: 0.95rem;
    color: #6b7280;
    margin-bottom: 1rem;
}

.section-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: #111827;
    margin-top: 0.5rem;
    margin-bottom: 0.8rem;
}

.fake-tab {
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 0.55rem 0.8rem;
    text-align: center;
    font-size: 0.92rem;
    color: #6b7280;
    background: #fafafa;
}

.rank-badge {
    font-size: 1.7rem;
    font-weight: 800;
    color: #111827;
    margin-bottom: 0.4rem;
}

.product-name {
    font-size: 1rem;
    font-weight: 700;
    color: #111827;
    line-height: 1.35;
    margin-top: 0.5rem;
    margin-bottom: 0.4rem;
    min-height: 2.7rem;
}

.product-meta {
    font-size: 0.9rem;
    color: #4b5563;
    margin-bottom: 0.6rem;
}

.spec-box {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 0.55rem 0.7rem;
    background: #f9fafb;
    font-size: 0.88rem;
    color: #111827;
    margin-bottom: 0.35rem;
}

.spec-label {
    color: #6b7280;
    font-size: 0.78rem;
    display: block;
    margin-bottom: 0.1rem;
}

.status-up {
    color: #15803d;
    font-size: 0.92rem;
    font-weight: 700;
    margin-top: 0.2rem;
    margin-bottom: 0.7rem;
}

.status-down {
    color: #b91c1c;
    font-size: 0.92rem;
    font-weight: 700;
    margin-top: 0.2rem;
    margin-bottom: 0.7rem;
}

.status-new {
    color: #b45309;
    font-size: 0.92rem;
    font-weight: 700;
    margin-top: 0.2rem;
    margin-bottom: 0.7rem;
}

.status-keep {
    color: #6b7280;
    font-size: 0.92rem;
    font-weight: 700;
    margin-top: 0.2rem;
    margin-bottom: 0.7rem;
}

.metric-box {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 0.9rem 1rem;
    background: white;
}

.metric-title {
    font-size: 0.82rem;
    color: #6b7280;
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #111827;
    line-height: 1;
}

.trend-box {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    background: white;
}

.trend-list {
    font-size: 1rem;
    line-height: 1.8;
    color: #1f2937;
    margin: 0;
    padding-left: 1.15rem;
}

div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
}

div[data-testid="stLinkButton"] a {
    border-radius: 10px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------
# 기본 함수
# -------------------------------
def load_rows(filename):
    rows = []
    if not os.path.exists(filename):
        return rows

    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def classify_product(name):
    name = str(name).lower()

    color = "기타"
    tone = "기타"
    style = "기타"

    if "brown" in name:
        color = "브라운"
    elif "beige" in name:
        color = "베이지"
    elif "gray" in name or "grey" in name:
        color = "그레이"
    elif "pink" in name:
        color = "핑크"

    if "baby" in name or "light" in name:
        tone = "라이트"
    elif "deep" in name or "dark" in name:
        tone = "딥"

    if "natural" in name:
        style = "내추럴"
    elif "glow" in name or "glowy" in name or "水光" in name:
        style = "물광"
    elif "churros" in name:
        style = "또렷함"

    return color, tone, style


def short_name(product, max_len=38):
    product = str(product)
    return product if len(product) <= max_len else product[:max_len] + "..."


@st.cache_data(show_spinner=False)
def get_product_spec(url):
    if not url:
        return {
            "DIA": "-",
            "G.DIA": "-",
            "BC": "-",
            "PERIOD": "-"
        }

    full_url = url if str(url).startswith("http") else f"https://morecon.jp{url}"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(full_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        def find_mm_after_keywords(keywords):
            for kw in keywords:
                pattern = rf"{re.escape(kw)}[^0-9]{{0,15}}([0-9]+(?:\.[0-9]+)?)\s*mm"
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    return f"{m.group(1)} mm"
            return "-"

        def find_plain_after_keywords(keywords):
            for kw in keywords:
                pattern = rf"{re.escape(kw)}[^0-9A-Za-z가-힣ァ-ヴー一-龥]{{0,15}}([0-9]+(?:\.[0-9]+)?)"
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    return m.group(1)
            return "-"

        dia = find_mm_after_keywords(["DIA", "렌즈 직경", "レンズ直径"])
        gdia = find_mm_after_keywords(["G.DIA", "着色直径", "착색 직경"])
        bc = find_plain_after_keywords(["BC", "렌즈 BC", "レンズBC"])
        if bc != "-":
            bc = f"{bc} mm"

        period = "-"
        low = text.lower()
        if "ワンデー" in text or "1day" in low or "원데이" in text:
            period = "원데이"
        elif "2week" in low or "2週間" in text or "2주" in text:
            period = "2주"
        elif "1month" in low or "1ヶ月" in text or "1개월" in text:
            period = "1개월"

        return {
            "DIA": dia,
            "G.DIA": gdia,
            "BC": bc,
            "PERIOD": period
        }

    except Exception:
        return {
            "DIA": "-",
            "G.DIA": "-",
            "BC": "-",
            "PERIOD": "-"
        }


def spec_cell(label, value):
    st.markdown(
        f"""
        <div class="spec-box">
            <span class="spec-label">{label}</span>
            {value}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status(status):
    if status == "상승":
        st.markdown('<div class="status-up">상승</div>', unsafe_allow_html=True)
    elif status == "하락":
        st.markdown('<div class="status-down">하락</div>', unsafe_allow_html=True)
    elif status == "신규":
        st.markdown('<div class="status-new">신규</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-keep">유지</div>', unsafe_allow_html=True)


def normalize_href(href):
    href = str(href).strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://morecon.jp{href}"
    return href


# -------------------------------
# 헤더
# -------------------------------
st.markdown('<div class="main-title">일본 컬러렌즈 대시보드</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">원데이 컬러렌즈 상위권 제품 구성을 시각적으로 확인하고 디자인 흐름을 정리합니다.</div>',
    unsafe_allow_html=True
)

# -------------------------------
# 업데이트 버튼
# -------------------------------
if st.button("오늘 데이터 업데이트"):
    if os.path.exists("today.csv"):
        shutil.copy("today.csv", "yesterday.csv")

    result = subprocess.run(
        [sys.executable, "app.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode == 0:
        st.success("업데이트 완료")
        st.rerun()
    else:
        st.error("오류 발생")
        st.text(result.stderr)

# -------------------------------
# CSV -> DataFrame
# -------------------------------
today_rows = load_rows("today.csv")
yesterday_rows = load_rows("yesterday.csv")

df_today = pd.DataFrame(today_rows)
df_yesterday = pd.DataFrame(yesterday_rows)

if not df_today.empty:
    df_today["rank"] = df_today["rank"].astype(int)
    df_today["href"] = df_today["href"].astype(str).apply(normalize_href)
    df_today = df_today.sort_values("rank").reset_index(drop=True)

if not df_yesterday.empty:
    df_yesterday["rank"] = df_yesterday["rank"].astype(int)
    df_yesterday["href"] = df_yesterday["href"].astype(str).apply(normalize_href)
    df_yesterday = df_yesterday.sort_values("rank").reset_index(drop=True)

# -------------------------------
# href 기준 상태 계산
# -------------------------------
status_map = {}

if not df_today.empty:
    yesterday_rank_map = {}
    if not df_yesterday.empty:
        yesterday_rank_map = dict(zip(df_yesterday["href"], df_yesterday["rank"]))

    for _, row in df_today.iterrows():
        href = row["href"]
        current_rank = int(row["rank"])

        if href not in yesterday_rank_map:
            status_map[href] = "신규"
        else:
            old_rank = int(yesterday_rank_map[href])
            if current_rank < old_rank:
                status_map[href] = "상승"
            elif current_rank > old_rank:
                status_map[href] = "하락"
            else:
                status_map[href] = "유지"

# -------------------------------
# 상단 탭 느낌
# -------------------------------
t1, t2, t3, t4 = st.columns(4)
with t1:
    st.markdown('<div class="fake-tab">원데이</div>', unsafe_allow_html=True)
with t2:
    st.markdown('<div class="fake-tab">월간</div>', unsafe_allow_html=True)
with t3:
    st.markdown('<div class="fake-tab">2주용</div>', unsafe_allow_html=True)
with t4:
    st.markdown('<div class="fake-tab">급상승</div>', unsafe_allow_html=True)

# -------------------------------
# 카드 렌더
# -------------------------------
def render_card(row):
    product = row["product"]
    rank = int(row["rank"])
    image = row.get("image_url", "")
    href = normalize_href(row.get("href", ""))
    status = status_map.get(href, "유지")

    color, tone, style = classify_product(product)
    spec = get_product_spec(href)

    with st.container(border=True):
        st.markdown(f'<div class="rank-badge">#{rank}</div>', unsafe_allow_html=True)

        img_col, info_col = st.columns([1.05, 0.95], gap="small")

        with img_col:
            if image:
                st.image(image, use_container_width=True)
            else:
                st.empty()

        with info_col:
            spec_cell("DIA", spec["DIA"])
            spec_cell("G.DIA", spec["G.DIA"])
            spec_cell("BC", spec["BC"])
            spec_cell("사용기간", spec["PERIOD"])
            spec_cell("톤", tone)
            spec_cell("스타일", style)

        st.markdown(
            f'<div class="product-name">{short_name(product)}</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            f'<div class="product-meta">{color} · {tone} · {style}</div>',
            unsafe_allow_html=True
        )

        render_status(status)
        st.link_button("상품 페이지 이동", href, use_container_width=True)

# -------------------------------
# 메인 레이아웃
# -------------------------------
left, right = st.columns([2.3, 1.0], gap="large")

with left:
    st.markdown('<div class="section-title">TOP 6 순위</div>', unsafe_allow_html=True)

    row1 = st.columns(3, gap="medium")
    row2 = st.columns(3, gap="medium")

    top_rows = df_today.head(6).to_dict("records") if not df_today.empty else []

    for i, row in enumerate(top_rows[:3]):
        with row1[i]:
            render_card(row)

    for i, row in enumerate(top_rows[3:6]):
        with row2[i]:
            render_card(row)

with right:
    st.markdown('<div class="section-title">요약</div>', unsafe_allow_html=True)

    up = sum(1 for s in status_map.values() if s == "상승")
    down = sum(1 for s in status_map.values() if s == "하락")
    keep = sum(1 for s in status_map.values() if s == "유지")
    new = sum(1 for s in status_map.values() if s == "신규")

    a, b = st.columns(2)
    with a:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">상승</div>
            <div class="metric-value">{up}</div>
        </div>
        """, unsafe_allow_html=True)
    with b:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">하락</div>
            <div class="metric-value">{down}</div>
        </div>
        """, unsafe_allow_html=True)

    c, d = st.columns(2)
    with c:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">유지</div>
            <div class="metric-value">{keep}</div>
        </div>
        """, unsafe_allow_html=True)
    with d:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">신규</div>
            <div class="metric-value">{new}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="section-title">디자인 트렌드</div>', unsafe_allow_html=True)

    trend_lines = [
        "자연스러운 브라운 계열이 상위권 중심을 유지하고 있습니다.",
        "하이라이트 요소가 포함된 제품이 상위권에서 확인됩니다.",
        "또렷한 인상을 주는 스타일이 일부 비중을 차지하고 있습니다."
    ]

    trend_html = "".join([f"<li>{line}</li>" for line in trend_lines])

    st.markdown(
        f"""
        <div class="trend-box">
            <ul class="trend-list">
                {trend_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )