"""Synchronous adapter with MCP sessions closed before their event loop exits."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import shutil
from typing import Any, Dict, Optional, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class AmapMCPTool:
    def __init__(self, api_key: str, server_command: Optional[List[str]] = None, timeout: float = 90):
        self.api_key = api_key
        self.timeout = timeout
        # amap-mcp-server 0.1.11 pins MCP 1.8.1, whose private Pydantic
        # import is incompatible with recent Pydantic releases. Keep this
        # constraint in uvx's isolated environment, not the API environment.
        self.command = server_command or [
            shutil.which("uvx") or "uvx", "--with", "pydantic==2.10.6",
            "amap-mcp-server==0.1.11",
        ]
        self._available_tools = self._execute({"action": "list_tools"})
        if not self._available_tools:
            raise RuntimeError("高德 MCP 未返回任何工具，请检查服务是否正确启动。")

    async def _operation(self, parameters: Dict[str, Any]):
        params = StdioServerParameters(
            command=self.command[0], args=self.command[1:],
            env={**os.environ, "AMAP_MAPS_API_KEY": self.api_key},
        )
        # Both context managers exit inside the same task and event loop,
        # including when initialize/call_tool fails or the operation times out.
        async def exchange(session):
            await session.initialize()
            if parameters.get("action") == "list_tools":
                tools = (await session.list_tools()).tools
                return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                        for t in tools]
            if parameters.get("action", "call_tool") != "call_tool":
                raise ValueError("仅支持 list_tools 和 call_tool")
            result = await session.call_tool(parameters["tool_name"], parameters.get("arguments", {}))
            parts = [getattr(item, "text", "") for item in result.content]
            content = "\n".join(part for part in parts if part)
            if result.isError:
                raise RuntimeError(content or "MCP 工具返回错误")
            for part in parts:
                try:
                    payload = json.loads(part)
                except ValueError:
                    continue
                if isinstance(payload, dict) and payload.get("error"):
                    raise RuntimeError(str(payload["error"]))
            return content or json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

        timed_out = False
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Only cancel protocol work, not process creation.
                    try:
                        result = await asyncio.wait_for(exchange(session), timeout=self.timeout)
                    except TimeoutError:
                        timed_out = True
        except Exception:
            if timed_out:
                raise TimeoutError("MCP 初始化或调用超时") from None
            raise
        if timed_out:
            raise TimeoutError("MCP 初始化或调用超时")
        return result

    def _execute(self, parameters):
        def run():
            return asyncio.run(self._operation(parameters))

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return run()
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(run).result()
        except Exception as exc:
            def describe(error):
                children = getattr(error, "exceptions", ())
                if children:
                    return "; ".join(describe(child) for child in children)
                return f"{type(error).__name__}: {error}"
            detail = describe(exc)
            if self.api_key:
                detail = detail.replace(self.api_key, "[REDACTED]")
            raise RuntimeError(f"高德 MCP 连接或调用失败: {detail}") from None

    def run(self, parameters: Dict[str, Any]) -> str:
        result = self._execute(parameters)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
