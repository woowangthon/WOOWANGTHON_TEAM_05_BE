"""Collect a reviewed allowlist. No login, anti-bot bypass, or retry on 429.

Run: uv run python scripts/collect_sources.py --sync-frontend
All required sources must parse before either snapshot is replaced.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

import httpx
try:
    from scripts.enrich_sources import enrich
except ModuleNotFoundError:
    from enrich_sources import enrich

ROOT = Path(__file__).resolve().parents[1]
LIVING_URL = "https://www.sydney.edu.au/study/fees-and-loans/other-costs/living-costs.html"
FARES_URL = "https://transportnsw.info/tickets-fares/fares"
HOUSING = [
    ("cda-newtown", "Newtown", "share", "peach", "https://cdacoliving.com/share-house/sydney/newtown"),
    ("cda-ashfield", "Ashfield", "share", "sage", "https://cdacoliving.com/flatmates/sydney/ashfield"),
    ("cda-redfern", "Redfern", "share", "lavender", "https://cdacoliving.com/flatmates/sydney/redfern"),
    ("uko-newtown", "Newtown", "studio", "sage", "https://www.uko.com.au/uko-newtown/floorplans/studio"),
    ("uko-surry", "Surry Hills", "studio", "peach", "https://www.uko.com.au/uko-surry-hills/floorplans/studio"),
]


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def visible_text(html):
    parser = PageText()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts))


def require(pattern, text):
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError("Source format changed: " + pattern)
    return match


def parse_housing(item, text, checked_at, transport):
    ident, area, kind, color, url = item
    if "no longer available" in text.lower():
        raise ValueError("Listing is no longer available: " + ident)
    cda = ident.startswith("cda-")
    if cda:
        rent = float(require(r"Weekly rent From \$\s*([\d,]+)", text)[1].replace(",", ""))
        commute = int(require(r"To the CBD (\d+) minutes", text)[1])
        require(r"All bills included", text)
        availability = "지역별 시작 요금 · 특정 방의 공실·입주일은 운영사 확인 필요"
    else:
        unit = require(r"Apartment:\s*#\s*(\w+) Date Available:\s*(\d{2}/\d{2}/\d{4}) Starting at:\s*\$([\d,.]+)\s*/Week", text)
        rent = float(unit[3].replace(",", ""))
        commute = None
        availability = f"공고 호실 {unit[1]} · 공고 입주 가능일 {unit[2]} · 현재 공실 재확인 필요"
    if not 50 <= rent <= 5000:
        raise ValueError("Unexpected weekly rent")
    return {
        "id": ident, "name": ("CDA " if cda else "UKO ") + area + (" 쉐어하우스 요금 안내" if cda else " 스튜디오"),
        "area": area, "type": kind, "weekly_rent": rent, "bond": None, "advance_rent": None,
        "commutes": {"Sydney CBD": commute, "Surry Hills": None, "Parramatta": None},
        "monthly_transport": transport, "tags": ["지역 시작 요금" if cda else "호실 시작 요금", "공과금 포함" if cda else "공과금 확인 필요"],
        "color": color, "is_demo": False, "source_url": url, "publisher": "CDA Coliving" if cda else "UKO",
        "checked_at": checked_at, "price_basis": "starting_from", "availability": availability,
        "bills_included": True if cda else None,
        "commute_note": "운영사가 안내한 지역→CBD 예상 시간. 도보·대기·실제 직장 위치는 미반영." if cda else "정확한 출발지·직장·출근시간으로 경로 확인 필요",
        "source_kind": "area_rate" if cda else "unit_advertisement",
    }


def collect(sync_frontend=False):
    now = datetime.now(timezone(timedelta(hours=9)))
    checked = now.date().isoformat()
    records = []
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "SettlementPlanner/0.1 public-source-check"}) as client:
        def fetch(url):
            response = client.get(url)
            response.raise_for_status()
            if str(response.url).rstrip("/") != url.rstrip("/"):
                raise ValueError("Source redirected; manual review required: " + url)
            text = visible_text(response.text)
            records.append({"url": url, "retrieved_at": now.isoformat(), "sha256": hashlib.sha256(response.content).hexdigest(), "status": response.status_code})
            return text

        fares = fetch(FARES_URL)
        weekly_cap = float(require(r"\$([\d.]+) a week", fares)[1])
        if not 10 <= weekly_cap <= 200:
            raise ValueError("Unexpected fare cap")
        living = fetch(LIVING_URL)
        food = require(r"Food and groceries.*?\$([\d,]+)\s*[-–]\s*\$([\d,]+)", living)
        phone = require(r"Mobile phone plan.*?\$([\d,]+)\s*[-–]\s*\$([\d,]+)", living)
        food_range = [float(food[i].replace(",", "")) for i in (1, 2)]
        phone_range = [float(phone[i].replace(",", "")) for i in (1, 2)]
        housing = [parse_housing(item, fetch(item[4]), checked, round(weekly_cap * 52 / 12, 2)) for item in HOUSING]

    data_path = ROOT / "app/data/sydney.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    data.update(version=checked + "-sourced-v1", housing=housing,
                living_costs={"food": food_range[0], "utilities": None, "phone": phone_range[0], "moving": None})
    data["cost_sources"] = [
        {"id": "living", "title": "식비·통신비 월 예산 참고", "publisher": "University of Sydney", "url": LIVING_URL, "checked_at": checked,
         "note": f"학생 생활비 참고 범위: 식비 {food_range[0]:g}–{food_range[1]:g}, 통신 {phone_range[0]:g}–{phone_range[1]:g} AUD/월. 계산에는 하한값 사용; 개인 견적·실제 지출이 아님."},
        {"id": "fares", "title": "성인 Opal 주간 상한", "publisher": "Transport for NSW", "url": FARES_URL, "checked_at": checked,
         "note": f"성인 주간 상한 {weekly_cap:g} AUD × 52 ÷ 12를 월 교통 예산으로 사용. 실제 통근 요금 아님. 공항 역 이용료·지역 열차 제외."},
    ]
    for guide in data["guides"]:
        if guide["id"] == "transport":
            guide["text"] = "출발지·직장·출근시간을 지정해 실제 경로를 확인하세요. 지역→CBD 시간은 운영사 참고치이며, 나머지 경로는 미확인입니다. 교통 예산은 성인 Opal 주간 상한을 월 환산합니다."
    # Preserve separately dated manual evidence; never claim it was crawled today.
    data = enrich(data)
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    data_path.write_text(encoded, encoding="utf-8")
    (ROOT / "app/data/source-manifest.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if sync_frontend:
        (ROOT.parent / "WOOWANGTHON_TEAM_05_FE/data/sydney.json").write_text(encoded, encoding="utf-8")
    print(f"Collected {len(housing)} housing references and {len(data['cost_sources'])} cost sources; version {data['version']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-frontend", action="store_true")
    collect(parser.parse_args().sync_frontend)
