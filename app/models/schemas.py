from typing import Any

from pydantic import BaseModel


class AtualizarValueRequest(BaseModel):
    value: dict[str, Any]
