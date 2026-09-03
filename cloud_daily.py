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
    },
    {
        "name": "Queen Eyes",
        "today": "queen_eyes_today.csv",
        "yesterday": "queen_eyes_yesterday.csv",
        "archive": "ranking_queen_eyes_*.csv",
        "script": "app_queen_eyes.py",
        "host": "https://www.queen-eyes.com",
    },
)
def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def full_url(value: str, host: str) -> str:
    value = (value or "").strip()
    return value if value.startswith("http") else f"{host}{value}"


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
        cards = []
        for row in read_rows(ROOT / source["today"]):
            href = full_url(row.get("href", ""), source["host"])
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
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">{"".join(pictures)}</div>'
                f'<a href="{html.escape(href)}" style="color:#263044;font-weight:700;text-decoration:none">'
                f'{html.escape(row.get("product", ""))}</a></td>'
            )
        rows_html = "".join(
            f'<tr>{"".join(cards[index:index + 3])}</tr>' for index in range(0, len(cards), 3)
        )
        sections.append(
            f'<h2 style="color:#d8688c;margin-top:32px">{source["name"]} 1day TOP 6</h2>'
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
