from typing import List, Optional, Union, Dict, Any

from pydantic import BaseModel, RootModel
from typing_extensions import Literal

TaskType = Literal["task", "userTask", "serviceTask", "sendTask", "receiveTask", "businessRuleTask", "manualTask", "scriptTask"]


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


class BPMNTask(BaseModel):
    """
    Represents a BPMN task.
    'type' must be one of: 'task', 'userTask', 'serviceTask', 'sendTask', 'receiveTask', 'businessRuleTask', 'manualTask', or 'scriptTask'.
    """

    type: TaskType
    id: str
    label: str


EventType = Literal["startEvent", "endEvent", "intermediateThrowEvent", "intermediateCatchEvent"]
EventDefinitionType = Literal["timerEventDefinition", "messageEventDefinition"]


class BPMNEvent(BaseModel):
    """
    Represents a BPMN event.
    'type' must be one of: 'startEvent', 'endEvent', 'intermediateThrowEvent', 'intermediateCatchEvent'.
    'eventDefinition' is optional and specifies the event type (timer, message, etc.)
    """

    type: EventType
    id: str
    label: Optional[str] = None
    eventDefinition: Optional[EventDefinitionType] = None


class ExclusiveGatewayBranch(BaseModel):
    """
    Represents a branch of an exclusive gateway.
    - 'condition': textual condition for the branch
    - 'path': array of BPMN elements executed if the condition is met
    - 'next': optional ID of the next element (if not following default sequence)
    """

    condition: str
    path: List["BPMNElement"] = []
    next: Optional[str] = None


class ExclusiveGateway(BaseModel):
    """
    Represents a BPMN exclusive gateway.
    - 'has_join': indicates whether this gateway also merges paths
    - 'branches': list of exclusive branches
    """

    type: Literal["exclusiveGateway"]
    id: str
    label: str
    has_join: bool
    branches: List[ExclusiveGatewayBranch]


class InclusiveGatewayBranch(BaseModel):
    """
    Represents a branch of an inclusive gateway.
    - 'condition': textual condition for the branch (not required for default branches)
    - 'path': array of BPMN elements executed if the condition is met
    - 'next': optional ID of the next element (if not following default sequence)
    - 'is_default': marks this branch as the default (taken when no conditions are met)
    """

    condition: Optional[str] = None
    path: List["BPMNElement"] = []
    next: Optional[str] = None
    is_default: bool = False


class InclusiveGateway(BaseModel):
    """
    Represents a BPMN inclusive gateway (OR-gateway).
    Multiple branches can be taken simultaneously based on their conditions.
    - 'has_join': indicates whether this gateway also merges paths
    - 'branches': list of inclusive branches (can have multiple conditions fulfilled)
    """

    type: Literal["inclusiveGateway"]
    id: str
    label: str
    has_join: bool
    branches: List[InclusiveGatewayBranch]


class ParallelGateway(BaseModel):
    """
    Represents a BPMN parallel gateway.
    - 'branches': an array of arrays, each of which holds a list of BPMN elements
      to be executed in parallel.
    """

    type: Literal["parallelGateway"]
    id: str
    branches: List[List["BPMNElement"]]


BPMNElement = Union[BPMNTask, BPMNEvent, ExclusiveGateway, InclusiveGateway, ParallelGateway]


class ProcessModel(BaseModel):
    """
    Represents a BPMN process containing a list of elements
    that can be tasks, events, or gateways.
    """

    process: List[BPMNElement]


# --- Collaboration (pools / message flows) ---


class MessageFlow(BaseModel):
    """
    A message flow connecting two elements that live in different participants
    (pools). Unlike sequence flows, message flows cross pool boundaries, so they
    are declared at the collaboration level rather than inside a process.
    """

    id: str
    sourceRef: str  # id of an element in some participant's process
    targetRef: str  # id of an element in another participant's process
    label: Optional[str] = None


class Participant(BaseModel):
    """
    A participant (pool) in a collaboration. 'process' reuses the exact same
    nested grammar as a standalone process. An empty 'process' represents a
    black-box pool (no internal detail).
    """

    id: str
    name: str
    process: List[BPMNElement] = []


class CollaborationModel(BaseModel):
    """
    A BPMN collaboration: multiple participants (pools), each owning a process,
    plus message flows between them. The single-process case is the degenerate
    form with one participant and no message flows.
    """

    participants: List[Participant]
    message_flows: List[MessageFlow] = []


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
    typed here (dicts) and validated by validate_bpmn(mode="choreography") so
    the same transformer/traversal code path is reused.
    """

    participants: List[ChoreographyParticipant]
    choreography: List[Dict[str, Any]]


def model_type(model: Any) -> str:
    """
    Detect which top-level diagram a model represents, by key presence.
    Returns one of: "process", "collaboration", "choreography".

    - A bare list (legacy) or a dict with only "process" -> "process".
    - A dict containing "choreography" -> "choreography".
    - A dict containing "participants" -> "collaboration".
    """
    if isinstance(model, list):
        return "process"
    if isinstance(model, dict):
        if "choreography" in model:
            return "choreography"
        if "participants" in model:
            return "collaboration"
        if "process" in model:
            return "process"
    raise ValueError(f"Unable to determine model type for: {model}")


class EditProposal(BaseModel):
    """
    Represents an edit proposal for a BPMN process.
    """

    function: str
    arguments: Dict[str, Any]


class StopSignal(BaseModel):
    """
    Represents a stop signal for the BPMN editing process.
    """

    stop: Literal[True]

IntermediateEditProposal = RootModel[Union[EditProposal, StopSignal]]