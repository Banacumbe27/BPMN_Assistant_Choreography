from xml.etree import ElementTree as ET

import pytest

from bpmn_assistant.services import BpmnLayoutGenerator, BpmnXmlGenerator
from bpmn_assistant.services.validate_bpmn import validate_model


def _di_shapes_edges(model):
    xml = BpmnXmlGenerator().create_bpmn_xml(model)
    full = BpmnLayoutGenerator().add_di(model, xml)
    root = ET.fromstring(full)  # must stay well-formed
    plane = root.find("{*}BPMNDiagram").find("{*}BPMNPlane")
    return root, plane.findall("{*}BPMNShape"), plane.findall("{*}BPMNEdge")


def _bounds(shape):
    b = shape.find("{*}Bounds")
    return (
        float(b.get("x")),
        float(b.get("y")),
        float(b.get("width")),
        float(b.get("height")),
    )


class TestChoreographyValidation:
    def test_valid_choreography(self, buyer_seller_choreography):
        validate_model(buyer_seller_choreography)

    def test_valid_deontic_choreography(self, jade_hotel_choreography):
        validate_model(jade_hotel_choreography)

    def test_rejects_process_list(self, empty_gateway_path_process):
        with pytest.raises(ValueError):
            validate_model(empty_gateway_path_process)

    def test_rejects_collaboration_dict(self):
        with pytest.raises(ValueError):
            validate_model({"participants": [{"id": "a", "name": "A"}], "message_flows": []})

    def test_rejects_orchestration_task_types(self, buyer_seller_choreography):
        buyer_seller_choreography["choreography"].insert(
            1, {"type": "userTask", "id": "t_bad", "label": "Do work"}
        )
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)

    def test_bad_participant_ref(self, buyer_seller_choreography):
        buyer_seller_choreography["choreography"][1]["recipient"] = "ghost"
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)

    def test_same_initiator_and_recipient_rejected(self, buyer_seller_choreography):
        buyer_seller_choreography["choreography"][1]["recipient"] = "buyer"
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)

    def test_requires_two_participants(self, buyer_seller_choreography):
        buyer_seller_choreography["participants"] = [{"id": "buyer", "name": "Buyer"}]
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)

    def test_invalid_event_definition_rejected(self, buyer_seller_choreography):
        buyer_seller_choreography["choreography"][0]["eventDefinition"] = "bogusEventDefinition"
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)

    def test_branched_choreography_validates(self):
        """A choreographyTask inside a gateway branch must validate (regression)."""
        model = {
            "participants": [
                {"id": "client", "name": "Client"},
                {"id": "contractor", "name": "Contractor"},
            ],
            "choreography": [
                {"type": "startEvent", "id": "st"},
                {
                    "type": "choreographyTask",
                    "id": "t1",
                    "name": "Request quote",
                    "initiator": "client",
                    "recipient": "contractor",
                    "message": "Request",
                },
                {
                    "type": "exclusiveGateway",
                    "id": "g",
                    "label": "Accepted?",
                    "has_join": False,
                    "branches": [
                        {
                            "condition": "Accepted",
                            "path": [
                                {
                                    "type": "choreographyTask",
                                    "id": "t2",
                                    "name": "Accept",
                                    "initiator": "client",
                                    "recipient": "contractor",
                                },
                                {"type": "endEvent", "id": "e1"},
                            ],
                        },
                        {"condition": "Declined", "path": [{"type": "endEvent", "id": "e2"}]},
                    ],
                },
            ],
        }
        validate_model(model)  # must not raise
        # and it must produce well-formed XML + DI
        _, shapes, _ = _di_shapes_edges(model)
        assert {"t1", "t2"}.issubset({s.get("bpmnElement") for s in shapes})


class TestRequestSchemaAcceptsDict:
    """The HTTP request models must accept choreography dicts."""

    def test_modify_request_accepts_dict_and_none(self, buyer_seller_choreography):
        from bpmn_assistant.api.requests import ModifyBpmnRequest

        ModifyBpmnRequest(
            message_history=[], process=buyer_seller_choreography, model="gpt-4.1"
        )
        ModifyBpmnRequest(message_history=[], process=None, model="gpt-4.1")

    def test_talk_request_accepts_dict(self, buyer_seller_choreography):
        from bpmn_assistant.api.requests import ConversationalRequest

        ConversationalRequest(
            message_history=[{"role": "user", "content": "x"}],
            process=buyer_seller_choreography,
            model="gpt-4.1",
            needs_to_be_final_comment=True,
        )


class TestLayoutDi:
    def _assert_bounds_valid(self, shapes):
        for s in shapes:
            b = s.find("{*}Bounds")
            assert b is not None
            assert float(b.get("width")) > 0
            assert float(b.get("height")) > 0
            float(b.get("x"))
            float(b.get("y"))

    def test_choreography_di(self, buyer_seller_choreography):
        _, shapes, edges = _di_shapes_edges(buyer_seller_choreography)
        self._assert_bounds_valid(shapes)
        # choreography tasks get the tall (band) height
        task = next(
            s
            for s in shapes
            if s.get("bpmnElement") == "ct_order" and not s.get("participantBandKind")
        )
        assert float(task.find("{*}Bounds").get("height")) == 150

    def test_choreography_band_di(self, buyer_seller_choreography):
        """chor-js needs 2 participant-band shapes per task (regression)."""
        _, shapes, _ = _di_shapes_edges(buyer_seller_choreography)
        bands = [s for s in shapes if s.get("participantBandKind")]
        # 2 tasks x 2 bands
        assert len(bands) == 4
        for b in bands:
            assert b.get("choreographyActivityShape", "").endswith("_di")
            assert b.get("isMessageVisible") == "false"
            assert float(b.find("{*}Bounds").get("height")) == 20
        # ct_order: buyer initiates -> top, seller -> bottom
        order_bands = {
            b.get("participantBandKind"): b.get("bpmnElement")
            for b in bands
            if b.get("choreographyActivityShape") == "ct_order_di"
        }
        assert order_bands == {"top_initiating": "buyer", "bottom_non_initiating": "seller"}

    def test_deontic_chain_layout(self, jade_hotel_choreography):
        """Terminate ends hang directly below their gateway; the compensation
        chain continues to the right on the top row."""
        _, shapes, edges = _di_shapes_edges(jade_hotel_choreography)
        self._assert_bounds_valid(shapes)
        boxes = {
            s.get("bpmnElement"): _bounds(s)
            for s in shapes
            if not s.get("participantBandKind")
        }

        for gw, end in [
            ("gw_alt_room", "end_fulfilled_room"),
            ("gw_spa_access", "end_fulfilled_spa"),
            ("gw_discount", "end_fulfilled_discount"),
        ]:
            gx, gy, gw_w, gh = boxes[gw]
            ex, ey, ew, eh = boxes[end]
            # same column, centered under the gateway
            assert abs((gx + gw_w / 2) - (ex + ew / 2)) < 1
            # below the gateway
            assert ey > gy + gh

        # main chain stays on one row, marching right
        chain = ["provide_alt_room", "gw_alt_room", "provide_spa_access",
                 "gw_spa_access", "provide_discount", "gw_discount"]
        xs = [boxes[e][0] for e in chain]
        assert xs == sorted(xs)
        # the unfulfilled end continues to the right of the last gateway
        assert boxes["end_unfulfilled"][0] > boxes["gw_discount"][0]

        # the vertical yes-drop edges are straight (two waypoints, same x)
        edge_map = {e.get("bpmnElement"): e for e in edges}
        drop = edge_map["gw_alt_room-end_fulfilled_room"]
        wps = drop.findall("{*}waypoint")
        assert len(wps) == 2
        assert wps[0].get("x") == wps[1].get("x")


class TestChoreographyMessageFlows:
    def test_message_flows_declared_and_resolve(self, buyer_seller_choreography):
        xml = BpmnXmlGenerator().create_bpmn_xml(buyer_seller_choreography)
        root = ET.fromstring(xml)
        choreo = root.find("{*}choreography")

        message_flows = {mf.get("id"): mf for mf in choreo.findall("{*}messageFlow")}
        assert message_flows  # not empty

        # every messageFlowRef on a task resolves to a declared <messageFlow>
        refs = [
            r.text
            for t in choreo.findall("{*}choreographyTask")
            for r in t.findall("{*}messageFlowRef")
        ]
        assert refs
        assert all(r in message_flows for r in refs)

        # messageFlow source/target are participant ids; messageRef resolves to a <message>
        messages = {m.get("id") for m in root.findall("{*}message")}
        participant_ids = {p["id"] for p in buyer_seller_choreography["participants"]}
        for mf in message_flows.values():
            assert mf.get("sourceRef") in participant_ids
            assert mf.get("targetRef") in participant_ids
            assert mf.get("messageRef") in messages


class _FakeFacade:
    """Minimal stand-in for LLMFacade that records the prompt and returns a fixed model."""

    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def call(self, prompt, max_tokens=3000, images=None):
        self.last_prompt = prompt
        return self.response


class TestChoreographyPrompt:
    def test_create_uses_choreography_prompt(self, buyer_seller_choreography):
        from bpmn_assistant.services.bpmn_modeling_service import BpmnModelingService

        facade = _FakeFacade(buyer_seller_choreography)
        model = BpmnModelingService().create_bpmn(facade, [])

        assert "choreography" in model  # valid dict returned
        assert "Create a BPMN **choreography**" in facade.last_prompt
        # deontic mapping guidance is part of the creation prompt
        assert "deontic" in facade.last_prompt.lower()
        assert "terminateEventDefinition" in facade.last_prompt
        assert "conditionalEventDefinition" in facade.last_prompt

    def test_update_includes_current_model(self, buyer_seller_choreography):
        from bpmn_assistant.services.bpmn_modeling_service import BpmnModelingService

        facade = _FakeFacade(buyer_seller_choreography)
        BpmnModelingService().create_bpmn(
            facade, [], current_model=buyer_seller_choreography
        )

        assert "complete updated" in facade.last_prompt
        assert "ct_order" in facade.last_prompt  # current model embedded
