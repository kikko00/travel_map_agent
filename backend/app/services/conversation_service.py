import os
import sqlite3
import threading
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from .conversation_store import ConversationStore, VersionConflict
from .web_search_service import WebSearchService
from ..graphs.conversation_graph import ConversationGraph, validate_plan
from ..graphs.trip_graph import get_langgraph_trip_planner
from ..models.schemas import TripPlan


class ConversationService:
    def __init__(self, data_dir=None, model=None, search=None):
        directory = Path(data_dir or Path(__file__).resolve().parents[2] / "data")
        directory.mkdir(parents=True, exist_ok=True)
        self.store = ConversationStore(directory / "conversations.sqlite3")
        self.checkpoint_connection = sqlite3.connect(directory / "checkpoints.sqlite3", check_same_thread=False)
        self.checkpointer = SqliteSaver(self.checkpoint_connection)
        self.search = search or WebSearchService(directory / "search.sqlite3")
        self.model = model

    def create(self, request, plan=None):
        if plan is None:
            plan = get_langgraph_trip_planner().plan_trip(request)
        if (plan.city, plan.start_date, plan.end_date, len(plan.days)) != (
                request.city, request.start_date, request.end_date, request.travel_days):
            raise ValueError("生成行程与请求的城市、日期或天数不一致。")
        return self.store.create(request, plan)

    def message(self, session_id, content, expected_version):
        with self.store.lock(session_id):
            snapshot = self.store.get(session_id)
            if snapshot["version"] != expected_version:
                raise VersionConflict("会话已更新，请重新载入后再发送。")
            model = self.model or get_langgraph_trip_planner()._get_chat_model()
            if model is None:
                raise RuntimeError("未配置模型密钥，无法继续对话。")
            try:
                result = ConversationGraph(model, self.search, self.checkpointer).run(snapshot, content)
            except (ValueError, KeyError) as exc:
                result = {"reply": f"此次调整未保存，原行程保持不变。{exc}", "plan": snapshot["plan"],
                          "constraints": [], "sources": [], "changed_days": []}
            snapshot["plan"] = result["plan"]
            remaining = [c for c in snapshot["constraints"] if c not in result.get("constraints_remove", [])]
            snapshot["constraints"] = list(dict.fromkeys([*remaining, *result["constraints"]]))
            snapshot["messages"].extend([
                {"role": "user", "content": content, "sources": []},
                {"role": "assistant", "content": result["reply"], "sources": result["sources"],
                 "changed_days": result["changed_days"]},
            ])
            return self.store.save(snapshot, expected_version)

    def update_plan(self, session_id, plan, expected_version):
        with self.store.lock(session_id):
            snapshot = self.store.get(session_id)
            if snapshot["version"] != expected_version:
                raise VersionConflict("会话已更新，请重新载入后再保存。")
            validated = validate_plan(plan, TripPlan.model_validate(snapshot["plan"]))
            snapshot["plan"] = validated.model_dump()
            snapshot["messages"].append({"role": "assistant", "content": "已保存手动编辑的行程，并重新核算预算。", "sources": []})
            return self.store.save(snapshot, expected_version)

    def close(self):
        self.checkpoint_connection.close()


_service = None
_service_lock = threading.Lock()


def get_conversation_service():
    global _service
    with _service_lock:
        if _service is None:
            _service = ConversationService(os.getenv("CONVERSATION_DATA_DIR") or None)
    return _service


def close_conversation_service():
    global _service
    if _service:
        _service.close()
        _service = None
