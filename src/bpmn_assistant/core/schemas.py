from typing import List, Optional, Dict, Any

from pydantic import BaseModel
from typing_extensions import Literal


class MessageImage(BaseModel):
    """
    Represents an image attached to a message.
    """

    preview: str  # Base64 encoded image data URL
    name: str  # Original filename


class MessageItem(BaseModel):
    """
    A message item used for LLM API communication.
    Supports text content and optional images for vision-enabled models.
    """

    role: str
    content: str
    images: Optional[List[MessageImage]] = None


EventType = Literal["startEvent", "endEvent", "intermediateThrowEvent", "intermediateCatchEvent"]
EventDefinitionType = Literal[
    "timerEventDefinition",
    "messageEventDefinition",
    "conditionalEventDefinition",
    "terminateEventDefinition",
]


class BPMNEvent(BaseModel):
    """
    Represents a BPMN event.
    'type' must be one of: 'startEvent', 'endEvent', 'intermediateThrowEvent', 'intermediateCatchEvent'.
    'eventDefinition' is optional and specifies the event type (timer, message, conditional, terminate).
    """

    type: EventType
    id: str
    label: Optional[str] = None
    eventDefinition: Optional[EventDefinitionType] = None


# --- Choreography ---


class ChoreographyTask(BaseModel):
    """
    A BPMN choreography task: an interaction between two participants. The
    'initiator' band is drawn on top, the 'recipient' band on the bottom.
    'message' is the (optional) message the initiator sends; 'return_message'
    makes the task two-way.
    """

    type: Literal["choreographyTask"]
    id: str
    name: str
    initiator: str  # participant id
    recipient: str  # participant id
    message: Optional[str] = None
    return_message: Optional[str] = None


class ChoreographyParticipant(BaseModel):
    """A participant in a choreography (name only - no internal process)."""

    id: str
    name: str


class ChoreographyModel(BaseModel):
    """
    A BPMN choreography. Nodes are choreography tasks connected by sequence
    flows, optionally branched with events/gateways. Elements are kept loosely
    typed here (dicts) and validated by validate_bpmn() so the same
    transformer/traversal code path is reused.
    """

    participants: List[ChoreographyParticipant]
    choreography: List[Dict[str, Any]]


def model_type(model: Any) -> str:
    """
    Detect the top-level diagram type. This application only supports
    choreographies; anything else raises.
    """
    if isinstance(model, dict) and "choreography" in model:
        return "choreography"
    raise ValueError(
        f"Only choreography models are supported. Unable to interpret: {model}"
    )
