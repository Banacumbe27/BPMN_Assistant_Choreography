import pytest

from bpmn_assistant.services.validate_bpmn import validate_bpmn


class TestValidateBpmn:

    def test_validate_bpmn_duplicate_id(self, buyer_seller_choreography):
        choreography = buyer_seller_choreography["choreography"]
        choreography[2]["id"] = choreography[1]["id"]  # duplicate ct_order

        with pytest.raises(ValueError) as exc_info:
            validate_bpmn(choreography)

        assert str(exc_info.value) == "Duplicate element ID found: ct_order"
