from abc import ABC, abstractmethod


class Extractor(ABC):
    @abstractmethod
    def extract(self, caminho: str) -> dict:
        raise NotImplementedError
