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
        assert option['utilities'] is None and '공과금' in option['monthly_missing']
        assert {'보증금', '선납 월세', '이사비'} <= set(option['initial_missing'])
        assert not option['is_demo'] and option['source_url'].startswith('https://')
