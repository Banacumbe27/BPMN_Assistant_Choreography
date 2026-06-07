from xml.etree import ElementTree as ET

import pytest

from bpmn_assistant.services import (
    BpmnJsonGenerator,
    BpmnLayoutGenerator,
    BpmnXmlGenerator,
)
from bpmn_assistant.services.process_editing.bpmn_editing_service import (
    BpmnEditingService,
)
from bpmn_assistant.services.process_editing.collaboration_functions import (
    add_message_flow,
    add_participant,
    delete_message_flow,
    delete_participant,
)
from bpmn_assistant.services.validate_bpmn import validate_model

from .test_bpmn_xml_generator import elements_equal


def _editor(model):
    """Build a BpmnEditingService without invoking the LLM/constructor."""
    svc = BpmnEditingService.__new__(BpmnEditingService)
    svc.process = model
    svc.is_collaboration = True
    return svc


def _di_shapes_edges(model):
    xml = BpmnXmlGenerator().create_bpmn_xml(model)
    full = BpmnLayoutGenerator().add_di(model, xml)
    root = ET.fromstring(full)  # must stay well-formed
    plane = root.find("{*}BPMNDiagram").find("{*}BPMNPlane")
    return root, plane.findall("{*}BPMNShape"), plane.findall("{*}BPMNEdge")


class TestCollaborationXml:
    def test_collaboration_structure(self, customer_supplier_collaboration):
        xml = BpmnXmlGenerator().create_bpmn_xml(customer_supplier_collaboration)
        root = ET.fromstring(xml)

        collaboration = root.find("{*}collaboration")
        assert collaboration is not None

        participants = collaboration.findall("{*}participant")
        assert {p.get("id") for p in participants} == {"customer", "supplier"}
        assert all(p.get("processRef") for p in participants)

        message_flows = collaboration.findall("{*}messageFlow")
        assert {mf.get("id") for mf in message_flows} == {"mf1", "mf2"}

        processes = root.findall("{*}process")
        assert {p.get("id") for p in processes} == {"Process_customer", "Process_supplier"}

    def test_black_box_participant(self):
        model = {
            "participants": [
                {
                    "id": "a",
                    "name": "A",
                    "process": [
                        {"type": "startEvent", "id": "a1"},
                        {"type": "task", "id": "a2", "label": "Do"},
                        {"type": "endEvent", "id": "a3"},
                    ],
                },
                {"id": "b", "name": "B"},  # black box: no process
            ],
            "message_flows": [{"id": "m", "sourceRef": "a2", "targetRef": "b"}],
        }
        validate_model(model)  # message flow may target a participant id
        xml = BpmnXmlGenerator().create_bpmn_xml(model)
        root = ET.fromstring(xml)
        # Only one <process> (black-box B has none)
        assert len(root.findall("{*}process")) == 1
        b = next(
            p
            for p in root.find("{*}collaboration").findall("{*}participant")
            if p.get("id") == "b"
        )
        assert b.get("processRef") is None

    def test_round_trip_stable(self, customer_supplier_collaboration):
        gen = BpmnXmlGenerator()
        xml = gen.create_bpmn_xml(customer_supplier_collaboration)
        back = BpmnJsonGenerator().create_bpmn_json(xml)
        # XML regenerated from the round-tripped JSON is identical
        xml2 = gen.create_bpmn_xml(back)
        assert elements_equal(ET.fromstring(xml), ET.fromstring(xml2))

    def test_message_flow_bad_ref_rejected(self, customer_supplier_collaboration):
        customer_supplier_collaboration["message_flows"].append(
            {"id": "bad", "sourceRef": "c_order", "targetRef": "does_not_exist"}
        )
        with pytest.raises(ValueError):
            validate_model(customer_supplier_collaboration)


class TestChoreographyXml:
    def test_choreography_structure(self, buyer_seller_choreography):
        xml = BpmnXmlGenerator().create_bpmn_xml(buyer_seller_choreography)
        root = ET.fromstring(xml)

        choreography = root.find("{*}choreography")
        assert choreography is not None

        bands = choreography.findall("{*}participant")
        assert {p.get("id") for p in bands} == {"buyer", "seller"}

        tasks = choreography.findall("{*}choreographyTask")
        assert {t.get("id") for t in tasks} == {"ct_order", "ct_confirm"}

        order = next(t for t in tasks if t.get("id") == "ct_order")
        assert order.get("initiatingParticipantRef") == "buyer"
        refs = [pr.text for pr in order.findall("{*}participantRef")]
        assert refs == ["buyer", "seller"]

        # <message> definitions emitted at definitions level
        messages = root.findall("{*}message")
        assert {m.get("id") for m in messages} == {"Message_ct_order", "Message_ct_confirm"}

    def test_choreography_validation(self, buyer_seller_choreography):
        validate_model(buyer_seller_choreography)

    def test_choreography_bad_participant_ref(self, buyer_seller_choreography):
        buyer_seller_choreography["choreography"][1]["recipient"] = "ghost"
        with pytest.raises(ValueError):
            validate_model(buyer_seller_choreography)


class TestLayoutDi:
    def _assert_bounds_valid(self, shapes):
        for s in shapes:
            b = s.find("{*}Bounds")
            assert b is not None
            assert float(b.get("width")) > 0
            assert float(b.get("height")) > 0
            float(b.get("x"))
            float(b.get("y"))

    def test_collaboration_di(self, customer_supplier_collaboration):
        root, shapes, edges = _di_shapes_edges(customer_supplier_collaboration)
        self._assert_bounds_valid(shapes)
        shape_refs = {s.get("bpmnElement") for s in shapes}
        # pools + all elements have a shape
        assert {"customer", "supplier"}.issubset(shape_refs)
        assert {"c_start", "c_order", "s_check"}.issubset(shape_refs)
        # message flows are drawn as edges
        edge_refs = {e.get("bpmnElement") for e in edges}
        assert {"mf1", "mf2"}.issubset(edge_refs)

    def test_collaboration_pools_dont_overlap(self, customer_supplier_collaboration):
        _, shapes, _ = _di_shapes_edges(customer_supplier_collaboration)
        pools = {
            s.get("bpmnElement"): s.find("{*}Bounds")
            for s in shapes
            if s.get("bpmnElement") in {"customer", "supplier"}
        }
        a = pools["customer"]
        b = pools["supplier"]
        a_bottom = float(a.get("y")) + float(a.get("height"))
        assert a_bottom <= float(b.get("y"))  # supplier band sits below customer

    def test_choreography_di(self, buyer_seller_choreography):
        _, shapes, edges = _di_shapes_edges(buyer_seller_choreography)
        self._assert_bounds_valid(shapes)
        # choreography tasks get the tall (band) height
        task = next(s for s in shapes if s.get("bpmnElement") == "ct_order")
        assert float(task.find("{*}Bounds").get("height")) == 150

    def test_single_process_di(self, linear_process):
        root, shapes, edges = _di_shapes_edges(linear_process)
        self._assert_bounds_valid(shapes)
        assert root.find("{*}BPMNDiagram").find("{*}BPMNPlane").get("bpmnElement") == "Process_1"


class TestCollaborationEditing:
    def test_add_message_flow(self, customer_supplier_collaboration):
        updated = add_message_flow(
            customer_supplier_collaboration,
            {"id": "mf3", "sourceRef": "s_confirm", "targetRef": "c_recv"},
        )["process"]
        validate_model(updated)
        assert len(updated["message_flows"]) == 3

    def test_add_then_delete_participant(self, customer_supplier_collaboration):
        with_w = add_participant(
            customer_supplier_collaboration,
            {
                "id": "warehouse",
                "name": "Warehouse",
                "process": [
                    {"type": "startEvent", "id": "w_start"},
                    {"type": "task", "id": "w_pick", "label": "Pick goods"},
                    {"type": "endEvent", "id": "w_end"},
                ],
            },
        )["process"]
        validate_model(with_w)
        assert len(with_w["participants"]) == 3

        without_supplier = delete_participant(with_w, "supplier")["process"]
        validate_model(without_supplier)
        assert len(without_supplier["participants"]) == 2
        # mf1 (-> s_start) and mf2 (s_confirm ->) reference supplier elements and are dropped
        assert without_supplier["message_flows"] == []

    def test_delete_message_flow(self, customer_supplier_collaboration):
        updated = delete_message_flow(customer_supplier_collaboration, "mf1")["process"]
        assert {mf["id"] for mf in updated["message_flows"]} == {"mf2"}

    def test_element_edit_routes_to_participant(self, customer_supplier_collaboration):
        svc = _editor(customer_supplier_collaboration)
        updated = svc._update_process(
            customer_supplier_collaboration,
            {
                "function": "add_element",
                "arguments": {
                    "participant_id": "supplier",
                    "element": {"type": "userTask", "id": "s_check2", "label": "Re-check"},
                    "after_id": "s_check",
                },
            },
        )
        validate_model(updated)
        supplier = next(p for p in updated["participants"] if p["id"] == "supplier")
        assert "s_check2" in [e["id"] for e in supplier["process"]]
        # other pool untouched
        customer = next(p for p in updated["participants"] if p["id"] == "customer")
        assert [e["id"] for e in customer["process"]] == ["c_start", "c_order", "c_recv", "c_end"]

    def test_element_edit_requires_participant_id(self, customer_supplier_collaboration):
        svc = _editor(customer_supplier_collaboration)
        with pytest.raises(ValueError):
            svc._update_process(
                customer_supplier_collaboration,
                {
                    "function": "delete_element",
                    "arguments": {"element_id": "s_check"},
                },
            )
