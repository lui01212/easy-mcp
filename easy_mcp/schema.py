"""
Automatic JSON Schema generator from Python function signatures and docstrings.
Zero external dependencies.
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, get_type_hints

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def python_type_to_json_type(py_type: Any) -> str:
    """Map python types to JSON schema types."""
    if py_type in TYPE_MAP:
        return TYPE_MAP[py_type]
    
    # Handle typing constructs or strings
    type_str = str(py_type).lower()
    if "str" in type_str:
        return "string"
    if "int" in type_str:
        return "integer"
    if "float" in type_str:
        return "number"
    if "bool" in type_str:
        return "boolean"
    if "list" in type_str:
        return "array"
    if "dict" in type_str:
        return "object"
        
    return "string"


def parse_docstring(docstring: Optional[str]) -> Tuple[str, Dict[str, str]]:
    """
    Extract main description and parameter descriptions from standard Google/Sphinx docstrings.
    """
    if not docstring:
        return "", {}
        
    lines = docstring.strip().splitlines()
    desc_lines = []
    param_docs: Dict[str, str] = {}
    
    in_args_section = False
    current_param = None
    
    for line in lines:
        stripped = line.strip()
        if re.match(r"^(Args|Parameters|Arguments):", stripped, re.IGNORECASE):
            in_args_section = True
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


def function_to_tool_schema(func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspect a python callable and convert it to an MCP tool definition with JSON Schema inputSchema.
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
        json_type = python_type_to_json_type(param_type)
        
        prop_def: Dict[str, Any] = {"type": json_type}
        
        if param_name in param_docs:
            prop_def["description"] = param_docs[param_name]
            
        if param.default is not inspect.Parameter.empty:
            prop_def["default"] = param.default
        else:
            required.append(param_name)
            
        properties[param_name] = prop_def
        
    input_schema = {
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
