from dataclasses import dataclass


@dataclass
class Transcricao:
    id: str
    tipo: str
    status: str
    erro: str | None
    value: dict | None
    criado_em: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "status": self.status,
            "erro": self.erro,
            "value": self.value,
        }
