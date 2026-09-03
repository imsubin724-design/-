from datetime import datetime
import csv
import os
import re

from playwright.sync_api import sync_playwright


TOP_N = 6
BASE_URL = "https://www.queen-eyes.com/"
RANKING_SELECTOR = (
    ".ranking-dark-box .tab-contents > li:first-child "
    ".item-list > li"
)


def save_csv(filename, rows):
    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["rank", "product", "href", "image_url", "eye_image_url"])
        writer.writerows(rows)


def normalize_url(url):
    url = str(url or "").strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"https://www.queen-eyes.com{url}"
    return url


def get_eye_image_url(context, product_url):
    detail_page = context.new_page()
    try:
        detail_page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
        detail_page.wait_for_timeout(1200)
        eye_thumbnail = detail_page.locator('img[src*="-03.jpg"]').first
        if not eye_thumbnail.count():
            return ""

        eye_url = normalize_url(eye_thumbnail.get_attribute("src"))
        eye_url = re.sub(r"([?&])size=[^&]+", r"\1size=l", eye_url)
        eye_url = re.sub(r"([?&])w=[^&]+", r"\1w=ODAw", eye_url)
        return eye_url
    finally:
        detail_page.close()


def collect_oneday_ranking(page, context, top_n=6):
    page.locator(RANKING_SELECTOR).first.wait_for(state="visible", timeout=30000)
    cards = page.locator(RANKING_SELECTOR).all()
    rows = []

    for fallback_rank, card in enumerate(cards, start=1):
        if len(rows) >= top_n:
            break

        link = card.locator("a").first
        image = card.locator("img").first
        name = card.locator("p.name").first
        rank_badge = card.locator("span.ranking").first

        href = normalize_url(link.get_attribute("href"))
        product = name.inner_text().strip()
        image_url = normalize_url(image.get_attribute("data-image") or image.get_attribute("src"))
        rank_text = rank_badge.inner_text().strip() if rank_badge.count() else str(fallback_rank)
        rank = int(rank_text) if rank_text.isdigit() else fallback_rank

        if href and product:
            eye_image_url = get_eye_image_url(context, href)
            rows.append([rank, product, href, image_url, eye_image_url])

    rows.sort(key=lambda row: row[0])
    if len(rows) < top_n:
        page.screenshot(path="debug_queen_eyes_ranking.png", full_page=True)
        raise RuntimeError(f"Queen Eyes 1day 랭킹 카드 부족: {len(rows)}개")
    return rows[:top_n]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=os.environ.get("LENS_HEADLESS", "0") == "1")
    context = browser.new_context(
        viewport={"width": 1440, "height": 2200},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    ranking_rows = collect_oneday_ranking(page, context, TOP_N)
    context.close()
    browser.close()


today = datetime.now().strftime("%Y-%m-%d")
save_csv("queen_eyes_today.csv", ranking_rows)
save_csv(f"ranking_queen_eyes_{today}.csv", ranking_rows)
print("Queen Eyes 1day TOP 6 저장 완료")
