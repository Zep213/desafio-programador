import logging

from app.services import tokens

logger = logging.getLogger("quickfiller")


def _eh_liquido(label: str) -> bool:
    return "liquido" in tokens.sem_acento(label).lower().replace(" ", "")


def _parse_valor(valor: str) -> float | None:
    if not valor or "?" in valor:
        return None
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def verificar_totais_holerite(id_: str, pages: list[dict]) -> None:
    """Soma fields[].value e compara com a base 'líquido' impressa. Só loga — nunca corrige o dado."""
    for entrada in pages:
        campos = entrada.get("fields", [])
        if not campos:
            continue

        valores = [_parse_valor(campo["value"]) for campo in campos]
        if any(v is None for v in valores):
            continue
        soma = sum(valores)

        for base in entrada.get("bases", []):
            if not _eh_liquido(base.get("label", "")):
                continue
            total_impresso = _parse_valor(base.get("value", ""))
            if total_impresso is None:
                continue
            delta = round(soma - total_impresso, 2)
            if abs(delta) > 0.01:
                logger.warning(
                    "holerite id=%s page=%s divergencia soma_fields=%.2f base_liquido=%.2f delta=%.2f",
                    id_,
                    entrada.get("page"),
                    soma,
                    total_impresso,
                    delta,
                )
