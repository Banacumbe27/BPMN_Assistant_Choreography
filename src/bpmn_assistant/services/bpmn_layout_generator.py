"""
Deterministic BPMN diagram-interchange (DI) generator.

The external `bpmn-auto-layout` library cannot lay out collaborations (pools)
or choreographies, so this module computes coordinates directly in Python and
injects a <bpmndi:BPMNDiagram> block into the generated BPMN XML.

It reuses BpmnProcessTransformer so the element/flow ids it positions are
exactly the ids emitted by BpmnXmlGenerator.
"""

from typing import Union

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
POOL_LABEL_W = 30  # width of the vertical pool label strip
POOL_PAD = 30  # padding inside a pool around its content
BAND_GAP = 60  # vertical gap between pools

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

    def add_di(self, model: Union[list, dict], bpmn_xml: str) -> str:
        """
        Compute DI for the model and splice it into the generated BPMN XML.
        Args:
            model: the process list / collaboration / choreography dict.
            bpmn_xml: the XML produced by BpmnXmlGenerator for that model.
        Returns:
            The BPMN XML with a <bpmndi:BPMNDiagram> block inserted.
        """
        kind = model_type(model)

        if kind == "collaboration":
            di = self._collaboration_di(model)
        elif kind == "choreography":
            di = self._choreography_di(model)
        else:
            process = model["process"] if isinstance(model, dict) else model
            di = self._process_di(process)

        return self._splice(bpmn_xml, di)

    # --- single process ---

    def _process_di(self, process: list) -> str:
        transformed = self.transformer.transform(process)
        shapes, edges, _ = self._layout(transformed, origin=(MARGIN, MARGIN))
        return self._render_diagram("Process_1", shapes, edges)

    # --- collaboration ---

    def _collaboration_di(self, model: dict) -> str:
        shapes: list[str] = []
        edges: list[str] = []
        # element_id -> (x, y, w, h) across the whole collaboration, used to
        # route message flows between pools.
        global_boxes: dict[str, tuple[float, float, float, float]] = {}

        band_y = MARGIN
        content_x = MARGIN + POOL_LABEL_W + POOL_PAD

        for participant in model["participants"]:
            process = participant.get("process") or []
            if process:
                transformed = self.transformer.transform(process)
                p_shapes, p_edges, boxes = self._layout(
                    transformed, origin=(content_x, band_y + POOL_PAD)
                )
                content_w = max((b[0] + b[2] for b in boxes.values()), default=content_x)
                content_h = max((b[1] + b[3] for b in boxes.values()), default=band_y)
                band_h = (content_h - band_y) + POOL_PAD
                shapes.extend(p_shapes)
                edges.extend(p_edges)
                global_boxes.update(boxes)
            else:
                # Black-box pool: empty band of a default size.
                content_w = content_x + 3 * H_SPACING
                band_h = ROW_H + 2 * POOL_PAD

            pool_w = (content_w - MARGIN) + POOL_PAD
            shapes.append(
                self._shape(
                    participant["id"],
                    MARGIN,
                    band_y,
                    pool_w,
                    band_h,
                    is_horizontal=True,
                )
            )
            # Record the pool box so message flows to a black-box pool can attach.
            global_boxes.setdefault(
                participant["id"], (MARGIN, band_y, pool_w, band_h)
            )
            band_y += band_h + BAND_GAP

        for mf in model.get("message_flows", []):
            edge = self._message_flow_edge(mf, global_boxes)
            if edge:
                edges.append(edge)

        return self._render_diagram("Collaboration_1", shapes, edges)

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

        # Group element ids by rank, preserving element order for stable slots.
        by_rank: dict[int, list[str]] = {}
        for e in elements:
            by_rank.setdefault(ranks[e["id"]], []).append(e["id"])

        ox, oy = origin
        boxes: dict[str, tuple[float, float, float, float]] = {}
        for rank, ids in by_rank.items():
            x = ox + rank * H_SPACING
            for slot, eid in enumerate(ids):
                w, h = _element_size(types[eid])
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
        is_horizontal: bool = False,
    ) -> str:
        attrs = f'id="{bpmn_element}_di" bpmnElement="{bpmn_element}"'
        if is_horizontal:
            attrs += ' isHorizontal="true"'
        return (
            f'<bpmndi:BPMNShape {attrs}>'
            f'<dc:Bounds x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" />'
            f"</bpmndi:BPMNShape>"
        )

    def _sequence_edge(self, flow: dict, boxes: dict) -> str:
        sx, sy, sw, sh = boxes[flow["sourceRef"]]
        tx, ty, tw, th = boxes[flow["targetRef"]]
        start = (sx + sw, sy + sh / 2)
        end = (tx, ty + th / 2)
        if abs(start[1] - end[1]) < 1:
            waypoints = [start, end]
        else:
            mid_x = (start[0] + end[0]) / 2
            waypoints = [start, (mid_x, start[1]), (mid_x, end[1]), end]
        return self._edge(flow["id"], waypoints)

    def _message_flow_edge(self, mf: dict, boxes: dict) -> str | None:
        if mf["sourceRef"] not in boxes or mf["targetRef"] not in boxes:
            return None
        sx, sy, sw, sh = boxes[mf["sourceRef"]]
        tx, ty, tw, th = boxes[mf["targetRef"]]
        # Vertical connector between bands (source above or below target).
        if sy < ty:
            start = (sx + sw / 2, sy + sh)
            end = (tx + tw / 2, ty)
        else:
            start = (sx + sw / 2, sy)
            end = (tx + tw / 2, ty + th)
        mid_y = (start[1] + end[1]) / 2
        waypoints = [start, (start[0], mid_y), (end[0], mid_y), end]
        return self._edge(mf["id"], waypoints)

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
