from app.services import tabela as tabela_util
from app.services.exporters.base import Exporter
from app.services.exporters.render import RENDERIZADORES


class HoleriteExporter(Exporter):
    def export(self, value: dict, formato: str) -> tuple[bytes, str]:
        renderizar, mimetype = RENDERIZADORES[formato]
        tabela = tabela_util.montar_tabela("holerite", value)
        return renderizar(tabela), mimetype
