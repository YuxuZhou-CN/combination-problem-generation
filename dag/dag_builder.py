"""DAGBuilder - builds Expression DAG from generator operations."""

from __future__ import annotations
from typing import Dict, List, Optional, Any
import uuid

from dag.expr_node import (
    ExprNode, SetNode, BagNode, TupleNode, OperatorNode,
    NodeType, InputType, IndexedAccessNode
)
from dag.problem_structure import ProblemStructure
from loggers import get_logger
logger = get_logger(__name__)


class DAGBuilder:
    """
    Builds Expression DAGs via fluent API.

    Usage:
        builder = DAGBuilder()
        s = builder.create_set(['a', 'b', 'c'])
        result = builder.choose(s, k=2)
        problem = builder.build(root=result)
    """

    def __init__(self):
        self.bindings: Dict[str, ExprNode] = {}
        self._name_counter: Dict[str, int] = {}
        self._node_to_name: Dict[str, str] = {}  # node.id -> name

    def _generate_name(self, prefix: str) -> str:
        """Generate a unique name for a node."""
        if prefix not in self._name_counter:
            self._name_counter[prefix] = 0
        name = f"{prefix}_{self._name_counter[prefix]}"
        self._name_counter[prefix] += 1
        return name

    def _compute_unique_entities(self, node: OperatorNode) -> None:
        """Compute and set the unique_entities field on an operator node."""
        object.__setattr__(node, 'unique_entities', node._get_possible_entities_value())

    def _compute_operator_depth(self, *nodes: ExprNode) -> int:
        """Compute depth for an operator node: max(input depths) + 1."""
        if not nodes:
            return 0
        return max(node.depth for node in nodes if hasattr(node, 'depth')) + 1

    def create_set(self, entitys: List[str]) -> SetNode:
        """Create a Set literal node."""
        node = SetNode(entitys=frozenset(entitys))
        name = self._generate_name('set')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        return node

    def create_bag(self, entitys: Dict[str, int]) -> BagNode:
        """Create a Bag literal node."""
        node = BagNode(entitys=entitys)
        name = self._generate_name('bag')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        return node

    def create_tuple(self, entitys: List[str]) -> TupleNode:
        """Create a Tuple literal node."""
        node = TupleNode(entitys=tuple(entitys))
        name = self._generate_name('tuple')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        return node

    def tuple(self, source: ExprNode) -> OperatorNode:
        """Create a tuple operator node from a set source."""
        node = OperatorNode(
            operator=NodeType.TUPLE,
            inputs=[source]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('tuple')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created tuple node '{name}' with unique_entities={node.unique_entities}")
        return node

    def choose(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a choose operator node."""
        node = OperatorNode(
            operator=NodeType.CHOOSE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('choose')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created choose node '{name}' with unique_entities={node.unique_entities}")
        return node

    def choose_replace(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a choose_replace operator node."""
        node = OperatorNode(
            operator=NodeType.CHOOSE_REPLACE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('choose_replace')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created choose_replace node '{name}' with unique_entities={node.unique_entities}")
        return node

    def choose_tuple(self, source: ExprNode, k: int, replace: bool = False) -> OperatorNode:
        """Create a choose_tuple operator node."""
        node = OperatorNode(
            operator=NodeType.CHOOSE_TUPLE if not replace else NodeType.CHOOSE_REPLACE_TUPLE,
            inputs=[source],
            params={'k': k, 'replace': replace}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('choose_tuple')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created choose_tuple node '{name}' with unique_entities={node.unique_entities}")
        return node

    def sequence(self, source: ExprNode) -> OperatorNode:
        """Create a sequence operator node."""
        node = OperatorNode(
            operator=NodeType.SEQUENCE,
            inputs=[source]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('sequence')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created sequence node '{name}' with unique_entities={node.unique_entities}")
        return node

    def circle(self, source: ExprNode, reflection: bool = False) -> OperatorNode:
        """Create a circle operator node."""
        node = OperatorNode(
            operator=NodeType.CIRCLE,
            inputs=[source],
            params={'reflection': reflection}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('circle')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created circle node '{name}' with unique_entities={node.unique_entities}")
        return node

    def compose(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a compose operator node."""
        node = OperatorNode(
            operator=NodeType.COMPOSE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('compose')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created compose node '{name}' with unique_entities={node.unique_entities}")
        return node

    def partition(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a partition operator node."""
        node = OperatorNode(
            operator=NodeType.PARTITION,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('partition')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created partition node '{name}' with unique_entities={node.unique_entities}")
        return node

    def index_access(self, parent: ExprNode, index: int) -> IndexedAccessNode:
        """Create an index access node for TupleOfSets/TupleOfBags, e.g., groups[1]."""
        node = IndexedAccessNode(parent=parent, index=index)
        name = parent.name + f"[{index}]"
        node.name = name
        node.inputs = parent.inputs
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        return node

    def set_union(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a set union operation."""
        node = OperatorNode(
            operator=NodeType.SET_UNION,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('set_union')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created set_union node '{name}' with unique_entities={node.unique_entities}")
        return node

    def set_intersection(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a set intersection operation."""
        node = OperatorNode(
            operator=NodeType.SET_INTERSECTION,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('set_inter')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created set_intersection node '{name}' with unique_entities={node.unique_entities}")
        return node

    def set_difference(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a set difference operation."""
        node = OperatorNode(
            operator=NodeType.SET_DIFFERENCE,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('set_diff')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created set_difference node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_union(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a bag union operation."""
        node = OperatorNode(
            operator=NodeType.BAG_UNION,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('bag_union')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_union node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_intersection(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a bag intersection operation."""
        node = OperatorNode(
            operator=NodeType.BAG_INTERSECTION,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('bag_inter')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_intersection node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_difference(self, left: ExprNode, right: ExprNode) -> OperatorNode:
        """Create a bag difference operation."""
        node = OperatorNode(
            operator=NodeType.BAG_DIFFERENCE,
            inputs=[left, right]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(left, right))
        name = self._generate_name('bag_diff')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_difference node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_choose(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a bag choose operator node."""
        node = OperatorNode(
            operator=NodeType.BAG_CHOOSE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('bag_choose')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_choose node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_choose_replace(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a bag choose_replace operator node."""
        node = OperatorNode(
            operator=NodeType.BAG_CHOOSE_REPLACE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('bag_choose_replace')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_choose_replace node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_compose(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a bag compose operator node."""
        node = OperatorNode(
            operator=NodeType.BAG_COMPOSE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('bag_compose')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_compose node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_partition(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a bag partition operator node."""
        node = OperatorNode(
            operator=NodeType.BAG_PARTITION,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('bag_partition')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_partition node '{name}' with unique_entities={node.unique_entities}")
        return node

    def bag_support(self, source: ExprNode) -> OperatorNode:
        """Create a bag_support operator node (extracts unique elements as a set)."""
        node = OperatorNode(
            operator=NodeType.BAG_SUPPORT,
            inputs=[source]
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('bag_support')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created bag_support node '{name}' with unique_entities={node.unique_entities}")
        return node

    def choose_replace_sequence(self, source: ExprNode, k: int) -> OperatorNode:
        """Create a choose_replace_sequence operator node."""
        node = OperatorNode(
            operator=NodeType.CHOOSE_REPLACE_SEQUENCE,
            inputs=[source],
            params={'k': k}
        )
        object.__setattr__(node, 'depth', self._compute_operator_depth(source))
        name = self._generate_name('choose_replace_sequence')
        node.name = name
        self.bindings[name] = node
        self._node_to_name[node.id] = name
        self._compute_unique_entities(node)
        logger.debug(f"Created choose_replace_sequence node '{name}' with unique_entities={node.unique_entities}")
        return node

    def add_constraint(self, node: ExprNode, constraint) -> None:
        """Add a constraint to a node."""
        node.constraints.append(constraint)

    def build(self, root: ExprNode) -> ProblemStructure:
        """Build the ProblemStructure from accumulated bindings."""
        return ProblemStructure(
            bindings=dict(self.bindings),
            root=root,
            global_constraints=[]
        )

    def get_name(self, node: ExprNode) -> Optional[str]:
        """Get the binding name for a node."""
        return self._node_to_name.get(node.id)