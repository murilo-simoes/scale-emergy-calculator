"""
Testes unitários para o módulo LCIManager.
Abordagem TDD — testa comportamento esperado independente de implementação.
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.lci_manager import (
    LCIProcess, LCIInput, LCIProcessFactory, LCIRepository
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def factory():
    return LCIProcessFactory()


@pytest.fixture
def empty_repo():
    return LCIRepository()


@pytest.fixture
def populated_repo():
    repo = LCIRepository()
    source = LCIProcessFactory.create_source(
        id="solar", name="Energia Solar", unit="J", uev=1.0
    )
    process = LCIProcessFactory.create_process(
        id="electricity", name="Eletricidade", unit="J", uev=159000.0,
        inputs=[LCIInput(process_id="solar", amount=0.3)]
    )
    repo.add_process(source)
    repo.add_process(process)
    return repo


# ── Factory tests ─────────────────────────────────────────────────────────────

class TestLCIProcessFactory:

    def test_create_source_sets_type(self):
        p = LCIProcessFactory.create_source("s1", "Solar", "J", 1.0)
        assert p.process_type == "source"
        assert p.is_source() is True

    def test_create_process_sets_type(self):
        p = LCIProcessFactory.create_process("p1", "Proc", "kg", 1000.0, [])
        assert p.process_type == "process"
        assert p.is_source() is False

    def test_create_from_dict_source(self):
        data = {
            "id": "wind", "name": "Vento", "type": "source",
            "unit": "J", "uev": 623.0, "description": "",
            "inputs": [], "output_amount": 1.0
        }
        p = LCIProcessFactory.create_from_dict(data)
        assert p.id == "wind"
        assert p.uev == 623.0
        assert len(p.inputs) == 0

    def test_create_from_dict_process_with_inputs(self):
        data = {
            "id": "water", "name": "Água", "type": "process",
            "unit": "L", "uev": 2500000.0, "description": "",
            "inputs": [{"process_id": "solar", "amount": 0.5}],
            "output_amount": 1.0
        }
        p = LCIProcessFactory.create_from_dict(data)
        assert len(p.inputs) == 1
        assert p.inputs[0].process_id == "solar"
        assert p.inputs[0].amount == 0.5


# ── Repository tests ──────────────────────────────────────────────────────────

class TestLCIRepository:

    def test_add_and_get_process(self, empty_repo):
        p = LCIProcessFactory.create_source("s1", "Solar", "J", 1.0)
        empty_repo.add_process(p)
        result = empty_repo.get_process("s1")
        assert result is not None
        assert result.id == "s1"

    def test_remove_process(self, populated_repo):
        populated_repo.remove_process("solar")
        assert populated_repo.get_process("solar") is None

    def test_get_sources_returns_only_sources(self, populated_repo):
        sources = populated_repo.get_sources()
        assert all(s.is_source() for s in sources)
        assert len(sources) == 1
        assert sources[0].id == "solar"

    def test_processes_property_returns_copy(self, populated_repo):
        snapshot = populated_repo.processes
        snapshot["injected"] = None
        assert "injected" not in populated_repo.processes

    def test_validate_detects_missing_reference(self, empty_repo):
        p = LCIProcessFactory.create_process(
            "orphan", "Órfão", "kg", 100.0,
            [LCIInput(process_id="nonexistent", amount=1.0)]
        )
        empty_repo.add_process(p)
        errors = empty_repo.validate()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_validate_clean_repo_returns_no_errors(self, populated_repo):
        errors = populated_repo.validate()
        assert errors == []

    def test_validate_negative_uev(self, empty_repo):
        p = LCIProcessFactory.create_source("bad", "Bad", "J", -1.0)
        empty_repo.add_process(p)
        errors = empty_repo.validate()
        assert any("UEV negativo" in e for e in errors)

    def test_observer_notified_on_add(self, empty_repo):
        events = []
        class MockObserver:
            def update(self, event, data):
                events.append(event)

        empty_repo.attach(MockObserver())
        p = LCIProcessFactory.create_source("s1", "Solar", "J", 1.0)
        empty_repo.add_process(p)
        assert "process_added" in events

    def test_save_and_load_roundtrip(self, populated_repo, tmp_path):
        filepath = str(tmp_path / "test_lci.json")
        populated_repo.save_to_file(filepath)

        new_repo = LCIRepository()
        new_repo.load_from_file(filepath)

        assert len(new_repo.get_all_processes()) == len(
            populated_repo.get_all_processes()
        )
        solar = new_repo.get_process("solar")
        assert solar is not None
        assert solar.uev == 1.0
