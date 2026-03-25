from __future__ import annotations
from typing import Any


def run_middleware(tool_name: str, args: dict, result: Any) -> Any:
    """
    Körs efter varje MCP-tool-anrop.
    Lägg till fler steg här efter behov – t.ex. schema-validering, rate limiting.
    """
    result = _log(tool_name, args, result)
    result = _filter_private_fields(result)
    return result


def _log(tool_name: str, args: dict, result) -> dict | list:
    print(f"  [middleware] {tool_name}({list(args.keys())}) → ok")
    return result


def _filter_private_fields(result) -> dict | list:
    """Tar bort fält som börjar med '_' – interna implementationsdetaljer."""
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if not k.startswith("_")}
    if isinstance(result, list):
        return [_filter_private_fields(item) for item in result]
    return result
