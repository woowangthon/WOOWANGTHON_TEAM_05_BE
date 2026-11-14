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
    utilities = 0 if housing.get("bills_included") else living["utilities"]
    monthly = money(rent + housing["monthly_transport"] + living["food"] + (utilities or 0) + living["phone"] + (profile.insurance if profile.insurance is not None else 0))
    initial = money((housing["bond"] or 0) + (housing["advance_rent"] or 0) + (living["moving"] or 0))
    return {"rent": rent, "monthly": monthly, "initial": initial,
            "utilities": utilities,
            "monthly_missing": (["의료·보험료"] if profile.insurance is None else []) + (["공과금"] if utilities is None else []),
            "initial_missing": (["보증금"] if housing["bond"] is None else []) + (["선납 월세"] if housing["advance_rent"] is None else []) + (["이사비"] if living["moving"] is None else []) + ["항공권", "비자 관련 비용", "기타 개인 정착 비용"],
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
        option = {**housing, **get_commute_estimates(housing, profile), **calculate_budget(housing, profile)}
        option["commute_verified"] = option["commute"] is not None
        if (option["commute"] is None or option["commute"] <= profile.max_commute) and option["monthly"] <= profile.monthly_budget and option["initial"] <= profile.initial_budget:
            options.append(option)
    def score(h):
        commute = h["commute"] if h["commute"] is not None else 10000
        value = h["monthly"] if profile.sort_by == "cheapest" else commute if profile.sort_by == "fastest" else h["monthly"] + commute * 10
        return value, h["id"]
    options.sort(key=score)
    return {"profile": profile.model_dump(mode="json"), "options": options[:3],
            "guides": build_checklist(profile, search_settlement_guides(profile)), "living_costs": DATA["living_costs"],
            "currency": "AUD", "data_version": DATA["version"], "mode": "rules", "cost_sources": DATA.get("cost_sources", []),
            "explanation": "공개 요금과 참고 예산으로 비교했습니다. 시작 요금은 확정 견적이 아니며 통근 미확인 후보는 조건 충족 여부를 확인해야 합니다." if options else "현재 조건에 맞는 후보가 없습니다. 예산·통근시간·주거 형태를 조정해 보세요.",
            "warnings": ["운영사 공개 요금 스냅샷입니다. 지역 시작 요금은 특정 공실이 아니며 계약 가격·입주 가능일은 원문에서 재확인하세요.",
                         "통근시간은 운영사 지역→CBD 참고치입니다. 미확인 경로도 후보로 표시하며 최대 통근 조건을 충족한다고 보장하지 않습니다.",
                         "식비·통신비는 대학 안내 범위의 하한, 교통비는 Opal 주간 상한의 월 환산 예산입니다. 개인 지출과 다를 수 있습니다.",
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
