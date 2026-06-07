from typing import Any

from pydantic import BaseModel, model_validator

from bpmn_assistant.core import MessageItem


class AvailableProvidersRequest(BaseModel):
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class BpmnToJsonRequest(BaseModel):
    bpmn_xml: str  # The BPMN XML to be converted to JSON
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class DetermineIntentRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    model: str  # The model to be used
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class ModifyBpmnRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    process: list[dict[str, Any]] | None  # The process to be updated (if it exists)
    model: str  # The model to be used
    api_keys: dict[str, str] | None = None  # Optional API keys from user


class ConversationalRequest(BaseModel):
    message_history: list[MessageItem]  # The message history
    process: list[dict[str, Any]] | None  # The current process (if it exists)
    model: str  # The model to be used
    needs_to_be_final_comment: bool  # Whether the response needs to be a comment after the process is created/edited
    api_keys: dict[str, str] | None = None  # Optional API keys from user

    @model_validator(mode="before")
    @classmethod
    def ensure_bpmn_json_presence(cls, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("needs_to_be_final_comment") and not data.get("process"):
            raise ValueError(
                "Process must be present when needs_to_be_final_comment is True"
            )
        return data
