from abc import ABC, abstractmethod


class Exporter(ABC):
    @abstractmethod
    def export(self, value: dict, formato: str) -> tuple[bytes, str]:
        raise NotImplementedError
