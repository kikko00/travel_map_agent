"""Local stdio MCP server for regression tests; no network or API key needed."""
from mcp.server.fastmcp import FastMCP

server = FastMCP("regression")


@server.tool()
def echo(value: str) -> str:
    return value


@server.tool()
def business_error() -> dict:
    return {"error": "USERKEY_PLAT_NOMATCH"}


if __name__ == "__main__":
    server.run(transport="stdio")
