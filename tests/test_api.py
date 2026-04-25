"""
Testes de integração da API REST FastAPI.
Usa TestClient do httpx para simular requisições HTTP sem levantar servidor.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app import app, repository
from modules.lci_manager import LCIProcessFactory, LCIInput

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_repo():
    """Reseta o repositório antes de cada teste para isolamento."""
    repository._processes.clear()
    solar = LCIProcessFactory.create_source("solar", "Energia Solar", "J", 1.0)
    electricity = LCIProcessFactory.create_process(
        "electricity", "Eletricidade", "J", 0.0,
        inputs=[LCIInput("solar", 100.0)]
    )
    repository.add_process(solar)
    repository.add_process(electricity)
    yield


# ── GET /api/processes ────────────────────────────────────────────────────────

class TestListProcesses:

    def test_returns_200(self):
        res = client.get("/api/processes")
        assert res.status_code == 200

    def test_returns_list(self):
        res = client.get("/api/processes")
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_contains_solar(self):
        res = client.get("/api/processes")
        ids = [p["id"] for p in res.json()]
        assert "solar" in ids


# ── POST /api/processes ───────────────────────────────────────────────────────

class TestAddProcess:

    def test_add_source_returns_201(self):
        res = client.post("/api/processes", json={
            "id": "wind", "name": "Vento", "type": "source",
            "unit": "J", "uev": 623.0, "inputs": []
        })
        assert res.status_code == 201

    def test_add_duplicate_returns_409(self):
        client.post("/api/processes", json={
            "id": "wind2", "name": "Vento2", "type": "source",
            "unit": "J", "uev": 1.0, "inputs": []
        })
        res = client.post("/api/processes", json={
            "id": "wind2", "name": "Vento2", "type": "source",
            "unit": "J", "uev": 1.0, "inputs": []
        })
        assert res.status_code == 409

    def test_add_invalid_type_returns_422(self):
        res = client.post("/api/processes", json={
            "id": "bad", "name": "Bad", "type": "invalid_type",
            "unit": "J", "uev": 1.0, "inputs": []
        })
        assert res.status_code == 422


# ── DELETE /api/processes/{id} ────────────────────────────────────────────────

class TestDeleteProcess:

    def test_delete_existing_returns_204(self):
        res = client.delete("/api/processes/solar")
        assert res.status_code == 204

    def test_delete_nonexistent_returns_404(self):
        res = client.delete("/api/processes/nonexistent")
        assert res.status_code == 404


# ── POST /api/simulate ────────────────────────────────────────────────────────

class TestSimulate:

    def test_simulate_returns_200(self):
        res = client.post("/api/simulate", json={
            "target_process_id": "electricity",
            "strategy": "dfs",
            "minflow": 1e-10
        })
        assert res.status_code == 200

    def test_simulate_returns_positive_emergy(self):
        res = client.post("/api/simulate", json={
            "target_process_id": "electricity",
            "strategy": "dfs",
            "minflow": 1e-10
        })
        data = res.json()
        assert data["total_emergy_sej"] > 0

    def test_simulate_invalid_target_returns_400(self):
        res = client.post("/api/simulate", json={
            "target_process_id": "nonexistent",
            "strategy": "dfs",
            "minflow": 1e-6
        })
        assert res.status_code == 400

    def test_simulate_response_contains_indices(self):
        res = client.post("/api/simulate", json={
            "target_process_id": "electricity",
            "strategy": "dfs",
            "minflow": 1e-10
        })
        data = res.json()
        assert "emergy_yield_ratio" in data
        assert "environmental_load_ratio" in data
        assert "sustainability_index" in data
        assert "renewable_fraction" in data

    def test_simulate_contributions_not_empty(self):
        res = client.post("/api/simulate", json={
            "target_process_id": "electricity",
            "strategy": "dfs",
            "minflow": 1e-10
        })
        data = res.json()
        assert len(data["contributions"]) > 0


# ── GET /api/validate ─────────────────────────────────────────────────────────

class TestValidate:

    def test_valid_repo_returns_no_errors(self):
        res = client.get("/api/validate")
        data = res.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_process_count_correct(self):
        res = client.get("/api/validate")
        data = res.json()
        assert data["process_count"] == 2
