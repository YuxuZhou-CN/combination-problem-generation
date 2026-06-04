"""DAGValidator - validates ProblemStructure for type safety and correctness."""

from __future__ import annotations
from typing import List, Tuple, Dict
import networkx as nx

from dag.expr_node import ExprNode, SetNode, BagNode, TupleNode, OperatorNode, NodeType, OutputType
from dag.problem_structure import ProblemStructure
from dag.constraints import Constraint, CountConstraint, MemberConstraint, CardinalityConstraint


class ValidationError(Exception):
    """Validation error with description."""
    def __init__(self, message: str, node: ExprNode = None):
        super().__init__(message)
        self.node = node
        self.message = message


class DAGValidator:
    """
    Validates ProblemStructure according to plan.md rules:
    - Type compatibility: operator inputs must match expected types
    - Constraint applicability: constraints must apply to compatible output types
    - Cycle detection: DAG must be acyclic
    """

    # Mapping of operator -> (input_types, output_type)
    OPERATOR_SIGNATURES = {
        NodeType.CHOOSE: ((OutputType.SET, OutputType.BAG), OutputType.SET),
        NodeType.CHOOSE_REPLACE: (OutputType.SET, OutputType.BAG),
        NodeType.CHOOSE_TUPLE: (OutputType.SET, OutputType.TUPLE),
        NodeType.CHOOSE_REPLACE_TUPLE: (OutputType.SET, OutputType.TUPLE),
        NodeType.SEQUENCE: (OutputType.SET, OutputType.TUPLE),
        NodeType.CIRCLE: (OutputType.SET, OutputType.TUPLE),
        NodeType.COMPOSE: ((OutputType.SET, OutputType.BAG), OutputType.TUPLE_OF_SETS),
        NodeType.PARTITION: ((OutputType.SET, OutputType.BAG), OutputType.TUPLE_OF_SETS),
    }

    # Constraints applicable to each output type
    CONSTRAINT_APPLICABILITY = {
        OutputType.SET: ['CardinalityConstraint', 'MemberConstraint', 'SubsetConstraint', 'DisjointConstraint'],
        OutputType.BAG: ['CountConstraint', 'MemberConstraint', 'CardinalityConstraint'],
        OutputType.TUPLE: ['PositionConstraint', 'CountConstraint', 'AdjacentConstraint', 'TogetherConstraint', 'MemberConstraint'],
        OutputType.TUPLE_OF_SETS: ['CardinalityConstraint', 'MemberConstraint'],
        OutputType.TUPLE_OF_BAGS: ['CardinalityConstraint', 'MemberConstraint'],
    }

    def validate_problem(self, problem: ProblemStructure) -> List[ValidationError]:
        """Validate the entire problem structure."""
        errors = []

        # Check for cycles
        if self._has_cycle(problem):
            errors.append(ValidationError("Problem contains a cycle"))

        # Validate each node
        for name, node in problem.bindings.items():
            errors.extend(self._validate_node(node))

        return errors

    def _validate_node(self, node: ExprNode) -> List[ValidationError]:
        """Validate a single node."""
        errors = []

        if isinstance(node, OperatorNode):
            errors.extend(self._validate_operator(node))
            errors.extend(self._validate_constraints(node))

        return errors

    def _validate_operator(self, node: OperatorNode) -> List[ValidationError]:
        """Validate operator input/output types."""
        errors = []

        if node.operator not in self.OPERATOR_SIGNATURES:
            errors.append(ValidationError(f"Unknown operator: {node.operator}", node))
            return errors

        expected_input_type, expected_output_type = self.OPERATOR_SIGNATURES[node.operator]

        # Check input types
        if not node.inputs:
            errors.append(ValidationError(f"Operator {node.operator} has no inputs", node))
        else:
            for inp in node.inputs:
                actual_type = inp.output_type
                if isinstance(expected_input_type, tuple):
                    valid = actual_type in expected_input_type
                else:
                    valid = actual_type == expected_input_type

                if not valid:
                    errors.append(ValidationError(
                        f"Operator {node.operator} expects {expected_input_type} input, got {actual_type}",
                        node
                    ))

        # Check output type
        if node.output_type != expected_output_type:
            errors.append(ValidationError(
                f"Operator {node.operator} outputs {expected_output_type}, got {node.output_type}",
                node
            ))

        return errors

    def _validate_constraints(self, node: ExprNode) -> List[ValidationError]:
        """Validate that constraints are applicable to the node's output type."""
        errors = []

        output_type = node.output_type
        allowed = self.CONSTRAINT_APPLICABILITY.get(output_type, [])

        for constraint in node.constraints:
            constraint_type = type(constraint).__name__
            if constraint_type not in allowed:
                errors.append(ValidationError(
                    f"Constraint {constraint_type} not applicable to {output_type}",
                    node
                ))

        return errors

    def _has_cycle(self, problem: ProblemStructure) -> bool:
        """Check if the problem DAG has a cycle using networkx."""
        G = nx.DiGraph()

        # Add all nodes
        for node in problem.bindings.values():
            G.add_node(node)

        # Add edges from inputs to operators
        for name, node in problem.bindings.items():
            if isinstance(node, OperatorNode):
                for inp in node.inputs:
                    if inp in G.nodes:
                        G.add_edge(inp, node)

        return not nx.is_directed_acyclic_graph(G)