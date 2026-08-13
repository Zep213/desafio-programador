from app.services.extractors.base import Extractor


class HoleriteExtractorFake(Extractor):
    def extract(self, caminho: str) -> dict:
        return {
            "pages": [
                {
                    "page": 1,
                    "year": "2024",
                    "month": "01",
                    "fields": [
                        {
                            "code": "0010",
                            "label": "Salário Base",
                            "reference": "220,00",
                            "value": "2.389,77",
                        },
                        {
                            "code": "0998",
                            "label": "INSS",
                            "reference": "",
                            "value": "262,87",
                        },
                    ],
                    "bases": [
                        {"label": "Base INSS", "value": "2.389,77"},
                        {"label": "Valor Líquido", "value": "2.126,90"},
                    ],
                }
            ]
        }
