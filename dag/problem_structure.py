"""ProblemStructure - root container for Expression DAG (plan.md section 9.2)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from dag.expr_node import ExprNode,BagNode,SetNode
from dag.constraints import Constraint


@dataclass
class ProblemStructure:
    """
    Root container for a combinatorial problem (plan.md section 9.2).

    Attributes:
        bindings: Dict mapping variable names to ExprNodes
        root: The final result expression
        global_constraints: List of global constraints
    """
    bindings: Dict[str, ExprNode] = field(default_factory=dict)
    root: ExprNode = None
    global_constraints: List[Constraint] = field(default_factory=list)
    entitys: List[str] = field(default_factory=list)

    def add_binding(self, name: str, node: ExprNode) -> None:
        """Add a variable binding."""
        self.bindings[name] = node

    def get_node_by_name(self, name: str) -> ExprNode:
        """Get a node by binding name."""
        return self.bindings.get(name)

    def all_nodes(self) -> List[ExprNode]:
        """Get all nodes in the DAG (unique, via bindings)."""
        return list(self.bindings.values())

    def collect_constraints(self) -> List[Constraint]:
        """Collect all constraints from all nodes plus global constraints."""
        constraints = list(self.global_constraints)
        for node in self.bindings.values():
            constraints.extend(node.constraints)
        return constraints
    
    def all_operators(self) -> List[str]:
        """Get all operators used in the DAG, excluding INDEXED_ACCESS."""
        from dag.expr_node import NodeType
        operators = set()
        for node in self.bindings.values():
            if node.operator and node.operator != NodeType.INDEXED_ACCESS:
                operators.add(node.operator.name)
        return list(operators)

    def all_non_deterministic_operators(self) -> List[str]:
        """Get all non-deterministic operators used in the DAG, excluding INDEXED_ACCESS."""
        from dag.expr_node import NodeType, OperatorNode
        operators = set()
        for node in self.bindings.values():
            if isinstance(node, OperatorNode) and node.operator:
                if node.operator != NodeType.INDEXED_ACCESS and not node.is_deterministic:
                    operators.add(node.operator.name)
        return list(operators)

    def all_constraints(self) -> List[str]:
        """Get all constraint class names used in the DAG."""
        constraints = set()
        for node in self.bindings.values():
            for constraint in node.constraints:
                constraints.add(constraint.__class__.__name__)
        for constraint in self.global_constraints:
            constraints.add(constraint.__class__.__name__)
        return list(constraints)
    
    def problem_depth(self) -> int:
        """Calculate the depth of the problem DAG."""
        def compute_depth(node: ExprNode) -> int:
            for node_input in node.inputs:
                if isinstance(node_input, BagNode):
                    return 1
                if isinstance(node_input, SetNode):
                    return 1
                return 1 + compute_depth(node_input)
            return 1
        depth = []
        for node in self.bindings.values():
            depth.append(compute_depth(node))

        return max(depth) if depth else 0

    def max_depth(self) -> int:
        """Calculate the maximum depth of all nodes in the DAG."""
        from dag.expr_node import OperatorNode
        def compute_depth(node: ExprNode) -> int:
            if isinstance(node, OperatorNode):
                if node.inputs:
                    return max(compute_depth(inp) for inp in node.inputs) + 1
            return node.depth
        if not self.bindings:
            return 0
        return max(compute_depth(node) for node in self.bindings.values())

    def depth_validate(self, expected_depth: int) -> None:
        """Validate that problem depth meets expected depth, raise if insufficient."""
        max_depth = self.max_depth()
        if max_depth < expected_depth:
            raise ValueError(f"深度不足: 期望{expected_depth}, 实际{max_depth}")