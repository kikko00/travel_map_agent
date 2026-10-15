import tempfile
import unittest
import json
from pathlib import Path

from app.services.conversation_store import ConversationStore, VersionConflict
from app.models.schemas import TripRequest, TripPlan, DayPlan, Hotel, Meal
from app.graphs.conversation_graph import merge_changes
from app.services.conversation_service import ConversationService
from app.services.web_search_service import WebSearchService
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
import httpx


class ScriptedModel:
    def __init__(self, responses):
        self.responses = responses
        self.prompts = []

    def bind_tools(self, tools):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


class SearchStub:
    def as_tool(self):
        @tool
        def search_attraction_info(city: str, attraction_name: str, visit_date: str = "", information_type: str = "") -> dict:
            """Test search evidence."""
            return {"available": True, "retrieved_at": "2026-10-14",
                    "sources": [{"title": "官方参观须知", "url": "https://example.com/visit", "snippet": "9点开放"}]}
        return search_attraction_info


def reply(data):
    return AIMessage(content=json.dumps(data, ensure_ascii=False))


def sample():
    request = TripRequest(city="杭州", start_date="2026-10-20", end_date="2026-10-21", travel_days=2,
                          transportation="公共交通", accommodation="经济型酒店")
    plan = TripPlan(city=request.city, start_date=request.start_date, end_date=request.end_date,
                    overall_suggestions="建议", days=[DayPlan(date=f"2026-10-{20+i}", day_index=i,
                    description=f"第{i+1}天", transportation=request.transportation,
                    accommodation=request.accommodation) for i in range(2)])
    return request, plan


class ConversationTests(unittest.TestCase):
    def test_restart_isolation_and_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sessions.db"
            request, plan = sample()
            store = ConversationStore(path)
            first = store.create(request, plan)
            second = store.create(request, plan)
            first["messages"].append({"role": "user", "content": "第二天轻松一点"})
            store.save(first, 1)
            reopened = ConversationStore(path)
            self.assertEqual(len(reopened.get(first["id"])["messages"]), 2)
            self.assertEqual(len(reopened.get(second["id"])["messages"]), 1)
            with self.assertRaises(VersionConflict):
                reopened.save(first, 1)

    def test_local_change_preserves_other_day_and_rejects_wrong_date(self):
        _, plan = sample()
        changed = plan.days[1].model_copy(update={"description": "博物馆"})
        result = merge_changes(plan, [changed], [1])
        self.assertEqual(result.days[0], plan.days[0])
        self.assertEqual(plan.days[1].description, "第2天")
        with self.assertRaises(ValueError):
            merge_changes(plan, [changed], [0])
        with self.assertRaises(ValueError):
            merge_changes(plan, [changed.model_copy(update={"date": "2026-01-01"})], [1])

    def test_question_then_edit_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            request, plan = sample()
            changed = plan.days[1].model_copy(update={"description": "博物馆"})
            model = ScriptedModel([
                reply({"intent": "answer"}), reply({"reply": "第一天行程较轻松"}),
                reply({"intent": "modify_plan", "target_days": [1]}),
                reply({"reply": "已调整第二天", "constraints": ["不要爬山"], "changes": [changed.model_dump()]}),
            ])
            service = ConversationService(temp, model=model, search=SearchStub())
            try:
                snapshot = service.create(request, plan)
                answered = service.message(snapshot["id"], "第一天会不会太赶", 1)
                self.assertEqual(answered["plan"], snapshot["plan"])
                edited = service.message(snapshot["id"], "第二天换成博物馆，不要爬山", 2)
                self.assertEqual(edited["plan"]["days"][0], snapshot["plan"]["days"][0])
                self.assertEqual(edited["plan"]["days"][1]["description"], "博物馆")
                self.assertIn("不要爬山", edited["constraints"])
                self.assertIn("第一天会不会太赶", model.prompts[2])
                self.assertIsNotNone(service.checkpointer.get_tuple({"configurable": {"thread_id": snapshot["id"]}}))
            finally:
                service.close()
            reopened = ConversationService(temp, model=model, search=SearchStub())
            self.assertEqual(reopened.store.get(snapshot["id"])["version"], 3)
            reopened.close()

    def test_dynamic_search_citations_and_invalid_edit_preserves_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            request, plan = sample()
            model = ScriptedModel([
                reply({"intent": "answer", "requires_search": True}),
                AIMessage(content="", tool_calls=[{"name": "search_attraction_info", "args": {"city": "杭州", "attraction_name": "博物馆"}, "id": "search-1", "type": "tool_call"}]),
                reply({"reply": "参观须知显示9点开放，请以官方公告为准。"}),
                reply({"intent": "modify_plan", "target_days": [0]}),
                reply({"reply": "已修改", "changes": [plan.days[1].model_dump()]}),
            ])
            service = ConversationService(temp, model=model, search=SearchStub())
            try:
                snapshot = service.create(request, plan)
                answered = service.message(snapshot["id"], "博物馆几点开放", 1)
                self.assertEqual(answered["messages"][-1]["sources"][0]["url"], "https://example.com/visit")
                rejected = service.message(snapshot["id"], "修改第一天", 2)
                self.assertEqual(rejected["plan"], snapshot["plan"])
                self.assertIn("未保存", rejected["messages"][-1]["content"])
            finally:
                service.close()

    def test_search_missing_key_cache_and_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "search.db"
            self.assertFalse(WebSearchService(path, api_key="").search("杭州", "西湖")["available"])
            calls = []
            def handle(request):
                calls.append(request)
                return httpx.Response(200, json={"results": [
                    {"title": "官方", "url": "https://example.com/visit", "content": "参观须知"},
                    {"title": "bad", "url": "javascript:alert(1)", "content": "bad"}]})
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                search = WebSearchService(path, api_key="test", client=client)
                first = search.search("杭州", "西湖")
                self.assertEqual(len(first["sources"]), 1)
                self.assertEqual(search.search("杭州", "西湖"), first)
                self.assertEqual(len(calls), 1)
            with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as client:
                self.assertFalse(WebSearchService(path, api_key="bad", client=client).search("杭州", "新景点")["available"])

    def test_partial_day_keeps_hotel_and_meals(self):
        _, plan = sample()
        plan.days[1].hotel = Hotel(name="原酒店", estimated_cost=200)
        plan.days[1].meals = [Meal(type="lunch", name="原午餐", estimated_cost=50)]
        replacement = DayPlan(date=plan.days[1].date, day_index=1, description="轻松游览",
                              transportation="公共交通", accommodation="经济型酒店")
        edited = merge_changes(plan, [replacement], [1])
        self.assertEqual(edited.days[1].hotel, plan.days[1].hotel)
        self.assertEqual(edited.days[1].meals, plan.days[1].meals)

    def test_explicit_constraint_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            request, plan = sample()
            model = ScriptedModel([
                reply({"intent": "answer"}), reply({"reply": "已记录", "constraints": ["不要爬山"]}),
                reply({"intent": "answer"}), reply({"reply": "已更新", "constraints_remove": ["不要爬山"], "constraints": ["可以安排爬山"]}),
            ])
            service = ConversationService(temp, model=model, search=SearchStub())
            try:
                snapshot = service.create(request, plan)
                service.message(snapshot["id"], "记住不要爬山", 1)
                updated = service.message(snapshot["id"], "撤销不要爬山的要求，可以安排爬山", 2)
                self.assertNotIn("不要爬山", updated["constraints"])
                self.assertIn("可以安排爬山", updated["constraints"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
