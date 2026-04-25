"""
Módulo Observer — padrão de projeto para notificação de eventos entre módulos.
"""
from abc import ABC, abstractmethod
from typing import List, Any


class Observer(ABC):
    """Interface para observadores de eventos."""

    @abstractmethod
    def update(self, event: str, data: Any) -> None:
        pass


class Subject:
    """Sujeito que notifica observadores sobre mudanças de estado."""

    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, event: str, data: Any = None) -> None:
        for observer in self._observers:
            observer.update(event, data)


class CalculationObserver(Observer):
    """Observador que registra eventos de cálculo para log e interface."""

    def __init__(self):
        self.log: List[dict] = []
        self._callbacks = {}

    def on(self, event: str, callback) -> None:
        self._callbacks[event] = callback

    def update(self, event: str, data: Any) -> None:
        self.log.append({"event": event, "data": data})
        if event in self._callbacks:
            self._callbacks[event](data)
