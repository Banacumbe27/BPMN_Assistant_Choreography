import os

import pytest
from dotenv import load_dotenv

from bpmn_assistant.core import LLMFacade, MessageItem
from bpmn_assistant.core.enums import AnthropicModels, OpenAIModels, Provider


@pytest.fixture
def anthropic_facade():
    load_dotenv(override=True)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    return LLMFacade(Provider.ANTHROPIC, api_key, AnthropicModels.SONNET_4_5.value)


@pytest.fixture
def openai_facade():
    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    return LLMFacade(Provider.OPENAI, api_key, OpenAIModels.GPT_4_1.value)


@pytest.fixture
def empty_gateway_path_process():
    """
    Description: An element list that contains an exclusive gateway with an empty path.
    (Transformer-level fixture; element types are irrelevant to the transformer.)
    """
    return [
        {"type": "startEvent", "id": "start"},
        {"type": "task", "id": "task1", "label": "Perform a simple task"},
        {"type": "task", "id": "task2", "label": "Perform a second task"},
        {
            "type": "exclusiveGateway",
            "id": "exclusive1",
            "label": "Decision Point",
            "has_join": False,
            "branches": [
                {
                    "condition": "Condition A",
                    "path": [
                        {
                            "type": "task",
                            "id": "task3",
                            "label": "Perform a third task",
                        }
                    ],
                },
                {"condition": "Condition B", "path": []},
            ],
        },
        {"type": "endEvent", "id": "end"},
    ]


@pytest.fixture
def eg_end_event_in_path_process():
    """
    Description: An element list that contains an exclusive gateway with an end
    event in one of the paths. (Transformer-level fixture.)
    """
    return [
        {"type": "startEvent", "id": "start"},
        {
            "type": "exclusiveGateway",
            "id": "exclusive1",
            "label": "Decision Point",
            "has_join": False,
            "branches": [
                {
                    "condition": "Condition A",
                    "path": [
                        {
                            "type": "task",
                            "id": "task1",
                            "label": "Perform the first task",
                        }
                    ],
                },
                {
                    "condition": "Condition B",
                    "path": [
                        {
                            "type": "endEvent",
                            "id": "end1",
                        }
                    ],
                },
            ],
        },
        {"type": "task", "id": "task2", "label": "Perform the second task"},
        {"type": "endEvent", "id": "end2"},
    ]


@pytest.fixture
def buyer_seller_choreography():
    """
    Description: A simple two-participant choreography (Buyer <-> Seller).
    """
    return {
        "participants": [
            {"id": "buyer", "name": "Buyer"},
            {"id": "seller", "name": "Seller"},
        ],
        "choreography": [
            {"type": "startEvent", "id": "ch_start"},
            {
                "type": "choreographyTask",
                "id": "ct_order",
                "initiator": "buyer",
                "recipient": "seller",
                "name": "Submit order",
                "message": "Order",
            },
            {
                "type": "choreographyTask",
                "id": "ct_confirm",
                "initiator": "seller",
                "recipient": "buyer",
                "name": "Confirm order",
                "message": "Confirmation",
            },
            {"type": "endEvent", "id": "ch_end"},
        ],
    }


@pytest.fixture
def jade_hotel_choreography():
    """
    Description: The deontic Jade Hotel compensation-chain choreography:
    conditional start, three chained compensations, terminate ends on the
    fulfilled branches, and a plain unfulfilled end.
    """
    return {
        "participants": [
            {"id": "jade_hotel", "name": "Jade Hotel"},
            {"id": "customer", "name": "Customer"},
        ],
        "choreography": [
            {
                "type": "startEvent",
                "id": "start_no_seaview",
                "label": "Hotel has no seaview room for customer booking the deluxe room",
                "eventDefinition": "conditionalEventDefinition",
            },
            {
                "type": "choreographyTask",
                "id": "provide_alt_room",
                "name": "Provide Alternative room",
                "initiator": "jade_hotel",
                "recipient": "customer",
                "message": "Alternative room offer",
            },
            {
                "type": "exclusiveGateway",
                "id": "gw_alt_room",
                "label": "Does alternative room available?",
                "has_join": False,
                "branches": [
                    {
                        "condition": "yes",
                        "path": [
                            {
                                "type": "endEvent",
                                "id": "end_fulfilled_room",
                                "label": "Contract fulfilled",
                                "eventDefinition": "terminateEventDefinition",
                            }
                        ],
                    },
                    {"condition": "no", "path": []},
                ],
            },
            {
                "type": "choreographyTask",
                "id": "provide_spa_access",
                "name": "Provide free spa access",
                "initiator": "jade_hotel",
                "recipient": "customer",
                "message": "Free spa access offer",
            },
            {
                "type": "exclusiveGateway",
                "id": "gw_spa_access",
                "label": "Does free spa access available?",
                "has_join": False,
                "branches": [
                    {
                        "condition": "yes",
                        "path": [
                            {
                                "type": "endEvent",
                                "id": "end_fulfilled_spa",
                                "label": "Contract fulfilled",
                                "eventDefinition": "terminateEventDefinition",
                            }
                        ],
                    },
                    {"condition": "no", "path": []},
                ],
            },
            {
                "type": "choreographyTask",
                "id": "provide_discount",
                "name": "Provide 50% discount on checkout",
                "initiator": "jade_hotel",
                "recipient": "customer",
                "message": "50% discount offer",
            },
            {
                "type": "exclusiveGateway",
                "id": "gw_discount",
                "label": "Does the discount available?",
                "has_join": False,
                "branches": [
                    {
                        "condition": "yes",
                        "path": [
                            {
                                "type": "endEvent",
                                "id": "end_fulfilled_discount",
                                "label": "Contract fulfilled",
                                "eventDefinition": "terminateEventDefinition",
                            }
                        ],
                    },
                    {
                        "condition": "no",
                        "path": [
                            {
                                "type": "endEvent",
                                "id": "end_unfulfilled",
                                "label": "Contract unfulfilled, customer is uncompensated",
                            }
                        ],
                    },
                ],
            },
        ],
    }


def dict_to_message_item(message_dict):
    return MessageItem(**message_dict)


def convert_message_history(message_history):
    return [dict_to_message_item(message) for message in message_history]


@pytest.fixture
def message_history_create_bpmn():
    """
    Description: A message history that contains a conversation between a user and an assistant.
    The user is asking the assistant to help them create a BPMN process.
    """
    message_history = [
        {"role": "user", "content": "Can you help me create a BPMN process?"},
        {
            "role": "assistant",
            "content": "Sure! What are the steps involved in the process?",
        },
        {
            "role": "user",
            "content": "Create a process that involves a user signing up for a service. 1. The user visits the website and clicks on the 'Sign Up' button. 2. The user enters their email address and password. 3. The user clicks on the 'Sign Up' button. 4. The user receives a confirmation email. 5. The user clicks on the confirmation link in the email. 6. The user is redirected to the website and sees a confirmation message.",
        },
    ]

    return convert_message_history(message_history)
