from playwright.sync_api import sync_playwright
import csv
import os
from datetime import datetime

TOP_N = 6
BASE_URL = "https://morecon.jp/"


def save_csv(filename, rows):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "product", "href", "image_url", "eye_image_url"])
        writer.writerows(rows)


def normalize_image_url(url):
    url = str(url or "").strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"https://morecon.jp{url}"
    return url


def get_image_url(detail_page):
    image_url = ""

    try:
        og = detail_page.locator("meta[property='og:image']").get_attribute("content")
        if og:
            image_url = normalize_image_url(og)
    except:
        pass

    if not image_url:
        try:
            src = detail_page.locator("img").first.get_attribute("src")
            if src:
                image_url = normalize_image_url(src)
        except:
            pass

    return image_url


def get_eye_image_url(detail_page, image_url=""):
    try:
        image_urls = detail_page.evaluate("""
        () => Array.from(document.querySelectorAll('img')).flatMap(img => [
            img.currentSrc,
            img.src,
            img.getAttribute('src'),
            img.getAttribute('data-src'),
            img.getAttribute('data-original'),
            img.getAttribute('data-lazy-src')
        ]).filter(Boolean)
        """)

        for src in image_urls:
            src = normalize_image_url(src)
            if "_eye" in src or "640x360_eye" in src:
                return src
    except:
        pass

    image_url = normalize_image_url(image_url)
    if "thum_640x640.jpg" in image_url:
        return image_url.replace("thum_640x640.jpg", "thum_640x360_eye.jpg")

    return ""


def collect_visible_ranking(page, context, top_n=6):
    links = page.evaluate("""
    () => {
        const anchors = Array.from(document.querySelectorAll('a[href^="/i/"]'));
        return anchors.map(a => {
            const r = a.getBoundingClientRect();
            return {
                href: a.getAttribute('href'),
                x: r.left,
                y: r.top,
                width: r.width,
                height: r.height
            };
        });
    }
    """)

    cards = []
    seen = set()

    for item in links:
        href = item["href"]
        x = item["x"]
        y = item["y"]
        w = item["width"]
        h = item["height"]

        if not href or href in seen:
            continue

        if x < 250:
            continue

        if y < 40 or y > 1600:
            continue

        if w < 70 or h < 70:
            continue

        cards.append({
            "href": href,
            "x": x,
            "y": y
        })
        seen.add(href)

    cards.sort(key=lambda item: (round(item["y"] / 20), item["x"]))
    product_cards = cards[:top_n]

    if len(product_cards) < top_n:
        page.screenshot(path="debug_ranking_area.png", full_page=True)
        raise Exception(f"카드 부족: {len(product_cards)}개 찾음")

    results = []

    for i, item in enumerate(product_cards, start=1):
        href = item["href"]

        detail_page = context.new_page()
        detail_page.goto(f"https://morecon.jp{href}", wait_until="domcontentloaded")
        detail_page.wait_for_timeout(2000)

        title = detail_page.title()
        image_url = get_image_url(detail_page)
        eye_image_url = get_eye_image_url(detail_page, image_url)

        results.append([i, title, href, image_url, eye_image_url])

        detail_page.close()

    return results


with sync_playwright() as p:
    headless = os.environ.get("LENS_HEADLESS", "0") == "1"
    browser = p.chromium.launch(headless=headless)

    context = browser.new_context(
        viewport={"width": 1400, "height": 2200},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    )

    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 원데이 랭킹 위치로 이동
    page.mouse.wheel(0, 1300)
    page.wait_for_timeout(3000)

    page.screenshot(path="debug_oneday_area.png", full_page=False)

    oneday_results = collect_visible_ranking(page, context, TOP_N)

    context.close()
    browser.close()


today_str = datetime.now().strftime("%Y-%m-%d")

save_csv("today.csv", oneday_results)
save_csv(f"ranking_{today_str}.csv", oneday_results)

print("원데이 랭킹 저장 완료")
