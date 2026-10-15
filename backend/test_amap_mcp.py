"""Run from any directory to test the actual Amap MCP connection."""
import os
from pathlib import Path

from dotenv import load_dotenv

from app.services.amap_mcp import AmapMCPTool


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.getenv("AMAP_API_KEY", "").strip()
    if not key:
        print("[FAIL] backend/.env 未配置 AMAP_API_KEY")
        return 2
    try:
        tool = AmapMCPTool(key)
        names = [item["name"] for item in tool._available_tools]
        print(f"[OK] MCP 已连接，工具数量: {len(names)}")
        print("工具名称:", ", ".join(names))
        for name, arguments in [
            ("maps_text_search", {"city": "杭州", "keywords": "西湖", "citylimit": "true"}),
            ("maps_weather", {"city": "杭州"}),
        ]:
            if name not in names:
                raise RuntimeError(f"当前 MCP 服务没有项目需要的工具: {name}")
            result = tool.run({"action": "call_tool", "tool_name": name, "arguments": arguments})
            print(f"[RESULT] {name}:", result.replace(key, "[REDACTED]"))
        print("调用已完成，请检查 RESULT 内是否包含高德业务错误码。")
        return 0
    except Exception as exc:
        print("[FAIL]", str(exc).replace(key, "[REDACTED]"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
