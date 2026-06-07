import traceback

from pydantic import BaseModel

from bpmn_assistant.config import logger
from bpmn_assistant.core import LLMFacade, MessageItem, MessageImage
from bpmn_assistant.prompts import PromptTemplateProcessor
from bpmn_assistant.utils import message_history_to_string

DIAGRAM_TYPES = ["process", "collaboration", "choreography"]


def _validate_diagram_type(response: dict) -> None:
    if "diagram_type" not in response:
        raise ValueError("Invalid response: 'diagram_type' key not found")
    if response["diagram_type"] not in DIAGRAM_TYPES:
        raise ValueError(
            f"Invalid response: 'diagram_type' must be one of {DIAGRAM_TYPES}"
        )


class DetermineDiagramTypeResponse(BaseModel):
    diagram_type: str


def determine_diagram_type(
    llm_facade: LLMFacade,
    message_history: list[MessageItem],
    images: list[MessageImage] | None = None,
    max_retries: int = 3,
) -> dict:
    """
    Determine which kind of BPMN diagram best fits the user's description:
    "process" (single pool), "collaboration" (multiple pools + message flows),
    or "choreography" (message-exchange protocol between participants).

    This is an optional pre-step. The create_bpmn prompt also self-selects the
    form, so this classifier is useful mainly to bias or constrain generation
    when the description is ambiguous.
    """
    prompt_processor = PromptTemplateProcessor()

    prompt = prompt_processor.render_template(
        "determine_diagram_type.jinja2",
        message_history=message_history_to_string(message_history),
    )

    attempts = 0
    last_error: Exception | None = None

    while attempts < max_retries:
        attempts += 1
        try:
            json_object = llm_facade.call(
                prompt,
                max_tokens=500,
                temperature=0.3,
                structured_output=DetermineDiagramTypeResponse,
                images=images,
            )
            _validate_diagram_type(json_object)
            logger.info(f"Diagram type: {json_object}")
            return json_object
        except Exception as e:
            last_error = e
            logger.warning(
                f"Validation error (attempt {attempts}): {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            prompt = f"Error: {str(e)}. Try again."

    error_message = (
        "Maximum number of retries reached. Could not determine diagram type."
    )
    if last_error:
        error_message += f" Last error from provider: {last_error}"
    raise Exception(error_message)
