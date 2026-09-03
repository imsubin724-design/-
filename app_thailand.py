from datetime import datetime
import csv
import re

from playwright.sync_api import sync_playwright

TOP_N = 6
BASE_URL = "https://shopee.co.th/search?keyword=color%20lens&page=0&sortBy=sales"
HOST = "https://shopee.co.th"
PROFILE_DIR = "shopee_thailand_profile"


def save_csv(filename, rows):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "product", "href", "image_url", "eye_image_url"])
        writer.writerows(rows)


def normalize_url(url):
    url = str(url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{HOST}{url}"
    return url


def clean_product_name(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return "Shopee color lens product"
    return text[:160]


def collect_shopee_results(page, top_n=6):
    page.wait_for_timeout(5000)

    if not has_product_links(page):
        print("Shopee 검색 결과가 보이지 않습니다. 열린 브라우저에서 로그인한 뒤 color lens 검색 결과 화면이 보일 때까지 기다려 주세요.")
        for _ in range(36):
            page.wait_for_timeout(5000)
            if has_product_links(page):
                print("Shopee 상품 링크를 찾았습니다. TOP 6 수집을 계속합니다.")
                break
            if "search?keyword=color" not in page.url:
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

    if not has_product_links(page):
        page.screenshot(path="debug_thailand_shopee_area.png", full_page=True)
        raise Exception(
            "Shopee 상품을 찾지 못했습니다. Shopee가 로그인 필요 화면을 보여주고 있습니다. "
            "열린 브라우저에서 로그인한 뒤 다시 오늘 데이터 업데이트를 눌러 주세요."
        )

    for _ in range(5):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(900)
    page.mouse.wheel(0, -5000)
    page.wait_for_timeout(1200)
    page.screenshot(path="debug_thailand_shopee_area.png", full_page=True)

    products = page.evaluate(
        """
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            const productLinks = anchors.filter(a => {
                const href = a.getAttribute('href') || '';
                return href.includes('/product/') || /-i\\.\\d+\\.\\d+/.test(href);
            });

            const rows = [];
            const seen = new Set();

            for (const a of productLinks) {
                const href = a.getAttribute('href') || '';
                if (!href || seen.has(href)) continue;

                const rect = a.getBoundingClientRect();
                if (rect.width < 120 || rect.height < 120) continue;

                const img = a.querySelector('img') || a.closest('div')?.querySelector('img');
                const imageUrl = img ? (img.currentSrc || img.src || img.getAttribute('src') || '') : '';
                const imgAlt = img ? (img.getAttribute('alt') || '') : '';
                const aria = a.getAttribute('aria-label') || '';
                const title = a.getAttribute('title') || '';
                const text = (title || aria || imgAlt || a.innerText || '').trim();

                rows.push({
                    href,
                    product: text,
                    image_url: imageUrl,
                    top: rect.top + window.scrollY,
                    left: rect.left + window.scrollX
                });
                seen.add(href);
            }

            rows.sort((a, b) => (Math.round(a.top / 30) - Math.round(b.top / 30)) || (a.left - b.left));
            return rows;
        }
        """
    )

    results = []
    seen_urls = set()
    for item in products:
        href = normalize_url(item.get("href"))
        if not href or href in seen_urls:
            continue

        image_url = normalize_url(item.get("image_url"))
        product = clean_product_name(item.get("product"))
        results.append([len(results) + 1, product, href, image_url, ""])
        seen_urls.add(href)

        if len(results) >= top_n:
            break

    if len(results) < top_n:
        raise Exception(f"Shopee 상품 카드를 {len(results)}개만 찾았습니다. debug_thailand_shopee_area.png를 확인해 주세요.")

    return results


def has_product_links(page):
    try:
        return page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]')).some(a => {
                const href = a.getAttribute('href') || '';
                return href.includes('/product/') || /-i\\.\\d+\\.\\d+/.test(href);
            })
            """
        )
    except Exception:
        return False


with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        viewport={"width": 1440, "height": 1800},
        locale="th-TH",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    thailand_results = collect_shopee_results(page, TOP_N)
    context.close()


today_str = datetime.now().strftime("%Y-%m-%d")
save_csv("thailand_today.csv", thailand_results)
save_csv(f"ranking_thailand_{today_str}.csv", thailand_results)

print("태국 Shopee 랭킹 저장 완료")
