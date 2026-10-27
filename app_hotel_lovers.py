from datetime import datetime
import csv
import os
import re
import shutil
from urllib.parse import urlsplit, parse_qs

from playwright.sync_api import sync_playwright

TOP_N = 6
BASE_URL = "https://hotellovers.jp"
RANKING_URL = BASE_URL
RANKING_SELECTOR = "#hl_period_zero_rank .toprank_list"
LATEST_RANKING_URL = f"{BASE_URL}/initranking"
LATEST_RANKING_SELECTOR = "#hl_rankpage_one .p-goods-wrapper:not(.is-skeleton)"


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


def product_key(url):
    parts = urlsplit(normalize_url(url))
    return parts.path, parse_qs(parts.query).get("color", [""])[0]


def collect_latest_product_images(context):
    """Use the detailed ranking page only as a product-image catalogue."""
    page = context.new_page()
    try:
        page.goto(LATEST_RANKING_URL, wait_until="domcontentloaded", timeout=45000)
        page.locator(LATEST_RANKING_SELECTOR).first.wait_for(state="attached", timeout=30000)
        cards = page.locator(LATEST_RANKING_SELECTOR).evaluate_all("""cards => cards.map(card => ({
            href: card.querySelector('a.p-goods')?.href,
            image: card.querySelector('img.w-100:not(.c-badge-band-image)')?.src
        }))""")
        return {product_key(card["href"]): card["image"]
                for card in cards if card.get("href") and card.get("image")}
    except Exception as error:
        print(f"상품 이미지 카탈로그 수집 경고: {error}")
        return {}
    finally:
        page.close()


def get_eye_image_url(context, product_url):
    detail_page = context.new_page()
    try:
        detail_page.goto(product_url, wait_until="domcontentloaded", timeout=45000)
        current = detail_page.locator("#js-thumb-pc-main .slick-current").first
        current.wait_for(state="attached", timeout=30000)
        # Dewlit's color gallery: hero, comparison, material guide, lens, single eye.
        # Keep the offset relative to the selected color, not the whole gallery.
        offset = 4 if "9f4b9b5a-30b0-481d-b7d5-45ea23723b65" in product_url else 1
        eye_image = current.locator(f"xpath=following-sibling::*[{offset}]//img[not(contains(@class, 'c-badge-band-image'))]").first
        return normalize_url(eye_image.get_attribute("src")) if eye_image.count() else ""
    except Exception as error:
        print(f"착용 이미지 수집 경고: {product_url} ({error})")
        return ""
    finally:
        detail_page.close()


def collect_oneday_ranking(page, context, top_n=6):
    product_images = collect_latest_product_images(context)
    page.goto(RANKING_URL, wait_until="domcontentloaded", timeout=45000)
    page.locator(RANKING_SELECTOR).first.wait_for(state="attached", timeout=30000)
    rows = []
    for fallback_rank, card in enumerate(page.locator(RANKING_SELECTOR).all(), start=1):
        if len(rows) >= top_n:
            break
        link = card.locator("a").first
        rank_image = card.locator(".toprank_no img").first
        rank_text = rank_image.get_attribute("title") or ""
        name = card.locator(".toprank_list_title").first.inner_text().strip()
        color = card.locator(".toprank_list_colorname").first.inner_text().strip()
        # The homepage artwork contains the model/product panel above and the
        # wearing-eye panel below. Email rendering crops the #home-eye version.
        composite = link.locator("img").first
        href = normalize_url(link.get_attribute("href"))
        composite_url = normalize_url(composite.get_attribute("src"))
        image_url = product_images.get(product_key(href)) or composite_url
        match = re.search(r"(\d+)", rank_text)
        rank = int(match.group(1)) if match else fallback_rank
        product = f"{name} {color}".strip()
        if href and product:
            eye_url = f"{composite_url}#home-eye" if composite_url else get_eye_image_url(context, href)
            rows.append([rank, product, href, image_url, eye_url])
    rows.sort(key=lambda row: row[0])
    if len(rows) < top_n:
        page.screenshot(path="debug_hotel_lovers_ranking.png", full_page=True)
        raise RuntimeError(f"Hotel Lovers 1day 랭킹 카드 부족: {len(rows)}개")
    return rows[:top_n]


with sync_playwright() as playwright:
    launch_options = {"headless": os.environ.get("LENS_HEADLESS", "0") == "1"}
    chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or shutil.which("chromium")
    if chromium_path:
        launch_options["executable_path"] = chromium_path
    browser = playwright.chromium.launch(**launch_options)
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
