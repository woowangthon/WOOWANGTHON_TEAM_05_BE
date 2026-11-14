import json
from pathlib import Path
import pytest
from scripts.collect_sources import HOUSING, parse_housing, visible_text
from app.models import Profile
from app.planner import build_plan
from tests.test_api import PROFILE


def test_collector_fails_closed_when_prices_are_missing_or_listing_is_removed():
    for text in ['blocked', 'Weekly rent From $ 230 To the CBD 20 minutes', 'no longer available']:
        with pytest.raises(ValueError):
            parse_housing(HOUSING[0], text, '2026-11-13', 216.67)
    assert visible_text('<script>wrong price 1</script><p>Visible</p>') == 'Visible'


def test_unknown_routes_and_costs_are_not_zero_cost_claims():
    plan = build_plan(Profile(**{**PROFILE, 'housing_type': 'studio', 'monthly_budget': 10000, 'max_commute': 1}))
    assert len(plan['options']) == 2
    for option in plan['options']:
        assert option['commute'] is None and not option['commute_verified']
        assert option['utilities'] == 0 and '공과금' not in option['monthly_missing']
        assert {'보증금', '선납 월세', '이사비'} <= set(option['initial_missing'])
        assert not option['is_demo'] and option['source_url'].startswith('https://')


def test_reference_amount_is_not_an_actual_quote_and_unknown_bills_stay_unknown():
    from app.planner import DATA, calculate_budget
    from scripts.enrich_sources import enrich
    import copy
    data = enrich(copy.deepcopy(DATA))
    assert enrich(copy.deepcopy(data)) == data
    for housing in data['housing']:
        assert housing['initial_reference'] == housing['weekly_rent'] * 6
        assert housing['bond'] is None and housing['advance_rent'] is None
    unknown = {**data['housing'][0], 'bills_included': None}
    result = calculate_budget(unknown, Profile(**PROFILE))
    assert result['utilities'] is None and '공과금' in result['monthly_missing']
    assert result['initial'] == 0
    assert calculate_budget({**unknown, 'bills_included': False}, Profile(**PROFILE))['utilities'] == 150
