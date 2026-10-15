import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes.conversation import router
from app.services.conversation_service import ConversationService
from test_conversations import sample, ScriptedModel, SearchStub, reply


class ConversationAPITests(unittest.TestCase):
    def test_create_restore_message_manual_edit_and_stale_write(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ConversationService(temp, model=ScriptedModel([
                reply({"intent": "answer"}), reply({"reply": "已记住当前行程"})
            ]), search=SearchStub())
            app = FastAPI()
            app.include_router(router, prefix="/api")
            try:
                with patch('app.api.routes.conversation.get_conversation_service', return_value=service), TestClient(app) as client:
                    request, plan = sample()
                    created = client.post('/api/conversations', json={"request": request.model_dump(), "plan": plan.model_dump()})
                    self.assertEqual(created.status_code, 200)
                    session = created.json()
                    base = '/api/conversations/' + session['id']
                    self.assertEqual(client.get(base).json()['plan'], session['plan'])
                    self.assertEqual(len(client.get('/api/conversations').json()), 1)
                    self.assertEqual(client.post(base+'/messages', json={"content": " ", "expected_version": 1}).status_code, 422)
                    answered = client.post(base+'/messages', json={"content": "现在行程怎样", "expected_version": 1})
                    self.assertEqual(answered.status_code, 200)
                    self.assertEqual(answered.json()['version'], 2)
                    self.assertEqual(client.patch(base+'/plan', json={"plan": plan.model_dump(), "expected_version": 1}).status_code, 409)
                    self.assertEqual(client.patch(base+'/plan', json={"plan": plan.model_dump(), "expected_version": 2}).status_code, 200)
                    self.assertEqual(client.get('/api/conversations/missing').status_code, 404)
            finally:
                service.close()
