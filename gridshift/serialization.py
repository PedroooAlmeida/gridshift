"""JSON exports never include API credentials or environment variables."""
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pydantic import BaseModel


def jsonable(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {k: jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    return value
