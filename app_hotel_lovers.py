from datetime import datetime
import csv
import os
import re

from playwright.sync_api import sync_playwright

TOP_N = 6
BASE_URL = "https://hotellovers.jp"
RANKING_URL = f"{BASE_URL}/initranking"
RANKING_SELECTOR = "#hl_rankpage_one .p-goods-wrapper:not(.is-skeleton)"


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
        return f"{BASE_URL}{url}"
    return url


def get_eye_image_url(context, product_url):
    detail_page = context.new_page()
    try:
        detail_page.goto(product_url, wait_until="domcontentloaded", timeout=45000)
        current = detail_page.locator("#js-thumb-pc-main .slick-current").first
        current.wait_for(state="attached", timeout=30000)
        eye_image = current.locator("xpath=following-sibling::*[1]//img").first
        return normalize_url(eye_image.get_attribute("src")) if eye_image.count() else ""
    except Exception as error:
        print(f"착용 이미지 수집 경고: {product_url} ({error})")
        return ""
    finally:
        detail_page.close()


def collect_oneday_ranking(page, context, top_n=6):
    page.goto(RANKING_URL, wait_until="domcontentloaded", timeout=45000)
    page.locator(RANKING_SELECTOR).first.wait_for(state="attached", timeout=30000)
    rows = []
    for fallback_rank, card in enumerate(page.locator(RANKING_SELECTOR).all(), start=1):
        if len(rows) >= top_n:
            break
        link = card.locator("a.p-goods").first
        rank_text = card.locator(".p-goods-rank").first.inner_text().strip()
        name = card.locator(".contact__product-name").first.inner_text().strip()
        color = card.locator(".contact__color").first.inner_text().strip()
        image = card.locator("img").first
        href = normalize_url(link.get_attribute("href"))
        image_url = normalize_url(image.get_attribute("src"))
        match = re.search(r"(\d+)", rank_text)
        rank = int(match.group(1)) if match else fallback_rank
        product = f"{name} {color}".strip()
        if href and product:
            rows.append([rank, product, href, image_url, get_eye_image_url(context, href)])
    rows.sort(key=lambda row: row[0])
    if len(rows) < top_n:
        page.screenshot(path="debug_hotel_lovers_ranking.png", full_page=True)
        raise RuntimeError(f"Hotel Lovers 1day 랭킹 카드 부족: {len(rows)}개")
    return rows[:top_n]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=os.environ.get("LENS_HEADLESS", "0") == "1")
    context = browser.new_context(
        viewport={"width": 1440, "height": 2200},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
    )
    ranking_rows = collect_oneday_ranking(context.new_page(), context, TOP_N)
    context.close()
    browser.close()

today = datetime.now().strftime("%Y-%m-%d")
save_csv("hotel_lovers_today.csv", ranking_rows)
save_csv(f"ranking_hotel_lovers_{today}.csv", ranking_rows)
print("Hotel Lovers 주간 1day TOP 6 저장 완료")
