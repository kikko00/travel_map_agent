import asyncio
from pathlib import Path
import sys
import unittest

from app.services.amap_mcp import AmapMCPTool


class MCPRegressionTests(unittest.TestCase):
    def test_discovery_and_repeated_calls_inside_running_loop(self):
        unraisable = []
        original = sys.unraisablehook
        sys.unraisablehook = unraisable.append
        try:
            async def scenario():
                tool = AmapMCPTool(
                    "test-key", server_command=[sys.executable, str(Path(__file__).with_name("mcp_test_server.py"))]
                )
                self.assertIn("echo", [item["name"] for item in tool._available_tools])
                for value in ["first", "second", "third"]:
                    result = tool.run({"action": "call_tool", "tool_name": "echo", "arguments": {"value": value}})
                    self.assertIn(value, result)
                with self.assertRaises(RuntimeError):
                    tool.run({"action": "call_tool", "tool_name": "unknown", "arguments": {}})
                with self.assertRaisesRegex(RuntimeError, "USERKEY_PLAT_NOMATCH"):
                    tool.run({"action": "call_tool", "tool_name": "business_error", "arguments": {}})
                tool.timeout = 0.001
                with self.assertRaisesRegex(RuntimeError, "TimeoutError"):
                    tool.run({"action": "call_tool", "tool_name": "echo", "arguments": {"value": "timeout"}})
            asyncio.run(scenario())
            import gc
            gc.collect()
            self.assertEqual(unraisable, [])
        finally:
            sys.unraisablehook = original

    def test_startup_failure_is_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "MCP"):
            AmapMCPTool("test-key", server_command=["nonexistent-amap-test-executable"])


if __name__ == "__main__":
    unittest.main()
