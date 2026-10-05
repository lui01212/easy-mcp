"""
Automatic JSON Schema generator from Python function signatures and docstrings.
Zero external dependencies.
"""

import collections.abc
import enum
import inspect
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, get_args, get_origin, get_type_hints

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    tuple: "array",
    set: "array",
    frozenset: "array",
    dict: "object",
}

_DOC_SECTION = re.compile(
    r"^(Returns?|Raises|Yields?|Examples?|Notes?|Warnings?|See Also|Todo|References)\s*:",
    re.IGNORECASE,
)


def _is_array_origin(origin: Any) -> bool:
    if not isinstance(origin, type) or issubclass(origin, (str, bytes)):
        return False
    return issubclass(origin, (collections.abc.Sequence, collections.abc.Set))


def python_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Map a Python type hint to a JSON Schema fragment.

    Unknown types fall back to ``{"type": "string"}``.
    """
    if py_type in TYPE_MAP:
        return {"type": TYPE_MAP[py_type]}

    origin = get_origin(py_type)
    args = get_args(py_type)

    if origin is Union:
        non_null = [a for a in args if a is not type(None)]
        if len(non_null) == 1:
            return python_type_to_json_schema(non_null[0])
        return {"type": "string"}

    if origin is not None:
        if origin in (list, tuple, set, frozenset) or _is_array_origin(origin):
            schema: Dict[str, Any] = {"type": "array"}
            item_types = [a for a in args if a is not Ellipsis]
            if len(set(item_types)) == 1:
                schema["items"] = python_type_to_json_schema(item_types[0])
            return schema
        if origin is dict or (isinstance(origin, type) and issubclass(origin, collections.abc.Mapping)):
            return {"type": "object"}
        return {"type": "string"}

    if isinstance(py_type, type):
        if issubclass(py_type, bool):
            return {"type": "boolean"}
        if issubclass(py_type, enum.Enum):
            return {"type": "string"}
        if issubclass(py_type, int):
            return {"type": "integer"}
        if issubclass(py_type, float):
            return {"type": "number"}
        if issubclass(py_type, str):
            return {"type": "string"}
        if issubclass(py_type, collections.abc.Mapping):
            return {"type": "object"}
        if _is_array_origin(py_type):
            return {"type": "array"}

    return {"type": "string"}


def python_type_to_json_type(py_type: Any) -> str:
    """Map Python types and type hints to JSON schema types."""
    return python_type_to_json_schema(py_type)["type"]


def _json_default(value: Any) -> Tuple[bool, Any]:
    """Return (ok, value) for a parameter default that can go into a JSON schema."""
    if isinstance(value, enum.Enum):
        value = value.value
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False, None
    return True, value


def parse_docstring(docstring: Optional[str]) -> Tuple[str, Dict[str, str]]:
    """
    Extract main description and parameter descriptions from docstrings.
    Supports Google, Sphinx, and standard docstrings.
    """
    if not docstring:
        return "", {}

    lines = docstring.strip().splitlines()
    desc_lines = []
    param_docs: Dict[str, str] = {}

    in_args_section = False
    in_other_section = False
    current_param = None

    for line in lines:
        stripped = line.strip()
        if re.match(r"^(Args|Parameters|Arguments):", stripped, re.IGNORECASE):
            in_args_section = True
            in_other_section = False
            continue
        if _DOC_SECTION.match(stripped):
            in_args_section = False
            in_other_section = True
            current_param = None
            continue

        if in_other_section:
            continue
        if in_args_section:
            # Check for param line: "param_name: description" or "param_name (type): description"
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\([^)]+\))?:\s*(.+)$", stripped)
            if m:
                current_param = m.group(1)
                param_docs[current_param] = m.group(2).strip()
            elif current_param and stripped:
                # Continuation line
                param_docs[current_param] += " " + stripped
        else:
            desc_lines.append(stripped)

    main_desc = " ".join(desc_lines).strip()
    return main_desc, param_docs


def function_to_tool_schema(
    func: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inspect a Python callable and convert it to an MCP tool definition with JSON Schema inputSchema.
    """
    tool_name = name or func.__name__
    raw_doc = inspect.getdoc(func) or ""
    main_desc, param_docs = parse_docstring(raw_doc)
    tool_desc = description or main_desc or f"Tool: {tool_name}"

    sig = inspect.signature(func)
    try:
        type_hints = get_type_hints(func)
    except Exception:
        type_hints = {}

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        param_type = type_hints.get(param_name, str)
        prop_def: Dict[str, Any] = python_type_to_json_schema(param_type)

        if param_name in param_docs:
            prop_def["description"] = param_docs[param_name]

        if param.default is not inspect.Parameter.empty:
            ok, default = _json_default(param.default)
            if ok:
                prop_def["default"] = default
        else:
            required.append(param_name)

        properties[param_name] = prop_def

    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return {
        "name": tool_name,
        "description": tool_desc,
        "inputSchema": input_schema
    }


def function_to_prompt_arguments(func: Callable) -> List[Dict[str, Any]]:
    """
    Inspect a Python callable and generate MCP prompt arguments list.
    """
    raw_doc = inspect.getdoc(func) or ""
    _, param_docs = parse_docstring(raw_doc)

    sig = inspect.signature(func)
    arguments: List[Dict[str, Any]] = []

    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        arg_def: Dict[str, Any] = {
            "name": param_name,
            "required": (param.default is inspect.Parameter.empty),
        }
        if param_name in param_docs:
            arg_def["description"] = param_docs[param_name]

        arguments.append(arg_def)

    return arguments
