from playwright.sync_api import sync_playwright
import csv
from datetime import datetime

TOP_N = 6
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        viewport={"width": 1400, "height": 2200},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    )

    page = context.new_page()

    # 1. 메인 페이지 열기
    page.goto("https://morecon.jp/", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 2. 원데이 카라콘 랭킹 위치까지 스크롤
    page.mouse.wheel(0, 1300)
    page.wait_for_timeout(3000)

    # 3. 현재 페이지에 있는 /i/ 상품 링크들을 JS로 직접 수집
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

    # 4. 보이는 카드 영역만 남기기
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

        # 왼쪽 필터 영역 제외
        if x < 300:
            continue

        # 화면에 보이는 중간 랭킹 카드 영역만 사용
        if y < 50 or y > 1500:
            continue

        # 너무 작은 링크 제외
        if w < 80 or h < 80:
            continue

        cards.append({
            "href": href,
            "x": x,
            "y": y
        })
        seen.add(href)

    # 5. 카드 순서 정렬 (위 → 아래, 왼 → 오른)
    cards.sort(key=lambda item: (round(item["y"] / 20), item["x"]))

    # 6. 디버그 캡처 저장
    page.screenshot(path="debug_ranking_area.png")

    # 7. 앞에서 6개만 사용
    product_cards = cards[:TOP_N]

    if len(product_cards) < TOP_N:
        context.close()
        browser.close()
        raise Exception(f"카드 부족: {len(product_cards)}개 찾음")

    # 8. 상세 페이지에서 상품명 + 이미지 가져오기
    for i, item in enumerate(product_cards, start=1):
        href = item["href"]

        detail_page = context.new_page()
        detail_page.goto(f"https://morecon.jp{href}", wait_until="domcontentloaded")
        detail_page.wait_for_timeout(2000)

        title = detail_page.title()

        image_url = ""
        try:
            # og:image 우선
            og = detail_page.locator("meta[property='og:image']").get_attribute("content")
            if og:
                image_url = og
        except:
            pass

        if not image_url:
            try:
                # 상품 대표 이미지 후보
                img = detail_page.locator("img").first
                src = img.get_attribute("src")
                if src:
                    image_url = src
            except:
                pass

        results.append([i, title, href, image_url])

        detail_page.close()

    context.close()
    browser.close()

# 9. today.csv 저장
with open("today.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["rank", "product", "href", "image_url"])
    writer.writerows(results)

# 10. 날짜별 파일 저장
today_str = datetime.now().strftime("%Y-%m-%d")
filename = f"ranking_{today_str}.csv"

with open(filename, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["rank", "product", "href", "image_url"])
    writer.writerows(results)