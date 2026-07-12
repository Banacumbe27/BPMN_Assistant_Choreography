import json
import traceback

from bpmn_assistant.config import logger
from bpmn_assistant.core import LLMFacade, MessageItem, MessageImage
from bpmn_assistant.prompts import PromptTemplateProcessor
from bpmn_assistant.utils import message_history_to_string

from .validate_bpmn import validate_model


class BpmnModelingService:
    """
    Service for creating and updating BPMN choreographies.
    """

    def __init__(self):
        self.prompt_processor = PromptTemplateProcessor()

    def create_bpmn(
        self,
        llm_facade: LLMFacade,
        message_history: list[MessageItem],
        images: list[MessageImage] | None = None,
        max_retries: int = 3,
        current_model: dict | None = None,
    ) -> dict:
        """
        Create a BPMN choreography from the description. If a current model is
        supplied, the LLM is asked to apply the requested changes to it and
        return the complete updated choreography.
        Args:
            llm_facade: The LLMFacade object.
            message_history: The message history.
            images: Optional list of images to attach to the request.
            max_retries: The maximum number of retries in case of failure.
            current_model: Optional existing choreography dict to update.
        Returns:
            The BPMN choreography dict {participants, choreography}.
        """
        prompt = self.prompt_processor.render_template(
            "create_choreography.jinja2",
            message_history=message_history_to_string(message_history),
            current_model=(
                json.dumps(current_model, indent=2) if current_model else None
            ),
        )

        attempts = 0
        last_error: Exception | None = None

        while attempts < max_retries:
            attempts += 1
            try:
                response = llm_facade.call(prompt, max_tokens=3000, images=images)
                logger.debug(f"LLM response:\n{json.dumps(response, indent=2)}")
                validate_model(response)
                logger.debug(
                    f"Generated BPMN choreography:\n{json.dumps(response, indent=2)}"
                )
                return response  # Return the model if it's valid
            except (ValueError, Exception) as e:
                last_error = e
                logger.warning(
                    f"Error (attempt {attempts}): {str(e)}\n"
                    f"Traceback: {traceback.format_exc()}"
                )
                prompt = f"Error: {str(e)}. Try again."

        message = "Max number of retries reached. Could not create the BPMN choreography."
        if last_error:
            message += f" Last error from provider: {last_error}"
        raise ValueError(message)
