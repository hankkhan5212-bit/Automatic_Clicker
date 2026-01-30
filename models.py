"""
数据模型：NodeModel 和 FlowModel（与之前相同，JSON 可序列化）
"""
import json
import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

@dataclass
class NodeModel:
    id: str
    label: str
    x: int
    y: int
    image_path: str = ""
    retries: int = 3
    wait_secs: float = 1.0
    clicks: int = 1
    double_click: bool = False
    post_wait: float = 0.5
    confidence: Optional[float] = None
    on_fail: str = "stop"
    is_start: bool = False

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return NodeModel(**d)

@dataclass
class FlowModel:
    nodes: Dict[str, NodeModel] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)

    def add_node(self, node: NodeModel):
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []

    def remove_node(self, node_id: str):
        self.nodes.pop(node_id, None)
        self.edges.pop(node_id, None)
        for src, targets in list(self.edges.items()):
            if node_id in targets:
                targets.remove(node_id)

    def add_edge(self, src: str, dst: str):
        if src not in self.edges:
            self.edges[src] = []
        if dst not in self.edges[src]:
            self.edges[src].append(dst)

    def remove_edge(self, src: str, dst: str):
        if src in self.edges and dst in self.edges[src]:
            self.edges[src].remove(dst)

    def to_json(self) -> str:
        data = {"nodes": {nid: node.to_dict() for nid, node in self.nodes.items()}, "edges": self.edges}
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def from_json(text: str):
        data = json.loads(text)
        fm = FlowModel()
        for nid, nd in data.get("nodes", {}).items():
            fm.nodes[nid] = NodeModel.from_dict(nd)
        fm.edges = data.get("edges", {})
        for nid in fm.nodes.keys():
            if nid not in fm.edges:
                fm.edges[nid] = []
        return fm

def make_default_node(x=50, y=50, label_prefix="Node"):
    nid = str(uuid.uuid4())
    return NodeModel(id=nid, label=label_prefix, x=x, y=y)