from abc import ABC, abstractmethod
from typing import Any, Generator

from pydantic import BaseModel


class LLMProvider(ABC):
    @abstractmethod
    def call(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        structured_output: type[BaseModel] | None = None,
    ) -> str | dict[str, Any]:
        pass

    @abstractmethod
    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def get_initial_messages(self) -> list[dict[str, str]]:
        pass

    @abstractmethod
    def check_model_compatibility(self, model: str) -> bool:
        pass
