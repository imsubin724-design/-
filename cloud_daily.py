"""Cloud runner for the daily Japan ranking update and HTML email."""

from __future__ import annotations

import argparse
import csv
import html
import os
import shutil
import smtplib
import subprocess
import sys
from collections import Counter
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
SOURCES = (
    {
        "name": "Morecon",
        "today": "today.csv",
        "yesterday": "yesterday.csv",
        "archive": "ranking_*.csv",
        "script": "app.py",
        "host": "https://morecon.jp",
        "tags": "manual_tags.csv",
    },
    {
        "name": "Queen Eyes",
        "today": "queen_eyes_today.csv",
        "yesterday": "queen_eyes_yesterday.csv",
        "archive": "ranking_queen_eyes_*.csv",
        "script": "app_queen_eyes.py",
        "host": "https://www.queen-eyes.com",
        "tags": "queen_eyes_manual_tags.csv",
    },
)
def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def full_url(value: str, host: str) -> str:
    value = (value or "").strip()
    return value if value.startswith("http") else f"{host}{value}"


def display_tag(tag: dict[str, str], field: str) -> str:
    value = (tag.get(field) or "").strip()
    if value == "기타":
        return (tag.get(f"{field}_other") or "기타").strip()
    return value or "미입력"


def analyze_source(source: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, Counter]]:
    today_rows = read_rows(ROOT / source["today"])
    yesterday_path = ROOT / source["yesterday"]
    yesterday_rows = read_rows(yesterday_path) if yesterday_path.exists() else []
    old_ranks = {
        full_url(row.get("href", ""), source["host"]): int(row["rank"])
        for row in yesterday_rows
    }
    tag_path = ROOT / source["tags"]
    tag_rows = read_rows(tag_path) if tag_path.exists() else []
    tags = {full_url(row.get("href", ""), source["host"]): row for row in tag_rows}
    counts = {field: Counter() for field in ("color", "mood", "edge")}
    analyzed = []
    for row in today_rows:
        item = dict(row)
        href = full_url(row.get("href", ""), source["host"])
        rank = int(row["rank"])
        old_rank = old_ranks.get(href)
        if old_rank is None:
            status, move = "신규", f"{rank}위 신규"
        elif rank < old_rank:
            status, move = "상승", f"{old_rank}위 → {rank}위"
        elif rank > old_rank:
            status, move = "하락", f"{old_rank}위 → {rank}위"
        else:
            status, move = "유지", f"{rank}위 유지"
        item.update(href=href, status=status, move=move)
        tag = tags.get(href, {})
        for field in counts:
            item[field] = display_tag(tag, field)
            if item[field] != "미입력":
                counts[field][item[field]] += 1
        analyzed.append(item)
    return analyzed, counts


def status_style(status: str) -> str:
    return {
        "신규": "background:#fff0d9;color:#9a5b00;border-color:#f0c985",
        "상승": "background:#eaf7ed;color:#16703a;border-color:#b9dfc5",
        "하락": "background:#fff0f0;color:#b43c3c;border-color:#f0b6b6",
    }.get(status, "background:#f4f6f9;color:#4b5563;border-color:#d8dee8")


def chips(counter: Counter) -> str:
    if not counter:
        return '<span style="color:#8b929e">입력값 없음</span>'
    return "".join(
        '<span style="display:inline-block;padding:5px 9px;margin:3px;border-radius:999px;'
        'background:#fff3f7;border:1px solid #f1ccd8;color:#74495a;font-size:12px;font-weight:700">'
        f'{html.escape(name)} {count}개</span>'
        for name, count in counter.most_common()
    )


def restore_yesterday(source: dict[str, str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    candidates = []
    for path in ROOT.glob(source["archive"]):
        if today not in path.stem:
            candidates.append(path)
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    if candidates:
        shutil.copy2(candidates[0], ROOT / source["yesterday"])
    elif (ROOT / source["today"]).exists():
        shutil.copy2(ROOT / source["today"], ROOT / source["yesterday"])


def collect() -> None:
    environment = os.environ.copy()
    environment["LENS_HEADLESS"] = "1"
    for source in SOURCES:
        restore_yesterday(source)
        subprocess.run(
            [sys.executable, source["script"]], cwd=ROOT, env=environment, check=True
        )
        rows = read_rows(ROOT / source["today"])
        if len(rows) != 6:
            raise RuntimeError(f"{source['name']} 수집 결과가 6개가 아닙니다: {len(rows)}개")


def build_report(cid_images: bool = False) -> tuple[str, list[tuple[str, bytes, str]]]:
    image_parts: list[tuple[str, bytes, str]] = []
    sections = []
    for source in SOURCES:
        analyzed, counts = analyze_source(source)
        status_counts = Counter(row["status"] for row in analyzed)
        main_color = counts["color"].most_common(1)[0][0] if counts["color"] else "입력값 없음"
        main_mood = counts["mood"].most_common(1)[0][0] if counts["mood"] else "입력값 없음"
        main_edge = counts["edge"].most_common(1)[0][0] if counts["edge"] else "입력값 없음"
        trend_lines = [
            f'TOP 6에서는 <b>{html.escape(main_color)}</b> 컬러가 가장 눈에 띕니다.',
            f'디자인은 <b>{html.escape(main_mood)}</b> 무드와 <b>{html.escape(main_edge)}</b> 엣지가 중심 흐름입니다.',
        ]
        if status_counts["상승"]:
            trend_lines.append("상승 제품의 디자인 조합은 다음 상품 기획의 참고 포인트로 볼 수 있습니다.")
        if status_counts["하락"]:
            trend_lines.append("하락 제품과 함께 보면 상위권 내 선호 강도 변화를 비교하기 좋습니다.")
        if status_counts["신규"]:
            trend_lines.append("신규 진입 제품은 오늘 가장 먼저 확인할 변화 포인트입니다.")
        summary_cells = "".join(
            f'<td style="padding:12px;text-align:center;border:1px solid #edf0f4">'
            f'<span style="font-size:12px;color:#667085">{label}</span><br>'
            f'<b style="font-size:22px">{status_counts[label]}</b></td>'
            for label in ("신규", "상승", "하락", "유지")
        )
        changes = "".join(
            '<tr>'
            f'<td style="padding:9px;border-bottom:1px solid #edf0f4"><span style="padding:4px 8px;'
            f'border:1px solid;border-radius:999px;font-size:12px;font-weight:800;{status_style(row["status"])}">'
            f'{row["status"]}</span></td>'
            f'<td style="padding:9px;border-bottom:1px solid #edf0f4;font-weight:800">{row["move"]}</td>'
            f'<td style="padding:9px;border-bottom:1px solid #edf0f4"><a href="{html.escape(row["href"])}" '
            f'style="color:#315ba7;text-decoration:none">{html.escape(row.get("product", ""))}</a></td></tr>'
            for row in analyzed
        )
        cards = []
        for row in analyzed:
            href = row["href"]
            pictures = []
            for kind, label in (("image_url", "제품 이미지"), ("eye_image_url", "착용 눈 이미지")):
                url = row.get(kind, "")
                src = url
                if cid_images and url:
                    try:
                        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        with urlopen(req, timeout=20) as response:
                            data = response.read()
                            mime = response.headers.get_content_type()
                        cid = f"{source['name'].replace(' ', '').lower()}-{row['rank']}-{kind}"
                        image_parts.append((cid, data, mime))
                        src = f"cid:{cid}"
                    except Exception as error:
                        print(f"이미지 다운로드 경고: {url} ({error})", file=sys.stderr)
                if src:
                    pictures.append(
                        f'<img src="{html.escape(src)}" alt="{label}" '
                        'style="width:180px;height:180px;object-fit:cover;border-radius:10px;">'
                    )
            cards.append(
                '<td style="width:33%;padding:12px;vertical-align:top">'
                f'<div style="font-size:24px;font-weight:800;color:#e27f9d">#{html.escape(row["rank"])}</div>'
                f'<div style="margin:5px 0;font-size:12px;font-weight:800">{row["status"]} · {row["move"]}</div>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">{"".join(pictures)}</div>'
                f'<a href="{html.escape(href)}" style="color:#263044;font-weight:700;text-decoration:none">'
                f'{html.escape(row.get("product", ""))}</a>'
                f'<div style="margin-top:8px;color:#667085;font-size:12px;line-height:1.6">'
                f'컬러: <b>{html.escape(row["color"])}</b><br>무드: <b>{html.escape(row["mood"])}</b><br>'
                f'엣지: <b>{html.escape(row["edge"])}</b></div></td>'
            )
        rows_html = "".join(
            f'<tr>{"".join(cards[index:index + 3])}</tr>' for index in range(0, len(cards), 3)
        )
        sections.append(
            f'<h2 style="color:#d8688c;margin-top:32px">{source["name"]} 1day TOP 6</h2>'
            f'<table role="presentation" style="width:100%;border-collapse:collapse;margin-bottom:16px"><tr>{summary_cells}</tr></table>'
            '<h3 style="color:#263044">디자인 트렌드</h3>'
            f'<div style="padding:14px;background:#fff8fa;border:1px solid #f1d7df;border-radius:10px">'
            f'<ul style="margin:0 0 12px 18px;padding:0;line-height:1.7">{"".join(f"<li>{line}</li>" for line in trend_lines)}</ul>'
            f'<b>컬러</b> {chips(counts["color"])}<br><b>무드</b> {chips(counts["mood"])}<br>'
            f'<b>엣지</b> {chips(counts["edge"])}</div>'
            '<h3 style="color:#263044">순위 변화</h3>'
            f'<table role="presentation" style="width:100%;border-collapse:collapse;margin-bottom:18px">{changes}</table>'
            '<h3 style="color:#263044">현재 TOP 6 제품</h3>'
            f'<table role="presentation" style="width:100%;border-collapse:collapse">{rows_html}</table>'
        )
    today = datetime.now().strftime("%Y-%m-%d")
    document = (
        '<!doctype html><html><body style="margin:0;background:#fff7fa;font-family:Arial,sans-serif;color:#263044">'
        '<div style="max-width:1100px;margin:auto;padding:28px;background:#ffffff">'
        f'<h1 style="color:#d8688c">일본 컬러렌즈 일일 트렌드 리포트 · {today}</h1>'
        '<p>Morecon과 Queen Eyes의 당일 1day 컬러렌즈 인기 순위입니다.</p>'
        f'{"".join(sections)}</div></body></html>'
    )
    return document, image_parts


def write_report() -> None:
    report, _ = build_report()
    (ROOT / "daily_report.html").write_text(report, encoding="utf-8")


def send_email() -> None:
    user = os.environ.get("NAVER_WORKS_SMTP_USER", "").strip()
    password = os.environ.get("NAVER_WORKS_SMTP_APP_PASSWORD", "").strip()
    recipients = tuple(
        address.strip()
        for address in os.environ.get("REPORT_RECIPIENTS", "").split(",")
        if address.strip()
    )
    if not user or not password or not recipients:
        print("SMTP secrets가 없어 메일 발송은 건너뜁니다.")
        return
    report, images = build_report(cid_images=True)
    message = EmailMessage()
    message["From"] = user
    message["To"] = ", ".join(recipients)
    message["Subject"] = f"일본 컬러렌즈 TOP 6 일일 리포트 - {datetime.now():%Y-%m-%d}"
    message.set_content("HTML을 지원하는 메일에서 리포트를 확인해 주세요.")
    message.add_alternative(report, subtype="html")
    html_part = message.get_payload()[-1]
    for cid, data, mime in images:
        maintype, subtype = mime.split("/", 1)
        html_part.add_related(data, maintype=maintype, subtype=subtype, cid=f"<{cid}>")
    with smtplib.SMTP("smtp.worksmobile.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(message)
    print(f"메일 발송 완료: {len(recipients)}명")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--send-email", action="store_true")
    args = parser.parse_args()
    if not args.skip_collection:
        collect()
    write_report()
    if args.send_email:
        send_email()


if __name__ == "__main__":
    main()
