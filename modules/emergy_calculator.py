"""
Módulo de Cálculo de Emergia.

Implementa o algoritmo DFS (Depth-First Search) do SCALE e as regras
da Álgebra Emergética conforme Marvuglia et al. (2013) e Odum (1996).

Padrão Strategy: permite trocar o algoritmo de cálculo sem alterar o contexto.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from .lci_manager import LCIRepository, LCIProcess
from .observer import Subject


@dataclass
class EmegyResult:
    """Resultado do cálculo de emergia para um processo."""
    process_id: str
    process_name: str
    emergy_sej: float           # Emergia total em solar emjoules
    uev: float                  # Unit Emergy Value calculado
    unit: str
    contributions: Dict[str, float] = field(default_factory=dict)
    truncated_paths: int = 0    # Caminhos cortados pelo minflow


@dataclass
class SimulationResult:
    """Resultado completo de uma simulação de emergia."""
    target_process_id: str
    total_emergy_sej: float
    minflow_threshold: float
    process_results: Dict[str, EmegyResult] = field(default_factory=dict)
    emergy_yield_ratio: float = 0.0      # EYR = (R + N + F) / F
    environmental_load_ratio: float = 0.0 # ELR = (N + F) / R
    sustainability_index: float = 0.0    # ESI = EYR / ELR
    renewable_fraction: float = 0.0


class EmergyCalculationStrategy(ABC):
    """Interface para estratégias de cálculo de emergia (padrão Strategy)."""

    @abstractmethod
    def calculate(self, repository: LCIRepository, target_id: str,
                  minflow: float) -> SimulationResult:
        pass


class DFSEmergyStrategy(EmergyCalculationStrategy):
    """
    Estratégia DFS (Depth-First Search) baseada no algoritmo SCALE.

    Percorre o grafo de processos em profundidade a partir do nó alvo,
    acumulando contribuições de emergia de cada fonte primária.
    Aplica as 4 regras da Álgebra Emergética de Odum (1996):
      1. Co-produtos recebem a emergia total do processo.
      2. Divisões (splits) são proporcionais ao fluxo físico.
      3. Sem dupla contagem em feedbacks (ciclos são detectados).
      4. Regra de substituição para materiais reciclados.
    """

    def __init__(self):
        self._visited: Set[str] = set()
        self._in_stack: Set[str] = set()  # detecção de ciclos

    def calculate(self, repository: LCIRepository, target_id: str,
                  minflow: float) -> SimulationResult:
        self._repository = repository
        self._minflow = minflow
        self._memo: Dict[str, float] = {}
        self._contributions: Dict[str, Dict[str, float]] = {}
        self._truncated: Dict[str, int] = {}

        target = repository.get_process(target_id)
        if target is None:
            raise ValueError(f"Processo '{target_id}' não encontrado no repositório.")

        self._visited = set()
        self._in_stack = set()
        total_emergy = self._dfs(target_id, scale=1.0)

        results = {}
        for pid, emergy in self._memo.items():
            proc = repository.get_process(pid)
            if proc:
                results[pid] = EmegyResult(
                    process_id=pid,
                    process_name=proc.name,
                    emergy_sej=emergy,
                    uev=emergy / proc.output_amount if proc.output_amount > 0 else 0,
                    unit=proc.unit,
                    contributions=self._contributions.get(pid, {}),
                    truncated_paths=self._truncated.get(pid, 0)
                )

        eyr, elr, esi, ren_frac = self._calculate_indices(
            repository, target_id, total_emergy
        )

        return SimulationResult(
            target_process_id=target_id,
            total_emergy_sej=total_emergy,
            minflow_threshold=minflow,
            process_results=results,
            emergy_yield_ratio=eyr,
            environmental_load_ratio=elr,
            sustainability_index=esi,
            renewable_fraction=ren_frac
        )

    def _dfs(self, process_id: str, scale: float) -> float:
        # Corte pelo threshold minflow (regra de precisão do SCALE)
        if scale < self._minflow:
            return 0.0

        process = self._repository.get_process(process_id)
        if process is None:
            return 0.0

        # Fonte primária: emergia = UEV × escala
        if process.is_source():
            emergy = process.uev * scale
            self._memo[process_id] = self._memo.get(process_id, 0) + emergy
            return emergy

        # Detecção de ciclo (Regra 3 — sem dupla contagem)
        if process_id in self._in_stack:
            return self._memo.get(process_id, 0)

        self._in_stack.add(process_id)
        total = 0.0

        for inp in process.inputs:
            child_scale = scale * inp.amount
            child_emergy = self._dfs(inp.process_id, child_scale)
            total += child_emergy

            contrib = self._contributions.setdefault(process_id, {})
            contrib[inp.process_id] = contrib.get(inp.process_id, 0) + child_emergy

        self._in_stack.discard(process_id)
        self._memo[process_id] = self._memo.get(process_id, 0) + total
        return total

    def _calculate_indices(self, repository: LCIRepository,
                           target_id: str, total_emergy: float):
        """
        Calcula índices emergéticos: EYR, ELR, ESI, fração renovável.
        Fórmulas baseadas em Zhao, Xu & Yu (2024).
        """
        renewable = 0.0
        non_renewable = 0.0
        purchased = 0.0

        for process in repository.get_sources():
            pid = process.id
            contribution = self._memo.get(pid, 0)
            name_lower = process.name.lower()

            if any(kw in name_lower for kw in ["solar", "chuva", "vento", "maré"]):
                renewable += contribution
            elif any(kw in name_lower for kw in ["elétric", "combust", "petról"]):
                purchased += contribution
            else:
                non_renewable += contribution

        r = renewable
        n = non_renewable
        f = purchased if purchased > 0 else 1e-9  # evitar divisão por zero

        eyr = (r + n + f) / f
        elr = (n + f) / r if r > 0 else float('inf')
        esi = eyr / elr if elr > 0 else 0.0
        ren_frac = r / total_emergy if total_emergy > 0 else 0.0

        return eyr, elr, esi, ren_frac


class SimplifiedEmergyStrategy(EmergyCalculationStrategy):
    """
    Estratégia simplificada: UEV direto sem percurso do grafo.

    Usada para estimativas rápidas quando o grafo completo não está disponível.
    Calcula a emergia multiplicando o UEV declarado pelo montante de saída.
    """

    def calculate(self, repository: LCIRepository, target_id: str,
                  minflow: float) -> SimulationResult:
        process = repository.get_process(target_id)
        if process is None:
            raise ValueError(f"Processo '{target_id}' não encontrado.")

        emergy = process.uev * process.output_amount
        result = EmegyResult(
            process_id=target_id,
            process_name=process.name,
            emergy_sej=emergy,
            uev=process.uev,
            unit=process.unit
        )

        return SimulationResult(
            target_process_id=target_id,
            total_emergy_sej=emergy,
            minflow_threshold=minflow,
            process_results={target_id: result}
        )


class EmergySimulator(Subject):
    """
    Contexto do padrão Strategy para simulação de emergia.

    Permite selecionar e trocar a estratégia de cálculo em tempo de execução,
    mantendo a interface consistente para a camada de apresentação.
    """

    STRATEGIES = {
        "dfs": DFSEmergyStrategy,
        "simplified": SimplifiedEmergyStrategy,
    }

    def __init__(self, repository: LCIRepository,
                 strategy_name: str = "dfs"):
        super().__init__()
        self._repository = repository
        self.set_strategy(strategy_name)
        self._last_result: Optional[SimulationResult] = None

    def set_strategy(self, strategy_name: str) -> None:
        if strategy_name not in self.STRATEGIES:
            raise ValueError(
                f"Estratégia '{strategy_name}' desconhecida. "
                f"Opções: {list(self.STRATEGIES.keys())}"
            )
        self._strategy = self.STRATEGIES[strategy_name]()
        self._strategy_name = strategy_name

    @property
    def strategy_name(self) -> str:
        return self._strategy_name

    @property
    def last_result(self) -> Optional[SimulationResult]:
        return self._last_result

    def run(self, target_process_id: str,
            minflow: float = 1e-6) -> SimulationResult:
        self.notify("simulation_started", {
            "target": target_process_id,
            "strategy": self._strategy_name,
            "minflow": minflow
        })

        errors = self._repository.validate()
        if errors:
            self.notify("validation_errors", errors)
            raise ValueError(f"Repositório inválido: {errors}")

        result = self._strategy.calculate(
            self._repository, target_process_id, minflow
        )
        self._last_result = result

        self.notify("simulation_completed", result)
        return result

    def format_result(self, result: SimulationResult) -> str:
        """Formata o resultado de simulação como texto legível."""
        target = self._repository.get_process(result.target_process_id)
        name = target.name if target else result.target_process_id

        lines = [
            "=" * 60,
            f"RESULTADO DA SIMULAÇÃO DE EMERGIA",
            "=" * 60,
            f"Processo alvo : {name}",
            f"Estratégia    : {result.minflow_threshold:.2e} (minflow)",
            f"Emergia total : {result.total_emergy_sej:.4e} sej",
            "",
            "ÍNDICES EMERGÉTICOS",
            "-" * 40,
            f"EYR (Emergy Yield Ratio)         : {result.emergy_yield_ratio:.4f}",
            f"ELR (Environmental Load Ratio)   : {result.environmental_load_ratio:.4f}",
            f"ESI (Emergy Sustainability Index): {result.sustainability_index:.4f}",
            f"Fração renovável                 : {result.renewable_fraction * 100:.1f}%",
            "",
            "CONTRIBUIÇÕES POR PROCESSO",
            "-" * 40,
        ]

        sorted_results = sorted(
            result.process_results.values(),
            key=lambda r: r.emergy_sej,
            reverse=True
        )
        for r in sorted_results:
            pct = (r.emergy_sej / result.total_emergy_sej * 100
                   if result.total_emergy_sej > 0 else 0)
            lines.append(
                f"  {r.process_name:<30} {r.emergy_sej:.4e} sej  ({pct:.1f}%)"
            )

        lines.append("=" * 60)
        return "\n".join(lines)
