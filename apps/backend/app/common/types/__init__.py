"""Shared TypedDict and type alias definitions."""

from typing import Any, TypeAlias

# JSON-serialisable value types
JsonValue: TypeAlias = str | int | float | bool | None | dict[str, Any] | list[Any]
JsonDict: TypeAlias = dict[str, JsonValue]

# Aggregation pipeline type
MongoPipeline: TypeAlias = list[dict[str, Any]]
