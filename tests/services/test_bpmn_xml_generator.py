from xml.etree import ElementTree as ET

import pytest

from bpmn_assistant.services import BpmnXmlGenerator


def elements_equal(e1: ET.Element, e2: ET.Element) -> bool:
    """Recursively compares two XML elements, ignoring the order of child elements."""
    if e1.tag != e2.tag:
        print(f"Tags do not match: {e1.tag} != {e2.tag}")
        return False
    if (e1.text or "").strip() != (e2.text or "").strip():
        print(f"Texts do not match in tag {e1.tag}: '{e1.text}' != '{e2.text}'")
        return False
    if e1.attrib != e2.attrib:
        print(f"Attributes do not match in tag {e1.tag}: {e1.attrib} != {e2.attrib}")
        return False
    if len(e1) != len(e2):
        print(
            f"Number of children do not match in tag {e1.tag}: {len(e1)} != {len(e2)}"
        )
        return False

    # Create a list of child elements for e2 to track matched elements
    children2 = list(e2)

    for child1 in e1:
        match_found = False
        for child2 in children2:
            if elements_equal(child1, child2):
                match_found = True
                children2.remove(child2)
                break
        if not match_found:
            print(
                f"No matching element found for {ET.tostring(child1, encoding='unicode')}"
            )
            return False
    return True


class TestBpmnXmlGenerator:

    def test_rejects_non_choreography_models(self, empty_gateway_path_process):
        gen = BpmnXmlGenerator()
        with pytest.raises(ValueError):
            gen.create_bpmn_xml(empty_gateway_path_process)  # bare process list
        with pytest.raises(ValueError):
            gen.create_bpmn_xml({"participants": [], "message_flows": []})  # collaboration

    def test_choreography_xml_structure(self, buyer_seller_choreography):
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

    def test_deontic_choreography_xml(self, jade_hotel_choreography):
        """Conditional start, terminate ends, and labeled yes/no flows must be emitted."""
        xml = BpmnXmlGenerator().create_bpmn_xml(jade_hotel_choreography)
        root = ET.fromstring(xml)
        choreo = root.find("{*}choreography")

        # Conditional start event with the required <condition> expression child
        start = choreo.find("{*}startEvent")
        assert start.get("id") == "start_no_seaview"
        cond_def = start.find("{*}conditionalEventDefinition")
        assert cond_def is not None
        assert cond_def.find("{*}condition") is not None

        # Terminate end events on all fulfilled branches; plain end on unfulfilled
        end_events = {e.get("id"): e for e in choreo.findall("{*}endEvent")}
        assert set(end_events) == {
            "end_fulfilled_room",
            "end_fulfilled_spa",
            "end_fulfilled_discount",
            "end_unfulfilled",
        }
        for eid, elem in end_events.items():
            terminate = elem.find("{*}terminateEventDefinition")
            if eid == "end_unfulfilled":
                assert terminate is None
            else:
                assert terminate is not None

        # Every gateway branch flow is labeled, including the yes -> end flows
        flows = choreo.findall("{*}sequenceFlow")
        labeled = {
            (f.get("sourceRef"), f.get("targetRef")): f.get("name") for f in flows
        }
        assert labeled[("gw_alt_room", "end_fulfilled_room")] == "yes"
        assert labeled[("gw_spa_access", "end_fulfilled_spa")] == "yes"
        assert labeled[("gw_discount", "end_fulfilled_discount")] == "yes"
        assert labeled[("gw_discount", "end_unfulfilled")] == "no"
        # empty "no" branches continue to the next compensation task
        assert labeled[("gw_alt_room", "provide_spa_access")] == "no"
        assert labeled[("gw_spa_access", "provide_discount")] == "no"
