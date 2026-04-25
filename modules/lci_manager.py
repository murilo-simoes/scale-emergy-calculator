"""
Módulo de Gerenciamento de Dados LCI (Life Cycle Inventory).

Implementa o padrão Factory para criação de processos e o repositório
de dados conforme especificado no sistema SCALE (Marvuglia et al., 2013).
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .observer import Subject


@dataclass
class LCIInput:
    """Representa uma entrada de um processo LCI."""
    process_id: str
    amount: float


@dataclass
class LCIProcess:
    """
    Representa um processo do inventário do ciclo de vida.

    Cada processo pode ser uma fonte primária de emergia (type='source')
    ou um processo intermediário (type='process').
    """
    id: str
    name: str
    process_type: str          # 'source' ou 'process'
    unit: str
    uev: float                 # Unit Emergy Value (sej/unidade)
    description: str
    inputs: List[LCIInput]
    output_amount: float = 1.0

    def is_source(self) -> bool:
        return self.process_type == "source"


class LCIProcessFactory:
    """
    Factory para criação de processos LCI.

    Padrão Factory (GoF): encapsula a lógica de criação de objetos,
    permitindo instanciar processos fonte ou intermediários de forma uniforme.
    """

    @staticmethod
    def create_from_dict(data: dict) -> LCIProcess:
        inputs = [
            LCIInput(
                process_id=inp["process_id"],
                amount=inp["amount"]
            )
            for inp in data.get("inputs", [])
        ]
        return LCIProcess(
            id=data["id"],
            name=data["name"],
            process_type=data["type"],
            unit=data["unit"],
            uev=data["uev"],
            description=data.get("description", ""),
            inputs=inputs,
            output_amount=data.get("output_amount", 1.0)
        )

    @staticmethod
    def create_source(id: str, name: str, unit: str, uev: float,
                      description: str = "") -> LCIProcess:
        return LCIProcess(
            id=id, name=name, process_type="source",
            unit=unit, uev=uev, description=description, inputs=[]
        )

    @staticmethod
    def create_process(id: str, name: str, unit: str, uev: float,
                       inputs: List[LCIInput], description: str = "",
                       output_amount: float = 1.0) -> LCIProcess:
        return LCIProcess(
            id=id, name=name, process_type="process",
            unit=unit, uev=uev, description=description,
            inputs=inputs, output_amount=output_amount
        )


class LCIRepository(Subject):
    """
    Repositório central para gerenciamento dos dados LCI.

    Suporta operações CRUD de processos, importação/exportação JSON
    e notificação de observadores via padrão Observer.
    """

    def __init__(self):
        super().__init__()
        self._processes: Dict[str, LCIProcess] = {}
        self._factory = LCIProcessFactory()

    @property
    def processes(self) -> Dict[str, LCIProcess]:
        return dict(self._processes)

    def add_process(self, process: LCIProcess) -> None:
        self._processes[process.id] = process
        self.notify("process_added", process)

    def remove_process(self, process_id: str) -> None:
        if process_id in self._processes:
            process = self._processes.pop(process_id)
            self.notify("process_removed", process)

    def get_process(self, process_id: str) -> Optional[LCIProcess]:
        return self._processes.get(process_id)

    def get_all_processes(self) -> List[LCIProcess]:
        return list(self._processes.values())

    def get_sources(self) -> List[LCIProcess]:
        return [p for p in self._processes.values() if p.is_source()]

    def load_from_file(self, filepath: str) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._processes.clear()
        for proc_data in data.get("processes", []):
            process = self._factory.create_from_dict(proc_data)
            self._processes[process.id] = process
        self.notify("repository_loaded", {"count": len(self._processes)})

    def save_to_file(self, filepath: str) -> None:
        data = {
            "metadata": {
                "version": "1.0",
                "description": "Base de dados LCI exportada pelo simulador"
            },
            "processes": [
                {
                    "id": p.id,
                    "name": p.name,
                    "type": p.process_type,
                    "unit": p.unit,
                    "uev": p.uev,
                    "description": p.description,
                    "inputs": [
                        {"process_id": inp.process_id, "amount": inp.amount}
                        for inp in p.inputs
                    ],
                    "output_amount": p.output_amount
                }
                for p in self._processes.values()
            ]
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.notify("repository_saved", {"filepath": filepath})

    def validate(self) -> List[str]:
        """Valida a consistência do repositório. Retorna lista de erros."""
        errors = []
        for process in self._processes.values():
            for inp in process.inputs:
                if inp.process_id not in self._processes:
                    errors.append(
                        f"Processo '{process.id}' referencia entrada "
                        f"inexistente '{inp.process_id}'"
                    )
            if process.uev < 0:
                errors.append(f"Processo '{process.id}' possui UEV negativo")
            if process.output_amount <= 0:
                errors.append(
                    f"Processo '{process.id}' possui output_amount inválido"
                )
        return errors
