from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, value: str) -> str:
        if not ObjectId.is_valid(value):
            raise ValueError(f"'{value}' is not a valid ObjectId")
        return str(value)


def is_valid_object_id(value: str) -> bool:
    try:
        return ObjectId.is_valid(value)
    except InvalidId:
        return False
