"""ExprNode hierarchy for Expression DAG."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
import uuid


class NodeType(Enum):
    """Node type enumeration matching plan.md section 9.3."""
    SET = "SET"
    TUPLE = "TUPLE"
    CHOOSE = "CHOOSE"
    CHOOSE_REPLACE = "CHOOSE_REPLACE"
    CHOOSE_TUPLE = "CHOOSE_TUPLE"
    CHOOSE_REPLACE_TUPLE = "CHOOSE_REPLACE_TUPLE"
    CHOOSE_REPLACE_SEQUENCE = "CHOOSE_REPLACE_SEQUENCE"
    SEQUENCE = "SEQUENCE"
    CIRCLE = "CIRCLE"
    COMPOSE = "COMPOSE"
    PARTITION = "PARTITION"
    SET_UNION = "SET_UNION"      # Set union (A + B)
    SET_INTERSECTION = "SET_INTERSECTION" # Set intersection (A & B)
    SET_DIFFERENCE = "SET_DIFFERENCE"  # Set difference (A - B)
    INDEXED_ACCESS = "INDEXED_ACCESS"  # Index access into tuple (e.g., p2[1])

    BAG = "BAG"
    BAG_UNION = "BAG_UNION"       # Bag union (A + B)
    BAG_DIFFERENCE = "BAG_DIFFERENCE" # Bag difference (A - B)
    BAG_INTERSECTION = "BAG_INTERSECTION" # Bag intersection (A & B)

# 确定性操作集合：输入全确定时输出才确定
DETERMINISTIC_OPERATORS: frozenset = frozenset({
    NodeType.SET_UNION,
    NodeType.SET_INTERSECTION,
    NodeType.SET_DIFFERENCE,
    NodeType.BAG_UNION,
    NodeType.BAG_INTERSECTION,
    NodeType.BAG_DIFFERENCE,
})

class InputType(Enum):
    """Input type for operators - describes what a node produces."""
    SET = "SET"       # A SetNode or derived Set
    BAG = "BAG"       # A BagNode or derived Bag
    TUPLE = "TUPLE"     # A TupleNode or derived Tuple
    TUPLE_OF_SETS = "TUPLE_OF_SETS" # TUPLE_OF_SETS (compose/partition output)
    TUPLE_OF_BAGS = "TUPLE_OF_BAGS" # TUPLE_OF_BAGS
    INDEXED_SET = "INDEXED_SET" # Indexed access returning SET
    INDEXED_BAG = "INDEXED_BAG" # Indexed access returning BAG
    ANY = "ANY"       # Can accept any type

@dataclass
class ExprNode(ABC):
    """Abstract base for all expression nodes (plan.md section 9.2)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = field(default="")
    constraints: List = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 可能存在的实体（如果已知）--- IGNORE ---
    unique_entities: frozenset = field(default_factory=frozenset)
    depth: int = 0  # NEW FIELD
    def __hash__(self):
        """Hash based on unique id for use as dict keys."""
        return hash(self.id)

    def get_name(self) -> str:
        """Return the name of this node."""
        return self.name

    @property
    @abstractmethod
    def node_type(self) -> NodeType:
        """Return the node type."""
        pass

    @property
    @abstractmethod
    def output_type(self) -> InputType:
        """Return the output type."""
        pass

    @abstractmethod
    def get_possible_entities(self) -> frozenset:
        """Return frozenset of all entities that could appear in this node's output."""
        pass

    @abstractmethod
    def is_deterministic(self) -> bool:
        """Return True if this node's output is deterministic given current inputs."""
        pass

@dataclass(eq=False)
class SetNode(ExprNode):
    """Set literal node or derived set node."""
    entitys: Union[frozenset, range, None] = field(default=None)
    inputs: List[ExprNode] = field(default_factory=list)
    operator: Optional[NodeType] = field(default=None)  # For derived sets: SET_UNION, SET_INTERSECTION, SET_DIFFERENCE

    def __post_init__(self):
        """Convert entitys to frozenset if needed."""
        if isinstance(self.entitys, (list, set)):
            object.__setattr__(self, 'entitys', frozenset(self.entitys))
        # Compute unique_entities
        if self.entitys is None:
            object.__setattr__(self, 'unique_entities', frozenset())
        elif isinstance(self.entitys, range):
            object.__setattr__(self, 'unique_entities', frozenset(self.entitys))
        else:
            object.__setattr__(self, 'unique_entities', frozenset(self.entitys))
        # Explicitly set depth=0
        object.__setattr__(self, 'depth', 0)

    @property
    def node_type(self) -> NodeType:
        return NodeType.SET

    @property
    def output_type(self) -> InputType:
        return InputType.SET

    @property
    def is_derived(self) -> bool:
        """True if this set is derived from an operation (has inputs)."""
        return len(self.inputs) > 0

    def get_input_type(self) -> InputType:
        """Return the InputType for this node (used in type-based DAG construction)."""
        return InputType.SET

    def get_possible_entities(self) -> frozenset:
        """Return entities in this set."""
        if self.entitys is None:
            return frozenset()
        if isinstance(self.entitys, range):
            return frozenset(self.entitys)
        return frozenset(self.entitys)

    @property
    def is_deterministic(self) -> bool:
        """Base nodes are always deterministic."""
        return True

@dataclass(eq=False)
class BagNode(ExprNode):
    """Bag literal node or derived bag node."""
    entitys: Dict[str, int] = field(default_factory=dict)
    inputs: List[ExprNode] = field(default_factory=list)
    operator: Optional[NodeType] = field(default=None)  # For derived bags: BAG_UNION, BAG_INTERSECTION, BAG_DIFFERENCE

    def __post_init__(self):
        """Compute unique_entities from entitys keys."""
        if self.entitys:
            object.__setattr__(self, 'unique_entities', frozenset(self.entitys.keys()))
        else:
            object.__setattr__(self, 'unique_entities', frozenset())
        # Explicitly set depth=0
        object.__setattr__(self, 'depth', 0)

    @property
    def node_type(self) -> NodeType:
        return NodeType.BAG

    @property
    def output_type(self) -> InputType:
        return InputType.BAG

    @property
    def is_derived(self) -> bool:
        """True if this bag is derived from an operation (has inputs)."""
        return len(self.inputs) > 0

    def get_input_type(self) -> InputType:
        """Return the InputType for this node (used in type-based DAG construction)."""
        return InputType.BAG

    def get_possible_entities(self) -> frozenset:
        """Return all unique entities in this bag."""
        return frozenset(self.entitys.keys()) if self.entitys else frozenset()

    @property
    def is_deterministic(self) -> bool:
        """Base nodes are always deterministic."""
        return True


@dataclass(eq=False)
class TupleNode(ExprNode):
    """Tuple literal node or derived tuple node."""
    entitys: tuple = field(default_factory=tuple)
    inputs: List[ExprNode] = field(default_factory=list)

    def __post_init__(self):
        """Convert entitys to tuple if needed."""
        if not isinstance(self.entitys, tuple):
            object.__setattr__(self, 'entitys', tuple(self.entitys))
        # Compute unique_entities
        if not self.entitys:
            object.__setattr__(self, 'unique_entities', frozenset())
        else:
            result = set()
            for e in self.entitys:
                if isinstance(e, (set, frozenset)):
                    result.update(e)
                else:
                    result.add(e)
            object.__setattr__(self, 'unique_entities', frozenset(result))
        # Explicitly set depth=0
        object.__setattr__(self, 'depth', 0)

    @property
    def node_type(self) -> NodeType:
        return NodeType.TUPLE

    @property
    def output_type(self) -> InputType:
        return InputType.TUPLE

    @property
    def is_derived(self) -> bool:
        """True if this tuple is derived from an operation (has inputs)."""
        return len(self.inputs) > 0

    def get_input_type(self) -> InputType:
        """Return the InputType for this node (used in type-based DAG construction)."""
        return InputType.TUPLE

    def get_possible_entities(self) -> frozenset:
        """Return all entities in this tuple."""
        if not self.entitys:
            return frozenset()
        result = set()
        for e in self.entitys:
            if isinstance(e, (set, frozenset)):
                result.update(e)
            else:
                result.add(e)
        return frozenset(result)

    @property
    def is_deterministic(self) -> bool:
        """Base nodes are always deterministic."""
        return True


@dataclass(eq=False)
class IndexedAccessNode(ExprNode):
    """Represents index access into a TupleOfSets/TupleOfBags, e.g., p2[1]."""
    parent: ExprNode = field(default=None)  # The tuple-of-sets/bags node
    index: int = field(default=1)           # 1-based index
    inputs: List[ExprNode] = field(default_factory=list)

    def __post_init__(self):
        """Compute unique_entities from parent and set depth."""
        if self.parent and hasattr(self.parent, 'unique_entities'):
            object.__setattr__(self, 'unique_entities', self.parent.unique_entities)
        else:
            object.__setattr__(self, 'unique_entities', frozenset())
        # Set depth from parent
        if self.parent and hasattr(self.parent, 'depth'):
            object.__setattr__(self, 'depth', self.parent.depth)
        else:
            object.__setattr__(self, 'depth', 0)

    @property
    def node_type(self) -> NodeType:
        return NodeType.INDEXED_ACCESS

    @property
    def output_type(self) -> InputType:
        # If parent is TUPLE_OF_SETS, this returns SET
        # If parent is TUPLE_OF_BAGS, this returns BAG
        if isinstance(self.parent, OperatorNode):
            if self.parent.operator in (NodeType.COMPOSE, NodeType.PARTITION):
                if self.parent.inputs and isinstance(self.parent.inputs[0], BagNode):
                    return InputType.BAG
                return InputType.SET
        return InputType.SET

    def get_input_type(self) -> InputType:
        """Return the InputType for this node (used in type-based DAG construction)."""
        if self.output_type == InputType.BAG:
            return InputType.INDEXED_BAG
        return InputType.INDEXED_SET

    def get_possible_entities(self) -> frozenset:
        """Return entities from the accessed element."""
        if self.parent and hasattr(self.parent, 'get_possible_entities'):
            return self.parent.get_possible_entities()
        return frozenset()

    @property
    def is_deterministic(self) -> bool:
        """Determinism depends on the parent node."""
        if self.parent is None:
            return True
        return getattr(self.parent, 'is_deterministic', True)



@dataclass(eq=False)
class OperatorNode(ExprNode):
    """Operator node (internal DAG node)."""
    operator: NodeType = field(default=None)
    inputs: List[ExprNode] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    entitys: frozenset = field(default_factory=frozenset)  # For derived nodes, entities may be unknown at creation
    entitys_numbers:int = field(default=0) # For derived nodes, entities numbers may be unknown at creation
    _is_deterministic: Optional[bool] = field(default=None, repr=False)

    @property
    def node_type(self) -> NodeType:
        return self.operator

    @property
    def output_type(self) -> InputType:
        """Derive output type from operator and input type."""
        # For operators that need input info to determine output
        if self.inputs and self.operator in (
            NodeType.CHOOSE, NodeType.CHOOSE_REPLACE,
            NodeType.CHOOSE_TUPLE, NodeType.CHOOSE_REPLACE_TUPLE,
            NodeType.SEQUENCE, NodeType.CIRCLE,
            NodeType.CHOOSE_REPLACE_SEQUENCE
        ):
            input_type = self.inputs[0].output_type
            if input_type:
                return self._get_output_from_input_type(input_type)

        # Fallback: operator-based logic
        return self._get_output_from_operator()


    def _get_output_from_input_type(self, input_type: InputType) -> InputType:
        """Get output type from input type using registry mapping."""
        from dag.operator_registry import get_signature
        sig = get_signature(self.operator)
        if sig and sig.input_to_output_map:
            mapped = sig.input_to_output_map.get(input_type)
            if mapped:
                return mapped
        return self._get_output_from_operator()

    def _get_output_from_operator(self) -> InputType:
        """Get output type purely from operator (fallback)."""
        if self.operator in (NodeType.SET, NodeType.SET_UNION,
                            NodeType.SET_INTERSECTION, NodeType.SET_DIFFERENCE):
            return InputType.SET
        elif self.operator in (NodeType.BAG, NodeType.BAG_UNION,
                              NodeType.BAG_INTERSECTION, NodeType.BAG_DIFFERENCE):
            return InputType.BAG
        elif self.operator in (NodeType.TUPLE, NodeType.CHOOSE_TUPLE,
                              NodeType.CHOOSE_REPLACE_TUPLE, NodeType.SEQUENCE,
                              NodeType.CIRCLE, NodeType.CHOOSE_REPLACE_SEQUENCE):
            return InputType.TUPLE
        elif self.operator == NodeType.COMPOSE:
            return InputType.TUPLE_OF_SETS
        elif self.operator == NodeType.PARTITION:
            return InputType.TUPLE_OF_SETS
        return InputType.BAG  # Default fallback

    def get_input_type(self) -> InputType:
        """Return the InputType for this node (used in type-based DAG construction)."""
        from dag.operator_registry import get_output_type
        return get_output_type(self.operator)

    def _get_possible_entities_value(self) -> frozenset:
        """
        Return all entities that could appear in this operator's output.
        Internal implementation - use unique_entities property instead.
        """
        if not self.inputs:
            return frozenset()

        # Collect entities from all inputs
        input_entities_list = []
        for inp in self.inputs:
            if hasattr(inp, 'unique_entities'):
                input_entities_list.append(inp.unique_entities)
            elif hasattr(inp, 'entitys'):
                # Fallback for nodes that have entitys but not get_possible_entities
                if isinstance(inp.entitys, frozenset):
                    input_entities_list.append(inp.entitys)
                elif isinstance(inp.entitys, dict):
                    input_entities_list.append(frozenset(inp.entitys.keys()))
                elif isinstance(inp.entitys, (list, tuple)):
                    input_entities_list.append(frozenset(inp.entitys))

        if not input_entities_list:
            return frozenset()

        # Merge all input entities
        merged = set()
        for entities in input_entities_list:
            merged.update(entities)
        all_entities = frozenset(merged)

        # Apply operator-specific rules
        if self.operator in (NodeType.CHOOSE, NodeType.CHOOSE_TUPLE):
            return all_entities
        elif self.operator in (NodeType.CHOOSE_REPLACE, NodeType.CHOOSE_REPLACE_TUPLE,
                                NodeType.CHOOSE_REPLACE_SEQUENCE):
            return all_entities
        elif self.operator in (NodeType.SEQUENCE, NodeType.CIRCLE):
            return all_entities
        elif self.operator in (NodeType.COMPOSE, NodeType.PARTITION):
            return all_entities
        elif self.operator == NodeType.SET_UNION:
            return all_entities
        elif self.operator == NodeType.SET_INTERSECTION:
            if len(input_entities_list) >= 2:
                return frozenset.intersection(*input_entities_list)
            return frozenset()
        elif self.operator == NodeType.SET_DIFFERENCE:
            if len(input_entities_list) >= 2:
                result = input_entities_list[0]
                for entities in input_entities_list[1:]:
                    result = result - entities
                return frozenset(result)
            return frozenset()
        elif self.operator in (NodeType.BAG_UNION, NodeType.BAG_INTERSECTION, NodeType.BAG_DIFFERENCE):
            if self.operator == NodeType.BAG_UNION:
                return all_entities
            elif self.operator == NodeType.BAG_INTERSECTION:
                if len(input_entities_list) >= 2:
                    return frozenset.intersection(*input_entities_list)
                return frozenset()
            elif self.operator == NodeType.BAG_DIFFERENCE:
                if len(input_entities_list) >= 2:
                    result = input_entities_list[0]
                    for entities in input_entities_list[1:]:
                        result = result - entities
                    return frozenset(result)
                return frozenset()

        return all_entities

    @property
    def get_possible_entities(self) -> frozenset:
        """DEPRECATED: Use unique_entities property instead."""
        import warnings
        warnings.warn(
            "get_possible_entities() is deprecated, use unique_entities property instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.unique_entities

    @property
    def is_deterministic(self) -> bool:
        """Return True if this node's output is deterministic given current inputs."""
        if self._is_deterministic is not None:
            return self._is_deterministic

        if self.operator in DETERMINISTIC_OPERATORS:
            # Deterministic only if ALL inputs are deterministic
            result = all(inp.is_deterministic for inp in self.inputs if hasattr(inp, 'is_deterministic'))
        else:
            # Non-deterministic operators always produce non-deterministic output
            result = False

        self._is_deterministic = result
        return result

    def get_entity_candidates(self, target_entities: frozenset = None) -> list:
        """
        Get a list of entity candidates from this node's possible entities.
        Returns a list suitable for random selection.

        If target_entities is provided, use those instead.
        This ensures constraints sample from the target node's actual entities.
        """
        if target_entities is not None:
            return list(target_entities) if target_entities else []
        entities = self.get_possible_entities
        if not entities:
            return []
        return list(entities)

    def get_max_count(self) -> int:
        """
        Get the maximum possible count for this node.
        For CHOOSE_REPLACE and variants: max is k (with replacement)
        For CHOOSE and other no-replacement operators: max is 1
        For SEQUENCE/CIRCLE: max is 1
        """
        k = self.params.get('k')
        if k is None:
            return 1
        # For replacement operators, count can be up to k
        if self.operator in (NodeType.CHOOSE_REPLACE, NodeType.CHOOSE_REPLACE_TUPLE,
                            NodeType.CHOOSE_REPLACE_SEQUENCE):
            return k
        # For non-replacement operators, count is at most 1
        elif self.operator in (NodeType.CHOOSE, NodeType.CHOOSE_TUPLE):
            return min(k, 1)
        # For SEQUENCE/CIRCLE, each element appears exactly once
        elif self.operator in (NodeType.SEQUENCE, NodeType.CIRCLE):
            return 1
        return k

    def get_max_dedup_count(self, set_target_size: int) -> int:
        """
        Get the maximum possible dedup_count for this node.
        Dedup_count is the count of distinct elements from set_target in this node.
        Max is min(k, set_target_size) for CHOOSE_REPLACE variants.
        """
        k = self.params.get('k')
        if k is None:
            return set_target_size
        if self.operator in (NodeType.CHOOSE_REPLACE, NodeType.CHOOSE_REPLACE_TUPLE,
                            NodeType.CHOOSE_REPLACE_SEQUENCE):
            return min(k, set_target_size)
        return set_target_size

ALL_OPERATOR = [ ]