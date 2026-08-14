from app.services.exporters.cartao_ponto import CartaoPontoExporter
from app.services.exporters.holerite import HoleriteExporter

EXPORTERS = {
    "cartao-ponto": CartaoPontoExporter(),
    "holerite": HoleriteExporter(),
}
