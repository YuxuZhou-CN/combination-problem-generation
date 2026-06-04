"""DAGCodeGenerator - topological sort and Cofola DSL serialization."""

from __future__ import annotations
from typing import Dict, Set

from dag.expr_node import ExprNode, SetNode, BagNode, TupleNode, OperatorNode, NodeType, IndexedAccessNode
from dag.problem_structure import ProblemStructure



class DAGCodeGenerator:
    """
    Generates Cofola DSL code from ProblemStructure.

    Performs topological sort to ensure dependencies are defined before use.
    """

    def __init__(self):
        self._name_map: Dict[ExprNode, str] = {}

    def generate(self, problem: ProblemStructure) -> str:
        """
        Generate Cofola DSL code from ProblemStructure.

        Uses topological sort to order definitions correctly.
        """
        # Build name mapping from bindings
        self._name_map = {node: name for name, node in problem.bindings.items()}

        # Topological sort using Kahn's algorithm
        ordered = self._topological_sort(problem)

        # Generate code lines
        lines = []
        constraint_lines = []
        for node in ordered:
            code = self._node_to_code(node)
            if code:
                lines.append(code)
                # Add constraints attached to this node
                for constraint in node.constraints:
                    constraint_lines.append(str(constraint))

        # Add global constraints
        for constraint in problem.global_constraints:
            constraint_lines.append(str(constraint))

        lines.extend(constraint_lines)
        return '\n'.join(lines)

    def _topological_sort(self, problem: ProblemStructure) -> list[ExprNode]:
        """Topological sort of nodes via Kahn's algorithm."""
        from typing import Dict, List

        # Build adjacency and in-degree
        in_degree: Dict[ExprNode, int] = {node: 0 for node in problem.bindings.values()}
        dependents: Dict[ExprNode, List[ExprNode]] = {node: [] for node in problem.bindings.values()}

        for node in problem.bindings.values():
            if isinstance(node, OperatorNode):
                for inp in node.inputs:
                    if inp in in_degree:
                        in_degree[node] += 1
                        dependents[inp].append(node)
            elif isinstance(node, IndexedAccessNode):
                parent = node.parent
                if parent in in_degree:
                    in_degree[node] += 1
                    dependents[parent].append(node)
            elif isinstance(node, (SetNode, BagNode)):
                for inp in node.inputs or []:
                    if inp in in_degree:
                        in_degree[node] += 1
                        dependents[inp].append(node)

        # Start with nodes that have no dependencies
        queue = [n for n, d in in_degree.items() if d == 0]
        ordered = []

        while queue:
            node = queue.pop(0)
            ordered.append(node)

            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        return ordered

    def _get_name(self, node: ExprNode) -> str:
        """Get binding name for a node."""
        if node in self._name_map:
            return self._name_map[node]
        return f"node_{id(node)}"

    def _node_to_code(self, node: ExprNode) -> str:
        """Convert a node to Cofola DSL code."""
        name = self._get_name(node)

        if isinstance(node, SetNode):
            if node.inputs:
                # Derived set: use operator to determine the operation symbol
                inp_names = [self._get_name(inp) for inp in node.inputs]
                if node.operator == NodeType.SET_UNION:
                    op_symbol = '+'
                elif node.operator == NodeType.SET_INTERSECTION:
                    op_symbol = '&'
                elif node.operator == NodeType.SET_DIFFERENCE:
                    op_symbol = '-'
                else:
                    op_symbol = '+'  # default
                return f"{name} = {self._fmt(node.inputs[0])} {op_symbol} {inp_names[1]}"
            if isinstance(node.entitys, range):
                return f"{name} = set({node.entitys.start}...{node.entitys.stop - 1})"
            else:
                entitys = ', '.join(sorted(node.entitys))
                return f"{name} = set({entitys})"

        elif isinstance(node, BagNode):
            if node.inputs:
                # Derived bag: use operator to determine the operation symbol
                inp_names = [self._get_name(inp) for inp in node.inputs]
                if node.operator == NodeType.BAG_UNION:
                    op_symbol = '+'
                elif node.operator == NodeType.BAG_INTERSECTION:
                    op_symbol = '&'
                elif node.operator == NodeType.BAG_DIFFERENCE:
                    op_symbol = '-'
                else:
                    op_symbol = '+'  # default
                return f"{name} = {self._fmt(node.inputs[0])} {op_symbol} {inp_names[1]}"
            parts = [f"{k}: {v}" for k, v in sorted(node.entitys.items())]
            return f"{name} = bag({', '.join(parts)})"

        elif isinstance(node, TupleNode):
            if node.inputs:
                # Derived tuple: this shouldn't normally happen but handle it
                inp_names = [self._get_name(inp) for inp in node.inputs]
                return f"{name} = tuple({', '.join(inp_names)})"
            entitys = ', '.join(str(e) for e in node.entitys)
            return f"{name} = tuple({entitys})"

        elif isinstance(node, OperatorNode):
            return self._operator_to_code(node, name)

        elif isinstance(node, IndexedAccessNode):
            # IndexedAccessNode is inlined when used as input to operators,
            # not generated as a separate binding
            return ""

        return ""

    def _operator_to_code(self, node: OperatorNode, name: str) -> str:
        """Convert an OperatorNode to Cofola DSL."""
        inp_names = [self._get_name(inp) for inp in node.inputs]

        if node.operator == NodeType.CHOOSE:
            k = node.params.get('k', 0)
            return f"{name} = choose({self._fmt(node.inputs[0])}, {k})"
        if node.operator == NodeType.TUPLE:
            return f"{name} = tuple({self._fmt(node.inputs[0])})"

        elif node.operator == NodeType.CHOOSE_REPLACE:
            k = node.params.get('k', 0)
            return f"{name} = choose_replace({self._fmt(node.inputs[0])}, {k})"

        elif node.operator == NodeType.CHOOSE_TUPLE:
            k = node.params.get('k', 0)
            return f"{name} = choose_tuple({self._fmt(node.inputs[0])}, {k})"

        elif node.operator == NodeType.CHOOSE_REPLACE_TUPLE:
            k = node.params.get('k', 0)
            return f"{name} = choose_replace_tuple({self._fmt(node.inputs[0])}, {k})"

        elif node.operator == NodeType.SEQUENCE:
            return f"{name} = sequence({self._fmt(node.inputs[0])})"

        elif node.operator == NodeType.CIRCLE:
            refl = node.params.get('reflection', False)
            refl_str = ", reflection=True" if refl else ""
            return f"{name} = circle({self._fmt(node.inputs[0])}{refl_str})"

        elif node.operator == NodeType.COMPOSE:
            k = node.params.get('k', 0)
            return f"{name} = compose({self._fmt(node.inputs[0])}, {k})"

        elif node.operator == NodeType.PARTITION:
            k = node.params.get('k', 0)
            return f"{name} = partition({self._fmt(node.inputs[0])}, {k})"

        elif node.operator == NodeType.SET_UNION:
            return f"{name} = {self._fmt(node.inputs[0])} + {self._fmt(node.inputs[1])}"

        elif node.operator == NodeType.SET_INTERSECTION:
            return f"{name} = {self._fmt(node.inputs[0])} & {self._fmt(node.inputs[1])}"

        elif node.operator == NodeType.SET_DIFFERENCE:
            return f"{name} = {self._fmt(node.inputs[0])} - {self._fmt(node.inputs[1])}"

        elif node.operator == NodeType.BAG_UNION:
            return f"{name} = {self._fmt(node.inputs[0])} + {self._fmt(node.inputs[1])}"

        elif node.operator == NodeType.BAG_INTERSECTION:
            return f"{name} = {self._fmt(node.inputs[0])} & {self._fmt(node.inputs[1])}"

        elif node.operator == NodeType.BAG_DIFFERENCE:
            return f"{name} = {self._fmt(node.inputs[0])} - {self._fmt(node.inputs[1])}"
        elif node.operator == NodeType.CHOOSE_REPLACE_SEQUENCE:
            k = node.params.get('k', 0)
            return f"{name} = choose_replace_sequence({self._fmt(node.inputs[0])}, {k})"
        return f"{name} = <unknown operator {node.operator}>"
    def _fmt(self,inp):
        if isinstance(inp, IndexedAccessNode):
            return f"{self._get_name(inp.parent)}[{inp.index}]"
        return self._get_name(inp)
    # Mapping from ComparisonOp to DSL symbols
    _OP_SYMBOLS = {
        'EQ': '==',
        'NE': '!=',
        'GT': '>',
        'GE': '>=',
        'LT': '<',
        'LE': '<=',
    }