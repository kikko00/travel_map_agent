import json
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError
import httpx
from openai import APITimeoutError

from app.graphs.trip_graph import LangGraphTripPlanner
from app.api.routes.conversation import router
from app.models.schemas import TripRequest
from test_conversations import sample


class PlannerFailureTests(unittest.TestCase):
    def planner(self, responses):
        planner = LangGraphTripPlanner()
        model = Mock()
        model.invoke.side_effect = responses
        planner._get_chat_model = Mock(return_value=model)
        planner._call_amap_tool = Mock(return_value='{}')
        return planner, model

    def test_timeout_stops_after_one_call_without_fallback(self):
        planner, model = self.planner([TimeoutError('timeout')])
        request, _ = sample()
        with self.assertRaises(TimeoutError):
            planner.plan_trip(request)
        self.assertEqual(model.invoke.call_count, 1)

    def test_empty_output_does_not_trigger_repair(self):
        planner, model = self.planner([AIMessage(content='')])
        request, _ = sample()
        with self.assertRaises(RuntimeError):
            planner.plan_trip(request)
        self.assertEqual(model.invoke.call_count, 1)

    def test_sdk_timeout_and_failed_repair(self):
        request, _ = sample()
        planner, model = self.planner([APITimeoutError(request=httpx.Request('POST', 'https://example.com'))])
        with self.assertRaises(TimeoutError):
            planner.plan_trip(request)
        self.assertEqual(model.invoke.call_count, 1)
        planner, model = self.planner([AIMessage(content='not JSON'), AIMessage(content='still not JSON')])
        with self.assertRaises(RuntimeError):
            planner.plan_trip(request)
        self.assertEqual(model.invoke.call_count, 2)

    def test_model_uses_configurable_timeout_without_sdk_retry(self):
        from app.config import Settings
        settings = Settings(_env_file=None, llm_timeout=150, llm_max_retries=0)
        with patch.dict('os.environ', {'LLM_API_KEY': 'test-only'}), patch('app.graphs.trip_graph.get_settings', return_value=settings):
            model = LangGraphTripPlanner()._get_chat_model()
            self.assertEqual(model.request_timeout.read, 150)
            self.assertEqual(model.request_timeout.connect, 10)
            self.assertEqual(model.max_retries, 0)

    def test_inconsistent_plan_is_repaired_once(self):
        request, valid = sample()
        wrong = valid.model_copy(update={'city': '北京'})
        planner, model = self.planner([AIMessage(content=wrong.model_dump_json()), AIMessage(content=valid.model_dump_json())])
        self.assertEqual(planner.plan_trip(request).city, request.city)
        self.assertEqual(model.invoke.call_count, 2)

    def test_invalid_request_dates_rejected_before_planning(self):
        request, _ = sample()
        for values in [{'start_date': 'bad'}, {'travel_days': 3}, {'end_date': '2026-10-19'}]:
            with self.assertRaises(ValidationError):
                TripRequest.model_validate({**request.model_dump(), **values})

    def test_api_timeout_is_504_not_422(self):
        app = FastAPI()
        app.include_router(router, prefix='/api')
        request, _ = sample()
        service = Mock()
        service.create.side_effect = TimeoutError('timeout')
        with patch('app.api.routes.conversation.get_conversation_service', return_value=service), TestClient(app) as client:
            response = client.post('/api/conversations', json={'request': request.model_dump()})
            self.assertEqual(response.status_code, 504)
            self.assertIn('超时', response.json()['detail'])
