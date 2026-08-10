from app.modules.finance_os.domain_intelligence.assets.asset_classifier import classify_asset
from app.modules.finance_os.domain_intelligence.assets.useful_life_recommender import recommend_useful_life
from app.modules.erp.assets.engine.asset_lifecycle_engine import (
    ensure_capitalizable,
    ensure_depreciable,
    next_status_after_depreciation,
)
from app.modules.erp.assets.engine.depreciation_engine import compute_depreciation, monthly_straight_line
from app.modules.erp.assets.engine.disposal_engine import compute_gain_loss
from app.modules.erp.assets.validators.capitalization_validator import validate_capitalization, validate_impairment
from app.services.event_consumers import _handle_asset_workflow_approval


def test_monthly_straight_line() -> None:
    assert monthly_straight_line(cost=120000, salvage_value=20000, useful_life_months=36) == 2777.78


def test_compute_depreciation() -> None:
    amt = compute_depreciation(
        cost=120000, salvage_value=20000, useful_life_months=36,
        accumulated_depreciation=0, book_value=120000,
    )
    assert amt == 2777.78


def test_compute_depreciation_fully_depreciated() -> None:
    amt = compute_depreciation(
        cost=1000, salvage_value=200, useful_life_months=36,
        accumulated_depreciation=800, book_value=200,
    )
    assert amt == 0


def test_classify_laptop() -> None:
    result = classify_asset("Dell Latitude Laptop 7420")
    assert result["category_code"] == "COMPUTERS"


def test_useful_life_recommendation() -> None:
    assert recommend_useful_life({"category_code": "BUILDINGS"}) == 240


def test_gain_on_disposal() -> None:
    assert compute_gain_loss(sale_amount=70000, book_value=50000) == 20000


def test_loss_on_disposal() -> None:
    assert compute_gain_loss(sale_amount=30000, book_value=50000) == -20000


def test_capitalization_threshold() -> None:
    try:
        validate_capitalization(cost=10000, useful_life_months=36, threshold=50000)
        assert False
    except ValueError:
        assert True


def test_capitalizable_status() -> None:
    ensure_capitalizable("draft")
    try:
        ensure_capitalizable("active")
        assert False
    except ValueError:
        assert True


def test_depreciable_status() -> None:
    ensure_depreciable("active")
    try:
        ensure_depreciable("draft")
        assert False
    except ValueError:
        assert True


def test_next_status_fully_depreciated() -> None:
    assert next_status_after_depreciation(book_value=100, salvage_value=100) == "fully_depreciated"


def test_impairment_validator() -> None:
    try:
        validate_impairment(impairment_amount=600, book_value=500)
        assert False
    except ValueError:
        assert True


def test_asset_workflow_unknown() -> None:
    assert _handle_asset_workflow_approval("org", {"entity_type": "other"}) is False
