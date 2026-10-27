"""
Tests for task and purchase order API endpoints.
"""
import copy

import pytest

import main


@pytest.fixture(autouse=True)
def reset_mutable_state():
    """Tasks, purchase orders and backlog PO links are module-level state; restore them around each test."""
    backlog_snapshot = copy.deepcopy(main.backlog_items)
    po_snapshot = copy.deepcopy(main.purchase_orders)
    main.tasks.clear()
    main.task_sequence = 0
    yield
    main.tasks.clear()
    main.task_sequence = 0
    # Restore in place: main holds references to these same list objects
    main.backlog_items[:] = backlog_snapshot
    main.purchase_orders[:] = po_snapshot


def create_task(client, **overrides):
    payload = {"title": "Review Q4 stock", "priority": "high", "dueDate": "2025-10-08"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


def po_payload(backlog_item_id, **overrides):
    payload = {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 350,
        "unit_cost": 12.5,
        "expected_delivery_date": "2025-11-15",
        "notes": "Rush",
    }
    payload.update(overrides)
    return payload


class TestTaskEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_empty(self, client):
        """Test that no tasks exist before any are created."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task returns a pending task with a string ID."""
        response = create_task(client)
        assert response.status_code == 201

        task = response.json()
        assert task["id"] == "TASK-1"
        assert task["title"] == "Review Q4 stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"

    def test_create_task_trims_title(self, client):
        """Test that surrounding whitespace is stripped from the title."""
        response = create_task(client, title="  Approve orders  ")
        assert response.status_code == 201
        assert response.json()["title"] == "Approve orders"

    def test_create_task_blank_title(self, client):
        """Test that a whitespace-only title is rejected."""
        response = create_task(client, title="   ")
        assert response.status_code == 400

    def test_create_task_missing_due_date(self, client):
        """Test that dueDate is required."""
        response = client.post("/api/tasks", json={"title": "No date"})
        assert response.status_code == 422

    def test_get_tasks_newest_first(self, client):
        """Test that tasks are listed newest first."""
        create_task(client, title="First")
        create_task(client, title="Second")

        data = client.get("/api/tasks").json()
        assert [t["title"] for t in data] == ["Second", "First"]

    def test_toggle_task(self, client):
        """Test toggling a task flips its status both ways."""
        task_id = create_task(client).json()["id"]

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.json()["status"] == "pending"

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist."""
        response = client.patch("/api/tasks/TASK-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_task(self, client):
        """Test deleting a task removes it from the list."""
        task_id = create_task(client).json()["id"]

        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist."""
        response = client.delete("/api/tasks/TASK-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client):
        """Test creating a purchase order for a backlog item."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]

        response = client.post("/api/purchase-orders", json=po_payload(backlog_id))
        assert response.status_code == 201

        po = response.json()
        assert po["id"].startswith("PO-")
        assert po["backlog_item_id"] == backlog_id
        assert po["supplier_name"] == "Acme Supply"
        assert po["quantity"] == 350
        assert abs(po["unit_cost"] - 12.5) < 0.01
        assert po["status"] == "Pending"
        assert "T" in po["created_date"]
        assert po["notes"] == "Rush"

    def test_create_purchase_order_links_backlog_item(self, client):
        """Test that the backlog item reports its new purchase order."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        po_id = client.post("/api/purchase-orders", json=po_payload(backlog_id)).json()["id"]

        item = next(b for b in client.get("/api/backlog").json() if b["id"] == backlog_id)
        assert item["has_purchase_order"] is True
        assert item["purchase_order_id"] == po_id

    def test_backlog_items_have_no_purchase_order_by_default(self, client):
        """Test that backlog items start without a linked purchase order."""
        for item in client.get("/api/backlog").json():
            assert item["purchase_order_id"] is None

    def test_create_purchase_order_unknown_backlog_item(self, client):
        """Test creating a purchase order for a backlog item that doesn't exist."""
        response = client.post("/api/purchase-orders", json=po_payload("nonexistent-999"))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_duplicate_purchase_order(self, client):
        """Test that a backlog item can only have one purchase order."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        client.post("/api/purchase-orders", json=po_payload(backlog_id))

        response = client.post("/api/purchase-orders", json=po_payload(backlog_id))
        assert response.status_code == 409

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_create_purchase_order_non_positive_quantity(self, client, quantity):
        """Test that quantity must be positive."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        response = client.post("/api/purchase-orders", json=po_payload(backlog_id, quantity=quantity))
        assert response.status_code == 400

    def test_create_purchase_order_negative_unit_cost(self, client):
        """Test that unit cost cannot be negative."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        response = client.post("/api/purchase-orders", json=po_payload(backlog_id, unit_cost=-1))
        assert response.status_code == 400

    def test_get_purchase_order_by_backlog_item(self, client):
        """Test fetching the purchase order linked to a backlog item."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        created = client.post("/api/purchase-orders", json=po_payload(backlog_id)).json()

        response = client.get(f"/api/purchase-orders/{backlog_id}")
        assert response.status_code == 200
        assert response.json() == created

    def test_get_nonexistent_purchase_order(self, client):
        """Test fetching a purchase order for a backlog item without one."""
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        response = client.get(f"/api/purchase-orders/{backlog_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
