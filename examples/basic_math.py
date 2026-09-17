"""
Simple Math MCP Server example using easy-mcp.
"""

from easy_mcp import EasyMCP

mcp = EasyMCP("math-server", version="1.0.0", description="Math tools for Claude")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: The first number
        b: The second number
    """
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.
    
    Args:
        a: The first number
        b: The second number
    """
    return a * b


@mcp.tool()
def power(base: float, exponent: float = 2.0) -> float:
    """Calculate base raised to the power of exponent.
    
    Args:
        base: The base number
        exponent: Exponent (default: 2.0)
    """
    return base ** exponent


if __name__ == "__main__":
    mcp.run()
