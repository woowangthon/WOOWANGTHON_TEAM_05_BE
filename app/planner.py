import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from app.models import Profile, ProfilePatch

DATA = json.loads((Path(__file__).parent / "data" / "sydney.json").read_text(encoding="utf-8"))


def money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def search_settlement_guides(profile: Profile) -> list[dict]:
    """Metadata retrieval from a small, curated official-source corpus."""
    return [dict(g) for g in DATA["guides"] if not g["purposes"] or profile.purpose in g["purposes"]]


def find_housing_options(profile: Profile) -> list[dict]:
    return [dict(h) for h in DATA["housing"] if profile.housing_type == "any" or h["type"] == profile.housing_type]


def get_commute_estimates(housing: dict, profile: Profile) -> dict:
    return {"commute": housing["commutes"][profile.workplace], "monthly_transport": housing["monthly_transport"]}


def calculate_budget(housing: dict, profile: Profile) -> dict:
    living = DATA["living_costs"]
    rent = money(housing["weekly_rent"] * 52 / 12)
    # Nullable costs have separate missing lists. The subtotal is never represented as a complete total.
    monthly = money(rent + housing["monthly_transport"] + living["food"] + living["utilities"] + living["phone"] + (profile.insurance if profile.insurance is not None else 0))
    initial = money((housing["bond"] if housing["bond"] is not None else 0) + housing["advance_rent"] + living["moving"])
    return {"rent": rent, "monthly": monthly, "initial": initial,
            "monthly_missing": ["의료·보험료"] if profile.insurance is None else [],
            "initial_missing": (["보증금"] if housing["bond"] is None else []) + ["항공권", "비자 관련 비용", "기타 개인 정착 비용"],
            "monthly_remaining": money(profile.monthly_budget - monthly), "initial_remaining": money(profile.initial_budget - initial)}


def build_checklist(profile: Profile, guides: list[dict]) -> list[dict]:
    if profile.visa_status == "held":
        for guide in guides:
            if guide["id"] == "visa":
                guide["title"] = "발급된 비자와 근로 조건 재확인"
    return guides


def build_plan(profile: Profile) -> dict:
    options = []
    for housing in find_housing_options(profile):
        option = {**housing, **get_commute_estimates(housing, profile), **calculate_budget(housing, profile),
                  "is_demo": True, "source_url": None, "checked_at": DATA["version"][:10]}
        if option["commute"] <= profile.max_commute and option["monthly"] <= profile.monthly_budget and option["initial"] <= profile.initial_budget:
            options.append(option)
    def score(h):
        value = h["monthly"] if profile.sort_by == "cheapest" else h["commute"] if profile.sort_by == "fastest" else h["monthly"] + h["commute"] * 10
        return value, h["id"]
    options.sort(key=score)
    return {"profile": profile.model_dump(mode="json"), "options": options[:3],
            "guides": build_checklist(profile, search_settlement_guides(profile)), "living_costs": DATA["living_costs"],
            "currency": "AUD", "data_version": DATA["version"], "mode": "demo",
            "explanation": "입력한 조건으로 가상 후보를 계산했습니다. 알려진 비용 기준이며 미확인 비용은 별도로 확인하세요." if options else "현재 조건에 맞는 후보가 없습니다. 예산·통근시간·주거 형태를 조정해 보세요.",
            "warnings": ["주거·월세·통근시간·생활비는 시연용 가상 데이터이며 실제 매물·시세가 아닙니다.",
                         "주간 월세는 주간 금액 × 52 ÷ 12로 월 환산합니다. 초기 비용은 보증금·선납 월세·이사비의 부분 합계이며 월 지출과 더하지 않습니다.",
                         "의료·보험료, 항공권, 비자 및 기타 비용의 누락 여부를 확인하세요. 비자 자격은 판정하지 않습니다."]}


def interpret_demo(message: str) -> dict:
    patch = {}
    if re.search("저렴|싸게|절약", message):
        patch["sort_by"] = "cheapest"
    if re.search("빠르|빠른|가까운|짧은", message):
        patch["sort_by"] = "fastest"
    if re.search("쉐어|셰어", message):
        patch["housing_type"] = "share"
    if re.search("스튜디오|원룸", message):
        patch["housing_type"] = "studio"
    if re.search("형태.*무관|모든.*주거", message):
        patch["housing_type"] = "any"
    if match := re.search(r"(?:통근|출퇴근)\s*(\d+)\s*분", message):
        patch["max_commute"] = int(match[1])
    if match := re.search(r"월\s*예산\s*(\d+(?:\.\d+)?)\s*(?:AUD|달러)?", message, re.I):
        patch["monthly_budget"] = float(match[1])
    if not patch:
        raise ValueError('데모에서는 “더 저렴하게”, “통근 60분”, “월 예산 3000”, “쉐어룸”을 사용하거나 입력 폼을 수정해 주세요. 자유로운 조건 해석은 Gemma 연결 후 가능합니다.')
    return ProfilePatch.model_validate(patch).changes()
