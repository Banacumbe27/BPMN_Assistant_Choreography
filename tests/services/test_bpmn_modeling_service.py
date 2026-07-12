from unittest.mock import Mock

import pytest

from bpmn_assistant.core import LLMFacade
from bpmn_assistant.services import BpmnModelingService


class TestCreateBpmn:

    def test_create_bpmn_raises_exception_for_missing_id(self):
        bpmn_service = BpmnModelingService()
        mock_llm_facade = Mock(LLMFacade)

        invalid_choreography = {
            "participants": [
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B"},
            ],
            "choreography": [
                {"type": "startEvent"},  # missing id
                {
                    "type": "choreographyTask",
                    "id": "t1",
                    "name": "Interact",
                    "initiator": "a",
                    "recipient": "b",
                },
                {"id": "end1", "type": "endEvent"},
            ],
        }

        mock_llm_facade.call.return_value = invalid_choreography

        with pytest.raises(ValueError) as e:
            bpmn_service.create_bpmn(mock_llm_facade, [])

        assert "Max number of retries reached" in str(e.value)
        assert mock_llm_facade.call.call_count == 3

    def test_create_bpmn_rejects_orchestration_response(self):
        """A legacy single-process response must be rejected, not unwrapped."""
        bpmn_service = BpmnModelingService()
        mock_llm_facade = Mock(LLMFacade)

        mock_llm_facade.call.return_value = {
            "process": [
                {"type": "startEvent", "id": "start"},
                {"type": "task", "id": "t1", "label": "Do"},
                {"type": "endEvent", "id": "end"},
            ]
        }

        with pytest.raises(ValueError):
            bpmn_service.create_bpmn(mock_llm_facade, [])
