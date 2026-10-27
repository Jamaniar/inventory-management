"""
Tests for restocking API endpoints.
"""
from datetime import datetime, timedelta
from itertools import combinations

import pytest

import main


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Restock orders are module-level state; clear them around each test."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


def get_candidates(client):
    """Non-decreasing forecasts sized to forecasted demand, as the API defines them."""
    forecasts = client.get("/api/demand").json()
    return [
        {"sku": f["item_sku"], "units": f["forecasted_demand"],
         "cost": round(f["forecasted_demand"] * f["unit_cost"], 2)}
        for f in forecasts if f["trend"] != "decreasing"
    ]


class TestRestockRecommendations:
    """Test suite for the restock recommendations endpoint."""

    def test_demand_forecasts_have_pricing(self, client):
        """Test that every forecast has a unit cost and lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        for forecast in response.json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0

    def test_get_recommendations_structure(self, client):
        """Test the recommendation response structure."""
        response = client.get("/api/restock/recommendations?budget=10000")
        assert response.status_code == 200

        data = response.json()
        for field in ["budget", "max_budget", "items", "total_cost", "total_units", "remaining_budget"]:
            assert field in data

        for item in data["items"]:
            for field in ["sku", "name", "trend", "quantity", "unit_cost", "line_total", "lead_time_days"]:
                assert field in item
            assert abs(item["line_total"] - item["quantity"] * item["unit_cost"]) < 0.01

    def test_zero_budget_returns_no_items(self, client):
        """Test that a zero budget recommends nothing."""
        response = client.get("/api/restock/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["total_units"] == 0

    def test_max_budget_returns_all_candidates(self, client):
        """Test that a budget covering everything recommends every candidate."""
        candidates = get_candidates(client)
        max_budget = client.get("/api/restock/recommendations?budget=0").json()["max_budget"]
        assert abs(max_budget - sum(c["cost"] for c in candidates)) < 0.01

        data = client.get(f"/api/restock/recommendations?budget={max_budget}").json()
        assert {i["sku"] for i in data["items"]} == {c["sku"] for c in candidates}
        assert abs(data["remaining_budget"]) < 0.01

    def test_decreasing_items_excluded(self, client):
        """Test that decreasing-demand items are never recommended."""
        data = client.get("/api/restock/recommendations?budget=1000000").json()
        for item in data["items"]:
            assert item["trend"] != "decreasing"

    @pytest.mark.parametrize("budget", [500, 5000, 12345.67, 30000, 50000])
    def test_recommendation_is_unit_optimal_within_budget(self, client, budget):
        """Test the recommendation stays within budget and maximizes units."""
        data = client.get(f"/api/restock/recommendations?budget={budget}").json()
        assert data["total_cost"] <= budget
        assert abs(data["total_cost"] - sum(i["line_total"] for i in data["items"])) < 0.01
        assert data["total_units"] == sum(i["quantity"] for i in data["items"])
        assert abs(data["remaining_budget"] - (budget - data["total_cost"])) < 0.01

        # Independently enumerate subsets to confirm no affordable set covers more units
        candidates = get_candidates(client)
        best_units = max(
            (sum(c["units"] for c in subset)
             for size in range(len(candidates) + 1)
             for subset in combinations(candidates, size)
             if sum(c["cost"] for c in subset) <= budget),
            default=0,
        )
        assert data["total_units"] == best_units

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget returns 400."""
        response = client.get("/api/restock/recommendations?budget=-1")
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_missing_budget_rejected(self, client):
        """Test that budget is a required parameter."""
        response = client.get("/api/restock/recommendations")
        assert response.status_code == 422


class TestRestockOrders:
    """Test suite for submitting and listing restock orders."""

    def test_get_restock_orders_empty(self, client):
        """Test that no orders exist before any are submitted."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Test submitting an order computes totals and lead time server-side."""
        forecasts = {f["item_sku"]: f for f in client.get("/api/demand").json()}
        payload = {"items": [{"sku": "GSK-203", "quantity": 100}, {"sku": "CTL-330", "quantity": 5}]}

        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert len(order["items"]) == 2

        expected_total = 100 * forecasts["GSK-203"]["unit_cost"] + 5 * forecasts["CTL-330"]["unit_cost"]
        assert abs(order["total_cost"] - expected_total) < 0.01

        expected_lead = max(forecasts["GSK-203"]["lead_time_days"], forecasts["CTL-330"]["lead_time_days"])
        assert order["lead_time_days"] == expected_lead

        submitted = datetime.fromisoformat(order["submitted_date"])
        delivery = datetime.fromisoformat(order["expected_delivery"])
        assert delivery - submitted == timedelta(days=expected_lead)

    def test_created_order_appears_in_list(self, client):
        """Test that submitted orders are listed newest first."""
        first = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": 10}]}).json()
        second = client.post("/api/restock-orders", json={"items": [{"sku": "BRG-102", "quantity": 10}]}).json()

        data = client.get("/api/restock-orders").json()
        assert [o["id"] for o in data] == [second["id"], first["id"]]
        assert first["order_number"] != second["order_number"]

    def test_create_order_unknown_sku(self, client):
        """Test that an unknown SKU returns 400 and nothing is stored."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}]})
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]
        assert client.get("/api/restock-orders").json() == []

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_create_order_non_positive_quantity(self, client, quantity):
        """Test that zero or negative quantities are rejected."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": quantity}]})
        assert response.status_code == 400

    def test_create_order_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restock-orders", json={"items": []})
        assert response.status_code == 400
