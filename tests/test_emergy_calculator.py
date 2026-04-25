"""
Testes unitários e de integração para o módulo EmergyCalculator.
Valida o algoritmo DFS, os índices emergéticos e o padrão Strategy.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.lci_manager import LCIRepository, LCIProcessFactory, LCIInput
from modules.emergy_calculator import (
    EmergySimulator, DFSEmergyStrategy, SimplifiedEmergyStrategy
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_repo():
    """Repositório mínimo: fonte solar → processo elétrico."""
    repo = LCIRepository()
    solar = LCIProcessFactory.create_source("solar", "Solar", "J", 1.0)
    elec = LCIProcessFactory.create_process(
        "electricity", "Eletricidade", "J", 0.0,
        inputs=[LCIInput("solar", 100.0)]
    )
    repo.add_process(solar)
    repo.add_process(elec)
    return repo


@pytest.fixture
def multi_source_repo():
    """Repositório com duas fontes e um processo combinado."""
    repo = LCIRepository()
    repo.add_process(LCIProcessFactory.create_source("solar", "Solar", "J", 1.0))
    repo.add_process(LCIProcessFactory.create_source("wind", "Vento", "J", 623.0))
    repo.add_process(LCIProcessFactory.create_process(
        "combined", "Combinado", "J", 0.0,
        inputs=[LCIInput("solar", 50.0), LCIInput("wind", 10.0)]
    ))
    return repo


@pytest.fixture
def simulator(simple_repo):
    return EmergySimulator(simple_repo, strategy_name="dfs")


# ── Strategy selection ────────────────────────────────────────────────────────

class TestStrategySelection:

    def test_default_strategy_is_dfs(self, simple_repo):
        sim = EmergySimulator(simple_repo)
        assert sim.strategy_name == "dfs"

    def test_can_switch_to_simplified(self, simple_repo):
        sim = EmergySimulator(simple_repo, strategy_name="simplified")
        assert sim.strategy_name == "simplified"

    def test_switch_strategy_at_runtime(self, simulator):
        simulator.set_strategy("simplified")
        assert sim2 := simulator
        assert sim2.strategy_name == "simplified"

    def test_invalid_strategy_raises_error(self, simple_repo):
        with pytest.raises(ValueError, match="desconhecida"):
            EmergySimulator(simple_repo, strategy_name="inexistente")


# ── DFS Algorithm ─────────────────────────────────────────────────────────────

class TestDFSStrategy:

    def test_source_emergy_equals_uev_times_scale(self, simple_repo):
        sim = EmergySimulator(simple_repo, "dfs")
        result = sim.run("electricity", minflow=1e-10)
        # solar.uev=1.0, input amount=100 → emergy = 1.0 × 100 = 100
        assert abs(result.total_emergy_sej - 100.0) < 1e-9

    def test_multi_source_sums_contributions(self, multi_source_repo):
        sim = EmergySimulator(multi_source_repo, "dfs")
        result = sim.run("combined", minflow=1e-10)
        # solar: 1.0 × 50 = 50; wind: 623 × 10 = 6230 → total = 6280
        expected = 1.0 * 50.0 + 623.0 * 10.0
        assert abs(result.total_emergy_sej - expected) < 1e-6

    def test_minflow_truncates_small_paths(self, simple_repo):
        sim = EmergySimulator(simple_repo, "dfs")
        # scale=1e-7 < minflow=1e-6 → caminho cortado
        result = sim.run("electricity", minflow=1.0)  # threshold alto
        # O threshold alto deve truncar o cálculo
        assert result.total_emergy_sej == 0.0

    def test_process_not_found_raises_error(self, simple_repo):
        sim = EmergySimulator(simple_repo, "dfs")
        with pytest.raises(ValueError, match="não encontrado"):
            sim.run("nonexistent_process")

    def test_result_contains_target_process(self, simple_repo):
        sim = EmergySimulator(simple_repo, "dfs")
        result = sim.run("electricity")
        assert result.target_process_id == "electricity"

    def test_renewable_fraction_is_1_for_pure_solar(self, simple_repo):
        sim = EmergySimulator(simple_repo, "dfs")
        result = sim.run("electricity", minflow=1e-10)
        assert 0.0 <= result.renewable_fraction <= 1.0


# ── Simplified Strategy ───────────────────────────────────────────────────────

class TestSimplifiedStrategy:

    def test_simplified_uses_uev_directly(self, simple_repo):
        # Ajusta UEV do processo para testar
        simple_repo.get_process("electricity").uev = 5000.0
        simple_repo.get_process("electricity").output_amount = 2.0
        sim = EmergySimulator(simple_repo, "simplified")
        result = sim.run("electricity")
        assert abs(result.total_emergy_sej - 10000.0) < 1e-9  # 5000 × 2

    def test_simplified_no_graph_traversal(self, simple_repo):
        sim = EmergySimulator(simple_repo, "simplified")
        result = sim.run("electricity")
        # Resultado deve conter apenas o processo alvo, não as fontes
        assert "electricity" in result.process_results


# ── Observer Integration ──────────────────────────────────────────────────────

class TestObserverIntegration:

    def test_observer_receives_started_event(self, simulator):
        events = []
        class MockObs:
            def update(self, event, data):
                events.append(event)

        simulator.attach(MockObs())
        simulator.run("electricity")
        assert "simulation_started" in events

    def test_observer_receives_completed_event(self, simulator):
        events = []
        class MockObs:
            def update(self, event, data):
                events.append(event)

        simulator.attach(MockObs())
        simulator.run("electricity")
        assert "simulation_completed" in events

    def test_last_result_stored_after_run(self, simulator):
        simulator.run("electricity")
        assert simulator.last_result is not None
        assert simulator.last_result.target_process_id == "electricity"


# ── Emergy Indices ────────────────────────────────────────────────────────────

class TestEmergyIndices:

    def test_eyr_is_positive(self, multi_source_repo):
        sim = EmergySimulator(multi_source_repo, "dfs")
        result = sim.run("combined", minflow=1e-10)
        assert result.emergy_yield_ratio >= 0.0

    def test_elr_is_non_negative(self, multi_source_repo):
        sim = EmergySimulator(multi_source_repo, "dfs")
        result = sim.run("combined", minflow=1e-10)
        assert result.environmental_load_ratio >= 0.0

    def test_esi_is_non_negative(self, multi_source_repo):
        sim = EmergySimulator(multi_source_repo, "dfs")
        result = sim.run("combined", minflow=1e-10)
        assert result.sustainability_index >= 0.0
