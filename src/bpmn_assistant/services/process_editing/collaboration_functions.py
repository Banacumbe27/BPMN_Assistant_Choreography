"""
Edit functions that operate at the collaboration level (participants and
message flows), as opposed to the element-level functions in functions.py
which operate inside a single participant's process.
"""

from copy import deepcopy

from bpmn_assistant.core.exceptions import (
    ElementAlreadyExistsError,
    ElementNotFoundException,
)


def _participant_ids(model: dict) -> set[str]:
    return {p["id"] for p in model.get("participants", [])}


def add_participant(model: dict, participant: dict) -> dict:
    if "id" not in participant or "name" not in participant:
        raise ValueError("Participant must have 'id' and 'name'")
    if participant["id"] in _participant_ids(model):
        raise ElementAlreadyExistsError(
            f"Participant with id {participant['id']} already exists"
        )

    model_copy = deepcopy(model)
    participant.setdefault("process", [])
    model_copy["participants"].append(participant)
    return {"process": model_copy, "added_participant": participant}


def delete_participant(model: dict, participant_id: str) -> dict:
    target = next(
        (p for p in model.get("participants", []) if p["id"] == participant_id), None
    )
    if target is None:
        raise ElementNotFoundException(
            f"Participant with id {participant_id} does not exist"
        )

    # Collect the pool id plus every element id inside the participant's process,
    # so message flows touching the removed pool are also dropped.
    dead_refs = {participant_id} | _all_element_ids(target.get("process", []))

    model_copy = deepcopy(model)
    model_copy["participants"] = [
        p for p in model_copy["participants"] if p["id"] != participant_id
    ]
    model_copy["message_flows"] = [
        mf
        for mf in model_copy.get("message_flows", [])
        if mf["sourceRef"] not in dead_refs and mf["targetRef"] not in dead_refs
    ]
    return {"process": model_copy, "deleted_participant": participant_id}


def _all_element_ids(process: list) -> set[str]:
    ids: set[str] = set()
    for element in process:
        if "id" in element:
            ids.add(element["id"])
        if "branches" in element:
            for branch in element["branches"]:
                path = branch.get("path", branch) if isinstance(branch, dict) else branch
                ids |= _all_element_ids(path)
    return ids


def add_message_flow(model: dict, message_flow: dict) -> dict:
    for key in ("id", "sourceRef", "targetRef"):
        if key not in message_flow:
            raise ValueError(f"Message flow must have '{key}'")

    existing = {mf["id"] for mf in model.get("message_flows", [])}
    if message_flow["id"] in existing:
        raise ElementAlreadyExistsError(
            f"Message flow with id {message_flow['id']} already exists"
        )

    model_copy = deepcopy(model)
    model_copy.setdefault("message_flows", []).append(message_flow)
    return {"process": model_copy, "added_message_flow": message_flow}


def delete_message_flow(model: dict, message_flow_id: str) -> dict:
    model_copy = deepcopy(model)
    flows = model_copy.get("message_flows", [])
    remaining = [mf for mf in flows if mf["id"] != message_flow_id]
    if len(remaining) == len(flows):
        raise ElementNotFoundException(
            f"Message flow with id {message_flow_id} does not exist"
        )
    model_copy["message_flows"] = remaining
    return {"process": model_copy, "deleted_message_flow": message_flow_id}


COLLABORATION_FUNCTIONS = {
    "add_participant",
    "delete_participant",
    "add_message_flow",
    "delete_message_flow",
}
