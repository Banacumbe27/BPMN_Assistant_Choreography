from typing import Any

from pydantic import BaseModel, model_validator

from bpmn_assistant.core import MessageItem


class AvailableProvidersRequest(BaseModel):
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class DetermineIntentRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    model: str  # The model to be used
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class ModifyBpmnRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    # The choreography dict to be updated (if it exists).
    process: dict[str, Any] | None
    model: str  # The model to be used
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class ConversationalRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    # The current choreography dict (if it exists).
    process: dict[str, Any] | None
    model: str  # The model to be used
    needs_to_be_final_comment: bool  # Whether the response needs to be a comment after the choreography is created/edited
    api_keys: dict[str, str] | None = None  # Optional API keys from user

    @model_validator(mode="before")
    @classmethod
    def ensure_bpmn_json_presence(cls, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("needs_to_be_final_comment") and not data.get("process"):
            raise ValueError(
                "Process must be present when needs_to_be_final_comment is True"
            )
        return data
