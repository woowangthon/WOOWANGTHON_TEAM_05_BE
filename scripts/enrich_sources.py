"""Reviewed supplementary evidence; does not invent individual quotes or routes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKED = "2026-11-14"
UTS = "https://www.uts.edu.au/for-students/international/life-in-sydney/cost-of-living"
LEASE = "https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/starting-a-residential-tenancy/signing-a-lease-and-moving"
UKO = {"uko-newtown": "https://www.uko.com.au/uko-newtown/", "uko-surry": "https://www.uko.com.au/uko-surry-hills"}


def enrich(data):
    # This date describes manual evidence review, not a new rent/availability crawl.
    data["version"] = data["version"].split("+reviewed-")[0] + "+reviewed-" + CHECKED
    data["living_costs"]["utilities"] = 150.0
    additions = [
        {"id": "utilities", "title": "공과금·인터넷 참고 예산", "publisher": "University of Technology Sydney", "url": UTS,
         "note": "월 150–400 AUD의 학생 생활비 참고 범위. 별도 납부가 확인된 주거에 하한 150 AUD 적용. 포함 요금에는 중복 가산하지 않으며, 포함 여부가 미확인이면 누락으로 표시합니다."},
        {"id": "lease-reference", "title": "일반 주거 임대차 입주 자금 참고", "publisher": "NSW Government", "url": LEASE,
         "note": "일반 주거 임대차 안내의 보증금 최대 4주·선납 월세 최대 2주를 별도 참고액으로 표시합니다. 해당 계약의 적용 여부·청구액은 미확인이므로 실제 초기 비용이나 예산 필터에 합산하지 않습니다."},
        {"id": "cda-deposit-faq", "title": "CDA 보증금 안내 상충", "publisher": "CDA Coliving", "url": "https://cdacoliving.com/faq",
         "note": "FAQ 검색 원문은 보증금 4주, 이용 안내는 보증금 없이 첫 주 월세 납부로 설명해 서로 다릅니다. 계약별 보증금·선납액을 서면 확인하기 전에는 금액을 확정하지 않습니다."},
        {"id": "cda-move-in", "title": "CDA 입주 준비와 보증금 안내", "publisher": "CDA Coliving", "url": "https://cdacoliving.com/how-it-works",
         "note": "가구·공과금·Wi-Fi 포함 안내. 보증금 안내는 FAQ와 상충합니다. 침구·개인용품·짐 운송은 개인별 준비가 필요하며 이사비가 무료라는 뜻은 아닙니다."},
    ]
    for h in data["housing"]:
        h["initial_reference"] = round(h["weekly_rent"] * 6, 2)
        h["initial_reference_note"] = "일반 주거 임대차 참고: 보증금 4주 + 선납 2주. 이 계약의 확정 청구액이 아니며 이사비 등 제외."
        h["deposit_note"] = ("운영사 안내 상충: FAQ는 보증금 4주, 이용 안내는 보증금 없음·첫 주 월세. 계약서로 확인하세요."
                             if h["id"].startswith("cda-") else "해당 호실의 보증금·선납 월세는 공개 원문에서 확정하지 못했습니다. 운영사 계약 견적을 확인하세요.")
        if h["id"] in UKO:
            h["bills_included"] = True
            h["tags"] = [t for t in h["tags"] if t != "공과금 확인 필요"]
            if "공과금 포함" not in h["tags"]:
                h["tags"].append("공과금 포함")
            additions.append({"id": h["id"] + "-bills", "title": h["name"] + " 공과금 포함 근거", "publisher": "UKO", "url": UKO[h["id"]],
                              "note": h["name"] + " 건물 공식 소개에서 공과금 포함을 확인했습니다. 호실별 계약의 포함 범위와 추가 요금은 계약 전에 재확인하세요."})
    for g in data["guides"]:
        if g["id"] == "insurance":
            g.update(url="https://immi.homeaffairs.gov.au/help-support/meeting-our-requirements/health/adequate-health-insurance", checked_at=CHECKED,
                     text="비자 조건에 필요한 의료 보장과 면책·본인부담금을 공식 안내에서 확인하세요. 보험료는 나이·체류기간·보장에 따라 달라 개인 견적을 월 금액으로 입력해야 합니다.")
        elif g["id"] == "work-visa":
            g.update(url="https://immi.homeaffairs.gov.au/visas/already-have-a-visa/check-visa-details-and-conditions/overview", checked_at=CHECKED,
                     title="발급 비자의 근로 조건 확인", text="발급된 비자는 VEVO에서 체류·근로 조건을 확인하세요. 비자 준비 중이라면 내무부 비자 안내에서 취업·인턴 목적에 맞는 종류와 요건을 먼저 확인하세요.")
    ids = {s["id"] for s in additions}
    data["cost_sources"] = [s for s in data.get("cost_sources", []) if s["id"] not in ids] + [{**s, "checked_at": CHECKED} for s in additions]
    return data


if __name__ == "__main__":
    path = ROOT / "app/data/sydney.json"
    data = enrich(json.loads(path.read_text(encoding="utf-8")))
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(encoded, encoding="utf-8")
    (ROOT.parent / "WOOWANGTHON_TEAM_05_FE/data/sydney.json").write_text(encoded, encoding="utf-8")
    print(data["version"])
