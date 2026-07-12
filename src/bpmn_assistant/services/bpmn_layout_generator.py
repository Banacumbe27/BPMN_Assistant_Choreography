"""
Deterministic BPMN diagram-interchange (DI) generator.

The external `bpmn-auto-layout` library cannot lay out choreographies, so this
module computes coordinates directly in Python and injects a
<bpmndi:BPMNDiagram> block into the generated BPMN XML.

It reuses BpmnProcessTransformer so the element/flow ids it positions are
exactly the ids emitted by BpmnXmlGenerator.
"""

from bpmn_assistant.core.schemas import model_type
from bpmn_assistant.services.bpmn_process_transformer import BpmnProcessTransformer

# Element sizing
EVENT_SIZE = 36
GATEWAY_SIZE = 50
TASK_W, TASK_H = 100, 80
CHOREO_W, CHOREO_H = 100, 150
BAND_HEIGHT = 20  # chor-js participant band strip height (BandUtil.js)

# Spacing
H_SPACING = 150  # horizontal distance between layers (columns)
V_SPACING = 120  # vertical distance between slots (rows)
ROW_H = 80  # nominal row height used to vertically center elements
MARGIN = 50

EVENT_TYPES = {
    "startEvent",
    "endEvent",
    "intermediateThrowEvent",
    "intermediateCatchEvent",
}
GATEWAY_TYPES = {"exclusiveGateway", "inclusiveGateway", "parallelGateway"}


def _element_size(element_type: str) -> tuple[int, int]:
    if element_type in EVENT_TYPES:
        return EVENT_SIZE, EVENT_SIZE
    if element_type in GATEWAY_TYPES:
        return GATEWAY_SIZE, GATEWAY_SIZE
    if element_type == "choreographyTask":
        return CHOREO_W, CHOREO_H
    return TASK_W, TASK_H


class BpmnLayoutGenerator:
    def __init__(self):
        self.transformer = BpmnProcessTransformer()

    def add_di(self, model: dict, bpmn_xml: str) -> str:
        """
        Compute DI for the choreography model and splice it into the generated BPMN XML.
        Args:
            model: the choreography dict.
            bpmn_xml: the XML produced by BpmnXmlGenerator for that model.
        Returns:
            The BPMN XML with a <bpmndi:BPMNDiagram> block inserted.
        """
        model_type(model)  # raises for anything that is not a choreography
        di = self._choreography_di(model)
        return self._splice(bpmn_xml, di)

    # --- choreography ---

    def _choreography_di(self, model: dict) -> str:
        choreography = model["choreography"]
        transformed = self.transformer.transform(choreography)
        shapes, edges, boxes = self._layout(transformed, origin=(MARGIN, MARGIN))

        # Per choreographyTask, add the two participant-band shapes chor-js needs
        # to draw the top/bottom strips (initiator on top, recipient on bottom).
        task_meta = {
            el["id"]: el
            for el in self._iter_elements(choreography)
            if el.get("type") == "choreographyTask"
        }
        for tid, meta in task_meta.items():
            if tid not in boxes:
                continue
            x, y, w, h = boxes[tid]
            shapes.append(
                self._band_shape(tid, meta["initiator"], "top_initiating", x, y, w)
            )
            shapes.append(
                self._band_shape(
                    tid, meta["recipient"], "bottom_non_initiating", x, y + h - BAND_HEIGHT, w
                )
            )

        return self._render_diagram("Choreography_1", shapes, edges)

    def _iter_elements(self, process: list[dict]) -> list[dict]:
        """Recursively yield every element in a (possibly branched) process list."""
        result: list[dict] = []
        for element in process:
            result.append(element)
            if "branches" in element:
                for branch in element["branches"]:
                    path = branch.get("path", branch) if isinstance(branch, dict) else branch
                    result.extend(self._iter_elements(path))
        return result

    def _band_shape(
        self, task_id: str, participant_id: str, band_kind: str, x: float, y: float, w: float
    ) -> str:
        """A participant band BPMNShape attached to a choreography activity shape."""
        return (
            f'<bpmndi:BPMNShape id="{task_id}_di_band_{participant_id}" '
            f'bpmnElement="{participant_id}" isMessageVisible="false" '
            f'participantBandKind="{band_kind}" '
            f'choreographyActivityShape="{task_id}_di">'
            f'<dc:Bounds x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(BAND_HEIGHT)}" />'
            f"</bpmndi:BPMNShape>"
        )

    # --- core layout ---

    def _layout(
        self, transformed: dict, origin: tuple[float, float]
    ) -> tuple[list[str], list[str], dict[str, tuple[float, float, float, float]]]:
        """
        Position the transformed elements left-to-right by layer rank and return
        (shape_xml_list, edge_xml_list, boxes) where boxes maps element id to its
        (x, y, w, h).
        """
        elements = transformed["elements"]
        flows = transformed["flows"]
        types = {e["id"]: e["type"] for e in elements}

        ranks = self._compute_ranks(elements, flows)

        # A terminating end event fed by a single gateway drops straight below
        # that gateway (same column) - the usual shape of deontic compensation
        # chains, where each "Contract fulfilled" hangs under its gateway while
        # the "no" path continues to the right.
        incoming: dict[str, list[str]] = {}
        for f in flows:
            incoming.setdefault(f["targetRef"], []).append(f["sourceRef"])
        for e in elements:
            if (
                e["type"] == "endEvent"
                and e.get("eventDefinition") == "terminateEventDefinition"
                and len(incoming.get(e["id"], [])) == 1
            ):
                source = incoming[e["id"]][0]
                if types.get(source) in GATEWAY_TYPES:
                    ranks[e["id"]] = ranks[source]

        # Group element ids by rank, preserving element order for stable slots.
        by_rank: dict[int, list[str]] = {}
        for e in elements:
            by_rank.setdefault(ranks[e["id"]], []).append(e["id"])

        # Within a rank, keep the continuing (main-chain) elements on the top
        # row and let end events hang below them.
        for ids in by_rank.values():
            ids.sort(key=lambda eid: types[eid] == "endEvent")

        ox, oy = origin
        boxes: dict[str, tuple[float, float, float, float]] = {}
        for rank, ids in by_rank.items():
            col_x = ox + rank * H_SPACING
            col_w = max(_element_size(types[eid])[0] for eid in ids)
            for slot, eid in enumerate(ids):
                w, h = _element_size(types[eid])
                # Center each element horizontally within its column so that
                # vertical connectors (gateway -> end event below) are straight.
                x = col_x + (col_w - w) / 2
                y = oy + slot * V_SPACING + (ROW_H - h) / 2
                boxes[eid] = (x, y, w, h)

        shapes = [
            self._shape(eid, *boxes[eid]) for eid in (e["id"] for e in elements)
        ]
        edges = [
            self._sequence_edge(flow, boxes)
            for flow in flows
            if flow["sourceRef"] in boxes and flow["targetRef"] in boxes
        ]
        return shapes, edges, boxes

    def _compute_ranks(self, elements: list[dict], flows: list[dict]) -> dict[str, int]:
        """Longest-path layer assignment over the flow DAG (back edges excluded)."""
        ids = [e["id"] for e in elements]
        adj: dict[str, list[str]] = {i: [] for i in ids}
        for f in flows:
            if f["sourceRef"] in adj and f["targetRef"] in adj:
                adj[f["sourceRef"]].append(f["targetRef"])

        # Identify back edges via DFS so loops don't inflate ranks.
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {i: WHITE for i in ids}
        back_edges: set[tuple[str, str]] = set()

        def dfs(u: str) -> None:
            color[u] = GRAY
            for v in adj[u]:
                if color[v] == GRAY:
                    back_edges.add((u, v))
                elif color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for i in ids:
            if color[i] == WHITE:
                dfs(i)

        forward: dict[str, list[str]] = {i: [] for i in ids}
        indeg = {i: 0 for i in ids}
        for u in ids:
            for v in adj[u]:
                if (u, v) in back_edges:
                    continue
                forward[u].append(v)
                indeg[v] += 1

        # Kahn topological order, then relax ranks along it.
        rank = {i: 0 for i in ids}
        queue = [i for i in ids if indeg[i] == 0]
        order: list[str] = []
        indeg_work = dict(indeg)
        while queue:
            u = queue.pop(0)
            order.append(u)
            for v in forward[u]:
                indeg_work[v] -= 1
                if indeg_work[v] == 0:
                    queue.append(v)
        for u in order:
            for v in forward[u]:
                if rank[u] + 1 > rank[v]:
                    rank[v] = rank[u] + 1
        return rank

    # --- XML rendering helpers ---

    def _shape(
        self,
        bpmn_element: str,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> str:
        attrs = f'id="{bpmn_element}_di" bpmnElement="{bpmn_element}"'
        return (
            f'<bpmndi:BPMNShape {attrs}>'
            f'<dc:Bounds x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" />'
            f"</bpmndi:BPMNShape>"
        )

    def _sequence_edge(self, flow: dict, boxes: dict) -> str:
        sx, sy, sw, sh = boxes[flow["sourceRef"]]
        tx, ty, tw, th = boxes[flow["targetRef"]]
        # Target sits (roughly) directly below the source: drop a straight
        # vertical connector from the source's bottom to the target's top.
        if ty >= sy + sh and abs((sx + sw / 2) - (tx + tw / 2)) < 1:
            waypoints = [(sx + sw / 2, sy + sh), (tx + tw / 2, ty)]
            return self._edge(flow["id"], waypoints)
        start = (sx + sw, sy + sh / 2)
        end = (tx, ty + th / 2)
        if abs(start[1] - end[1]) < 1:
            waypoints = [start, end]
        else:
            mid_x = (start[0] + end[0]) / 2
            waypoints = [start, (mid_x, start[1]), (mid_x, end[1]), end]
        return self._edge(flow["id"], waypoints)

    def _edge(self, bpmn_element: str, waypoints: list[tuple[float, float]]) -> str:
        wps = "".join(
            f'<di:waypoint x="{_n(x)}" y="{_n(y)}" />' for x, y in waypoints
        )
        return (
            f'<bpmndi:BPMNEdge id="{bpmn_element}_di" bpmnElement="{bpmn_element}">'
            f"{wps}</bpmndi:BPMNEdge>"
        )

    def _render_diagram(
        self, plane_element: str, shapes: list[str], edges: list[str]
    ) -> str:
        return (
            '<bpmndi:BPMNDiagram id="BPMNDiagram_1">'
            f'<bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{plane_element}">'
            + "".join(shapes)
            + "".join(edges)
            + "</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>"
        )

    def _splice(self, bpmn_xml: str, di: str) -> str:
        marker = "</definitions>"
        idx = bpmn_xml.rfind(marker)
        if idx == -1:
            raise ValueError("Could not find </definitions> to insert DI")
        return bpmn_xml[:idx] + di + bpmn_xml[idx:]


def _n(value: float) -> str:
    """Render a coordinate as an int when whole, else trimmed float."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"
