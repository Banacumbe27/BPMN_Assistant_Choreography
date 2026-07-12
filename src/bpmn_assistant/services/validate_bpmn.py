from typing import Union

from pydantic import ValidationError

from bpmn_assistant.core.enums import BPMNElementType
from bpmn_assistant.core.schemas import BPMNEvent, model_type
from bpmn_assistant.services.bpmn_process_transformer import BpmnProcessTransformer

EVENT_TYPES = {
    BPMNElementType.START_EVENT.value,
    BPMNElementType.END_EVENT.value,
    BPMNElementType.INTERMEDIATE_THROW_EVENT.value,
    BPMNElementType.INTERMEDIATE_CATCH_EVENT.value,
}


def validate_model(model: Union[list, dict]) -> None:
    """
    Validate a top-level choreography model.
    Raises:
        ValueError: If the model is invalid.
    """
    model_type(model)  # raises for anything that is not a choreography
    _validate_choreography(model)


def _validate_choreography(model: dict) -> None:
    participants = model.get("participants")
    if not participants or not isinstance(participants, list):
        raise ValueError("Choreography must contain a non-empty 'participants' list")

    for participant in participants:
        if "id" not in participant or "name" not in participant:
            raise ValueError(f"Participant must have 'id' and 'name': {participant}")

    participant_ids = {p["id"] for p in participants}
    if len(participant_ids) < 2:
        raise ValueError("Choreography must contain at least two participants")

    choreography = model.get("choreography")
    if not choreography or not isinstance(choreography, list):
        raise ValueError("Choreography must contain a non-empty 'choreography' list")

    # Choreography tasks reference participants that must exist
    for element in _iter_elements(choreography):
        if element.get("type") == BPMNElementType.CHOREOGRAPHY_TASK.value:
            for ref in (element.get("initiator"), element.get("recipient")):
                if ref is not None and ref not in participant_ids:
                    raise ValueError(
                        f"Choreography task '{element.get('id')}' references unknown "
                        f"participant id: {ref}"
                    )

    validate_bpmn(choreography)


def _iter_elements(process: list) -> list[dict]:
    """Recursively yield every element in a (possibly branched) element list."""
    result: list[dict] = []
    for element in process:
        result.append(element)
        if "branches" in element:
            for branch in element["branches"]:
                path = branch.get("path", branch) if isinstance(branch, dict) else branch
                result.extend(_iter_elements(path))
    return result


def validate_bpmn(process: list, is_top_level: bool = True) -> None:
    """
    Validate a choreography element list.
    Args:
        process: The list of choreography elements in JSON format.
        is_top_level: Whether this is the top-level list (not a branch).
    Raises:
        ValueError: If the list, or any of its elements, is invalid.
    """
    seen_ids = set()
    start_event_count = 0

    for element in process:
        validate_element(element)

        if element["id"] in seen_ids:
            raise ValueError(f"Duplicate element ID found: {element['id']}")
        seen_ids.add(element["id"])

        # Count start events at the top level
        if is_top_level and element["type"] == BPMNElementType.START_EVENT.value:
            start_event_count += 1

        if element["type"] in (
            BPMNElementType.EXCLUSIVE_GATEWAY.value,
            BPMNElementType.INCLUSIVE_GATEWAY.value,
        ):
            for branch in element["branches"]:
                validate_bpmn(branch["path"], is_top_level=False)
        if element["type"] == BPMNElementType.PARALLEL_GATEWAY.value:
            for branch in element["branches"]:
                validate_bpmn(branch, is_top_level=False)

    # Check for exactly one start event at the top level
    if is_top_level and start_event_count != 1:
        raise ValueError(f"Choreography must contain exactly one start event, found {start_event_count}")
    if is_top_level and not _process_has_end_event(process):
        raise ValueError("Choreography must contain at least one end event")
    if is_top_level:
        # Ensure the choreography can be transformed into BPMN XML
        transformer = BpmnProcessTransformer()
        transformer.transform(process)


def validate_element(element: dict) -> None:
    """
    Validate a single choreography element.
    Raises:
        ValueError: If the element is invalid.
    """
    if "id" not in element:
        raise ValueError(f"Element is missing an ID: {element}")
    elif "type" not in element:
        raise ValueError(f"Element is missing a type: {element}")

    supported_elements = [e.value for e in BPMNElementType]

    if element["type"] not in supported_elements:
        raise ValueError(
            f"Unsupported element type: {element['type']}. Supported types: {supported_elements}"
        )

    if element["type"] == BPMNElementType.CHOREOGRAPHY_TASK.value:
        _validate_choreography_task(element)

    elif element["type"] in EVENT_TYPES:
        _validate_event(element)

    elif element["type"] == BPMNElementType.EXCLUSIVE_GATEWAY.value:
        _validate_exclusive_gateway(element)

    elif element["type"] == BPMNElementType.INCLUSIVE_GATEWAY.value:
        _validate_inclusive_gateway(element)

    elif element["type"] == BPMNElementType.PARALLEL_GATEWAY.value:
        _validate_parallel_gateway(element)


def _validate_choreography_task(element: dict) -> None:
    for key in ("name", "initiator", "recipient"):
        if key not in element:
            raise ValueError(f"Choreography task is missing '{key}': {element}")
    if element["initiator"] == element["recipient"]:
        raise ValueError(
            f"Choreography task initiator and recipient must differ: {element}"
        )


def _validate_event(element: dict) -> None:
    try:
        BPMNEvent.model_validate(element)
    except ValidationError:
        raise ValueError(f"Invalid event element: {element}")


def _validate_exclusive_gateway(element: dict) -> None:
    if "label" not in element:
        raise ValueError(f"Exclusive gateway is missing a label: {element}")
    if "branches" not in element or not isinstance(element["branches"], list):
        raise ValueError(
            f"Exclusive gateway is missing or has invalid 'branches': {element}"
        )
    branch_paths = []
    for branch in element["branches"]:
        if "condition" not in branch or "path" not in branch:
            raise ValueError(f"Invalid branch in exclusive gateway: {branch}")
        if not isinstance(branch["path"], list):
            raise ValueError(f"Exclusive gateway branch 'path' must be a list: {branch}")
        branch_paths.append(branch["path"])

    if branch_paths and all(len(path) == 0 for path in branch_paths):
        raise ValueError(
            "Exclusive gateway must have at least one branch with elements; all branch paths are empty."
        )


def _validate_inclusive_gateway(element: dict) -> None:
    if "label" not in element:
        raise ValueError(f"Inclusive gateway is missing a label: {element}")
    if "branches" not in element or not isinstance(element["branches"], list):
        raise ValueError(
            f"Inclusive gateway is missing or has invalid 'branches': {element}"
        )
    for branch in element["branches"]:
        # Default branches don't require a condition, but all branches need a path
        if "path" not in branch:
            raise ValueError(f"Invalid branch in inclusive gateway (missing 'path'): {branch}")
        # Non-default branches must have a condition
        if not branch.get("is_default", False) and "condition" not in branch:
            raise ValueError(f"Invalid branch in inclusive gateway (non-default branch missing 'condition'): {branch}")


def _validate_parallel_gateway(element: dict) -> None:
    if "branches" not in element or not isinstance(element["branches"], list):
        raise ValueError(
            f"Parallel gateway has missing or invalid 'branches': {element}"
        )


def _process_has_end_event(process: list[dict]) -> bool:
    """Recursively check whether the choreography (including branches) contains at least one end event."""
    for element in process:
        if element["type"] == BPMNElementType.END_EVENT.value:
            return True
        if element["type"] in [
            BPMNElementType.EXCLUSIVE_GATEWAY.value,
            BPMNElementType.INCLUSIVE_GATEWAY.value
        ]:
            for branch in element["branches"]:
                if _process_has_end_event(branch["path"]):
                    return True
        if element["type"] == BPMNElementType.PARALLEL_GATEWAY.value:
            for branch in element["branches"]:
                if _process_has_end_event(branch):
                    return True
    return False
