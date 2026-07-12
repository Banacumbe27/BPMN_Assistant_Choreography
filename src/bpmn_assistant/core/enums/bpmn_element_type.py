from enum import Enum


class BPMNElementType(Enum):
    """Element types supported in a BPMN choreography."""

    CHOREOGRAPHY_TASK = "choreographyTask"
    EXCLUSIVE_GATEWAY = "exclusiveGateway"
    INCLUSIVE_GATEWAY = "inclusiveGateway"
    PARALLEL_GATEWAY = "parallelGateway"
    START_EVENT = "startEvent"
    END_EVENT = "endEvent"
    INTERMEDIATE_THROW_EVENT = "intermediateThrowEvent"
    INTERMEDIATE_CATCH_EVENT = "intermediateCatchEvent"


class EventDefinitionType(Enum):
    """Event definition types for BPMN events"""
    TIMER = "timerEventDefinition"
    MESSAGE = "messageEventDefinition"
    CONDITIONAL = "conditionalEventDefinition"
    TERMINATE = "terminateEventDefinition"
    NONE = None  # For events without definitions
