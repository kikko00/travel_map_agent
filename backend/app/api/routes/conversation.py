from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import APITimeoutError
import httpx

from ...models.schemas import TripRequest, TripPlan
from ...models.conversation import MessageRequest, PlanUpdate
from ...services.conversation_service import get_conversation_service
from ...services.conversation_store import VersionConflict
from ...services.planning_errors import ModelServiceError

router = APIRouter(prefix="/conversations", tags=["旅行会话"])


class CreateConversation(BaseModel):
    request: TripRequest
    plan: Optional[TripPlan] = None


def perform(action):
    try:
        return action()
    except VersionConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except KeyError:
        raise HTTPException(404, "会话不存在。") from None
    except (TimeoutError, APITimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "大模型或外部服务响应超时，本次未保存修改。请稍后重试或调整 LLM_TIMEOUT。") from None
    except ModelServiceError as exc:
        raise HTTPException(502, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(502, "模型或外部服务调用失败，原有行程已保留，请稍后重试并检查服务配置。") from None


@router.post("")
def create_conversation(body: CreateConversation):
    return perform(lambda: get_conversation_service().create(body.request, body.plan))


@router.get("")
def list_conversations():
    return get_conversation_service().store.list()


@router.get("/{session_id}")
def get_conversation(session_id: str):
    return perform(lambda: get_conversation_service().store.get(session_id))


@router.post("/{session_id}/messages")
def send_message(session_id: str, body: MessageRequest):
    if not body.content.strip():
        raise HTTPException(422, "消息不能为空。")
    return perform(lambda: get_conversation_service().message(session_id, body.content.strip(), body.expected_version))


@router.patch("/{session_id}/plan")
def update_plan(session_id: str, body: PlanUpdate):
    return perform(lambda: get_conversation_service().update_plan(session_id, body.plan, body.expected_version))
