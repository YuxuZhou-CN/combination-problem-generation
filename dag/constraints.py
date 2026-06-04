"""Constraint types from plan.md section 4."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional, Union
import random

from .expr_node import NodeType, OperatorNode, InputType, SetNode, BagNode, TupleNode,IndexedAccessNode

def _to_ordinal(n: int) -> str:
    """Convert to ordinal string (1st, 2nd, 3rd, etc.)."""
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

COMPARATOR2STR = {
    "==": "exactly",
    "<=": "at most",
    "<": "less than",
    ">=": "at least",
    ">": "greater than"
}

NONE_CONSTRAINT_OPS = {
    NodeType.BAG_DIFFERENCE,NodeType.BAG_UNION,NodeType.BAG_INTERSECTION,
    NodeType.SET_DIFFERENCE,NodeType.SET_UNION,NodeType.SET_INTERSECTION,
    NodeType.PARTITION,
}


class ComparisonOp(Enum):
    """Comparison operators for constraints."""
    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="


@dataclass
class Constraint(ABC):
    """Abstract base for all constraints (plan.md section 9.2)."""
    target: Any = None
    negated: bool = False

    def __repr__(self) -> str:
        pass

    @abstractmethod
    def is_applicable(self, node: OperatorNode) -> bool:
        """Check if this constraint can be applied to the given node."""
        pass

    @abstractmethod
    def assignParameters(self, node: OperatorNode) -> 'Constraint':
        """Return a new constraint with parameters assigned."""
        pass
    def __eq__(self, value: object) -> bool:
        return repr(self) == repr(value)
    
    @abstractmethod
    def get_parameters(self) -> dict:
        """Return a dict of parameters for this constraint."""
        pass

@dataclass
class IndexAccess:
    """Index access: groups[i] - access Tuple element at index."""
    base: Any = None
    index: int = 0


def _get_set_references(node: OperatorNode, bindings: dict) -> list:
    """
    Get a list of set references from the node's inputs and bindings.
    Returns bindings names for SetNodes or OperatorNodes that produce sets.
    """
    if bindings is None:
        bindings = {}
    set_refs = []

    for name,expr_node in bindings.items():
        if node.name == name:
            continue
        elif isinstance(expr_node, SetNode):
            set_refs.append(name)
        elif isinstance(expr_node, BagNode):
            set_refs.append(name)
        elif  expr_node.output_type == InputType.SET:
            set_refs.append(name)
        elif  expr_node.output_type == InputType.BAG:
            set_refs.append(name)
    return set_refs


# ===== Existing Constraints =====

@dataclass
class CountConstraint(Constraint):
    """target.count(element) op value."""
    element: Any = None
    op: ComparisonOp = ComparisonOp.EQ
    value: int = 0
    index: Optional[int] = None  # For indexed access like target[i].count(elem). 只对compose适用

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg. "target.count(e) >= 3" or "target[1].count(e) < 5"
        neg = "not " if self.negated else ""
        return f"{self.target.name}.count({self.element}) {self.op.value} {self.value}"

    def is_applicable(self, node: OperatorNode) -> bool:
        # BAG 集合运算（UNION/INTERSECTION/DIFFERENCE）不可约束
        application_types = {
            NodeType.CHOOSE_REPLACE,
            NodeType.CHOOSE_REPLACE_TUPLE,
        }
        only_bag_input_can_be_applicable = {
            NodeType.CHOOSE, NodeType.COMPOSE,
            NodeType.CHOOSE_TUPLE
        }
        if node.node_type in only_bag_input_can_be_applicable:
            input = node.inputs[0] if node.inputs else None
            if input.output_type == InputType.BAG:
                return True
            else: return False
        return node.node_type in application_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'CountConstraint':
        """Assign concrete element and value based on target node's possible entities and k parameter."""
        k = node.params.get('k', 5)
        self.target = node
        if node.node_type == NodeType.COMPOSE:
            self.index = random.randint(0, max(0, k - 1))
            self.target = IndexedAccessNode(parent=node, index=self.index)
            self.target.name = f"{node.name}[{self.index}]"
        entities = list(node.unique_entities)
        self.element = random.choice(entities)
        self.op = random.choice(list(ComparisonOp))
        max_count = node.get_max_count()
        self.value = random.randint(1, (max_count if max_count > 0 else 5))
        return self

    def get_parameters(self) -> dict:
        return {
            'target': self.target,
            'entity': self.element,
            'comparator': self.op.value,
            'value': self.value,
        }
@dataclass
class MemberConstraint(Constraint):
    """element in target."""
    element: Any = None
    index: Optional[int] = None  # For indexed access like element in target[i]. 只对compose适用

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg. "e in target" or "e not in target[2]"
        neg = "not " if self.negated else ""
        return f"{self.element} {neg}in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        application_types = {
            NodeType.CHOOSE, NodeType.CHOOSE_REPLACE,
            NodeType.CHOOSE_TUPLE,
            NodeType.COMPOSE,
        }
        return node.node_type in application_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'MemberConstraint':
        """Assign concrete element from target node's possible entities."""
        self.target = node
        if node.node_type in [NodeType.COMPOSE]:
            k = node.params.get('k', 5)
            self.index = random.randint(0, max(0, k - 1))
            self.target = IndexedAccessNode(parent=node, index=self.index)   
            self.target.name = f"{node.name}[{self.index}]"
        if self.element is None:
            entities = list(node.unique_entities)
            if entities:
                self.element = random.choice(entities)
        if self.element is None:
            return None
        return self

    def get_parameters(self) -> dict:
        positive = "" if not self.negated else "not "
        return {
            'target': self.target,
            'positive': positive,
            'entity': self.element,
        }


@dataclass
class CardinalityConstraint(Constraint):
    """|target| op value, or |target[i]| op value for indexed access."""
    op: ComparisonOp = ComparisonOp.EQ
    value: int = 0
    index: Optional[int] = None

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # e,g. "|compose[0]| >= 3" or "|set| < 5"
        return f"|{self.target.name}| {self.op.value} {self.value}"

    def is_applicable(self, node: OperatorNode) -> bool:
        container_types = {
            NodeType.INDEXED_ACCESS, NodeType.COMPOSE
        }
        return node.node_type in container_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'CardinalityConstraint':
        """Assign concrete cardinality based on node's k param or source size, mutates self."""
        if self.op == ComparisonOp.EQ:
            self.op = random.choice([
                ComparisonOp.EQ, ComparisonOp.GE, ComparisonOp.LE, ComparisonOp.GT, ComparisonOp.LT
            ])
        k = node.params.get('k')
        self.target = node
        if node.node_type == NodeType.COMPOSE:
            self.index = random.randint(0, max(0, k - 1))
            self.target = IndexedAccessNode(parent=node, index=self.index)
            self.target.name = f"{node.name}[{self.index}]"
        else:
            self.index = None
        if k is None and node.inputs:
            first_input = node.inputs[0]
            elems = getattr(first_input, 'elements', None)
            contents = getattr(first_input, 'contents', None)
            if elems is not None:
                k = len(elems)
            elif contents is not None:
                k = sum(contents.values())
            else:
                k = 5
        k = k or 5
        if self.value <= 0:
            self.value = random.randint(1, max(1, k - 1))
        return self

    def get_parameters(self) -> dict:
        return {
            'target': self.target,
            'comparator': self.op.value,
            'value': self.value,
            'index': self.index + 1,
        }

@dataclass
class NextToConstraint(Constraint):
    """next_to(a, b) in target."""
    a: Any = None
    b: Any = None
    negated: bool = False

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        positive = "" if not self.negated else "not "
        return f"next_to({self.a}, {self.b}) {positive}in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.SEQUENCE, NodeType.CIRCLE,
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'NextToConstraint':
        """Assign a and b to two different entities from the node."""
        entities = list(node.unique_entities)
        if len(entities) < 2:
            return None
        self.a, self.b = random.sample(entities, 2)
        self.negated = random.choice([True, False])
        self.target = node
        return self

    def get_parameters(self) -> dict:
        positive = "positive" if not self.negated else "negative"
        return {
            'entity1': self.a,
            'entity2': self.b,
            'target': self.target,
            'positive': positive,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        tmpl_dict = template
        key_name = 'negative' if self.negated else 'positive'
        tmpl = tmpl_dict.get(key_name, '')
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['target'] = set_names.get(params['target'].name, params['target'].name)
        return tmpl.format(**params)


@dataclass
class TogetherConstraint(Constraint):
    """together(group) in target."""
    group: list = field(default_factory=list)
    negated: bool = False
    target: Any = None

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        positive = "" if not self.negated else "not "
        return f"together(set({', '.join(self.group)})) {positive}in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.SEQUENCE, NodeType.CIRCLE,
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'TogetherConstraint':
        """Assign concrete group from target node's possible entities."""
        if not self.group:
            entities = list(node.unique_entities)
            if len(entities) >= 2:
                group_size = random.randint(2, min(3, len(entities)))
                self.group = random.sample(entities, group_size)
            else:
                return None
        self.negated = random.choice([True, False])
        self.target = node
        return self

    def get_parameters(self) -> dict:
        positive = "positive" if not self.negated else "negative"
        return {
            'group': self.group,
            'target': self.target,
            'positive': positive,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        tmpl_dict = template
        key_name = 'negative' if self.negated else 'positive'
        tmpl = tmpl_dict.get(key_name, '')
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['target'] = set_names.get(params['target'].name, params['target'].name)
        return tmpl.format(**params)

@dataclass
class LessThanConstraint(Constraint):
    """a < b in target — a appears before b in tuple."""
    a: Any = None
    b: Any = None
    negated: bool = False

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        positive = "" if not self.negated else "not "
        return f"{self.a} < {self.b} {positive}in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.SEQUENCE,NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'LessThanConstraint':
        """Assign concrete elements a and b from target node's possible entities."""
        entities = list(node.unique_entities)
        if len(entities) < 2:
            return None
        self.a, self.b = random.sample(entities, 2)
        self.target = node
        self.negated = random.choice([True, False])
        return self

    def get_parameters(self) -> dict:
        positive = 'negative' if self.negated else 'positive'
        return {
            'entity1': self.a,
            'entity2': self.b,
            'target': self.target,
            'positive': positive,
        }


def _get_node_size(node: ExprNode) -> int:
    """Get the size of a node (number of elements in output)."""
    if isinstance(node, OperatorNode) and 'k' in node.params:
        return node.params['k']
    return len(node.unique_entities)


@dataclass
class SubsetConstraint(Constraint):
    """A subset B."""
    a: Any = None  # str (binding name) or list (fallback entity names)
    target: Any = None
    index: Optional[int] = None  # For subset constraints on compose[i]

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        if isinstance(self.a, str):
            return f"{self.a} subset {self.target.name}"
        else:
            if self.target.output_type == InputType.BAG:
                return f"supp({self.target.name}) subset set(" + str(",".join(self.a)) + ")"
            return f"{self.target.name} subset set(" + str(",".join(self.a)) + ")"

    def is_applicable(self, node: OperatorNode) -> bool:
        set_types = {
            NodeType.COMPOSE, NodeType.CHOOSE, NodeType.CHOOSE_REPLACE
        }
        return node.node_type in set_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'SubsetConstraint':
        """Assign concrete sets A and B. Prefer binding references with blood relationship."""
        if bindings is None:
            bindings = {}

        self.target = node
        k = node.params.get('k', 5)

        if node.node_type == NodeType.COMPOSE:
            self.index = random.randint(0, max(0, k - 1))
            self.target = IndexedAccessNode(parent=node, index=self.index)
            self.target.name = f"{node.name}[{self.index}]"
        else:
            self.index = None

        target_entities = self.target.unique_entities
        if not target_entities or len(target_entities) < 2:
            return None

        # Get target size for size validation
        target_size = _get_node_size(self.target)

        # Try to find candidates from bindings with blood relationship and size validation
        candidates = _get_set_references(node,bindings)

        if candidates:
            self.a = random.choice(candidates)
            return self

        # Fallback: dynamically construct a random subset
        # For A ⊆ B to be possible, we need |A| <= |B|, i.e., sample_size <= target_size
        # But since self.a is the subset (A) and self.target is the superset (B),
        # we need target_size <= sample_size for the constraint to be satisfiable
        entities = list(target_entities)
        if target_size > len(entities):
            # Cannot construct a set large enough to contain target
            return None
        sample_size = random.randint(target_size, max(target_size, min(target_size, len(entities))))
        sample = random.sample(entities, sample_size)
        self.a = sorted(sample)
        return self

    def get_parameters(self) -> dict:
        if isinstance(self.a, str):
            first_set = self.a
        else:
            first_set = f"set({','.join(self.a)})"
        return {
            'first_set': first_set,
            'second_set': self.target.name if hasattr(self.target, 'name') else self.target,
        }




@dataclass
class DisjointConstraint(Constraint):
    """A disjoint B."""
    a: Any = None  # str (binding name) or list (fallback entity names)
    target: Any = None
    index: Optional[int] = None  # For disjoint constraints on compose[i]
    a_needs_supp: bool = False  # Whether a is a bag type needing supp() conversion

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        
        target_str = self.target.name
        if getattr(self, 'node_needs_supp', False):
            target_str = f"supp({target_str})"
            
        # Format a: if binding name use directly, otherwise wrap in set()
        if isinstance(self.a, str):
            a_str = self.a
            if getattr(self, 'a_needs_supp', False):
                a_str = f"supp({a_str})"
        else:
            a_str = "set(" + str(",".join(self.a)) + ")"

        return f"{target_str} disjoint {a_str}"

    def is_applicable(self, node: OperatorNode) -> bool:
        set_types = {
            NodeType.CHOOSE, NodeType.COMPOSE, NodeType.CHOOSE_REPLACE
        }
        return node.node_type in set_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'DisjointConstraint':
        """Assign concrete sets A and B as disjoint subsets of target node's entities."""
        if bindings is None:
            bindings = {}

        self.target = node
        k = node.params.get('k', 5)

        if node.node_type == NodeType.COMPOSE:
            self.index = random.randint(0, max(0, k - 1))
            self.target = IndexedAccessNode(parent=node, index=self.index)
            self.target.name = f"{node.name}[{self.index}]"
        else:
            self.index = None

        target_entities = self.target.unique_entities
        if not target_entities or len(target_entities) < 4:
            return None

        # Try to find candidates from bindings with blood relationship
        candidates = _get_set_references(node, bindings)

        if candidates:
            chosen_name = random.choice(candidates)
            self.a = chosen_name
            # Check if chosen binding needs supp() conversion (is a bag type or choose_replace)
            self.a_needs_supp = False
            self.node_needs_supp = False
            if chosen_name in bindings:
                expr = bindings[chosen_name]
                if hasattr(expr, 'output_type') and hasattr(self.target, 'output_type'):
                    if expr.output_type != self.target.output_type:
                        if expr.output_type == InputType.BAG:
                            self.a_needs_supp = True
                        if self.target.output_type == InputType.BAG:
                            self.node_needs_supp = True
            return self

        # Fallback: dynamically construct two disjoint subsets
        entities = list(target_entities)
        sample_size = random.randint(1, max(2, (len(entities) - 1) // 2))
        sample = random.sample(entities, sample_size)
        self.a = sorted(sample)
        self.a_needs_supp = False
        return self

    def get_parameters(self) -> dict:
        if isinstance(self.a, str):
            first_set = self.a
        else:
            first_set = f"set({','.join(self.a)})"
        return {
            'first_set': first_set,
            'second_set': self.target.name if hasattr(self.target, 'name') else self.target,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        params = self.get_parameters()
        if hasattr(params.get('second_set'), 'name'):
            params['second_set'] = set_names.get(params['second_set'].name, params['second_set'].name)
        return template.format(**params)


@dataclass
class CompositeConstraint(Constraint):
    """(c1) and/or/not (c2)."""
    constraints: List = field(default_factory=list)
    operator: str = 'and'

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg: "not (c1 and c2)" or "(c1 or c2)"
        if self.operator == 'not':
            return f"not ({self.constraints[0]})"
        ops = f" {self.operator} ".join(str(c) for c in self.constraints)
        return f"({ops})"

    def is_applicable(self, node: OperatorNode) -> bool:
        return any(c.is_applicable(node) for c in self.constraints)

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'CompositeConstraint':
        """Recursively assign parameters to sub-constraints, mutates self."""
        for c in self.constraints:
            if hasattr(c, 'assignParameters'):
                c.assignParameters(node)
        self.target = node
        return self

    def get_parameters(self) -> dict:
        sub_params = [c.get_parameters() for c in self.constraints if hasattr(c, 'get_parameters')]
        return {
            'operator': self.operator,
            'sub_constraints': sub_params,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        sub_results = []
        for c in self.constraints:
            try:
                sub_results.append(c.fromat_template(template, set_names))
            except (KeyError, AttributeError):
                # Sub-constraint can't format with this template, skip it
                pass
        if not sub_results:
            return ""
        if self.operator == 'not':
            return f"not ({sub_results[0]})"
        return f"({' ' + self.operator + ' '.join(sub_results)})"


@dataclass
class QuantifiedConstraint(Constraint):
    """forall/exists part in target where condition."""
    quantifier: str = 'for'
    part_var: str = 'part'
    op: ComparisonOp = ComparisonOp.EQ
    value: Any = None

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg: "|part| >= 1 for part in target "]
        body = f"|{self.part_var}| {self.op.value} {self.value}"
        return f"{body} {self.quantifier} {self.part_var} in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        container_types = {
            NodeType.PARTITION,
        }
        return node.node_type in container_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'QuantifiedConstraint':
        """Assign quantifier and body based on node, mutates self."""
        self.value = random.randint(1, 3)
        self.op = random.choice(list(ComparisonOp))
        self.target = node
        return self

    def get_parameters(self) -> dict:
        
        return {
            "target": self.target,
            "comparator": self.op.value,
            "value": self.value,
        }
@dataclass
class IndexMemberConstraint(Constraint):
    """obj[i] in S — element at index i belongs to set S."""
    index: int = 0
    set_target: Any = None

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg. "obj[2] in S"
        return f"{self.target.name}[{self.index}] in {self.set_target}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.CHOOSE_TUPLE
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'IndexMemberConstraint':
        """Assign concrete index and set from node info, mutates self."""
        k = node.params.get('k', 5)
        if self.index <= 0:
            self.index = random.randint(0, max(0, k - 1))
        if not self.set_target:
            set_refs = _get_set_references(node, bindings)
            if set_refs:
                self.set_target = random.choice(set_refs)
            else:
                return None
        self.target = node
        return self

    def get_parameters(self) -> dict:
        positive = "" if not self.negated else "not "
        return {
            'target': self.target,
            'positive': positive,
            'container': self.set_target,
            'index': self.index+1,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['target_tuple'] = params['target'].name
        if 'index' in params and params['index'] is not None:
            params['index'] = _to_ordinal(params['index'] + 1)
        return template.format(**params)

@dataclass
class IndexEqualMemberConstraint(Constraint):
    """obj[i] == e1 or obj[i] != e2 — element at index i is equal to or not equal to a specific element."""
    index: int = 0
    entity_target: Any = None
    positive: bool = True
    eq: ComparisonOp = ComparisonOp.EQ


    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg. "obj[2] == e1"
        return f"{self.target.name}[{self.index}] {self.eq.value} {self.entity_target}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.CHOOSE_TUPLE, NodeType.CHOOSE_REPLACE_TUPLE,NodeType.TUPLE
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'IndexEqualMemberConstraint':
        """Assign concrete index and set from node info, mutates self."""
        unique_entities = list(node.unique_entities)
        k = node.params.get('k', len(unique_entities))
        self.index = random.randint(0, max(0, k - 1))
        self.entity_target = None
        self.positive = random.choice([True, False])
        if self.positive:
            self.eq = ComparisonOp.EQ
        else:
            self.eq = ComparisonOp.NE
        if unique_entities:
            self.entity_target = random.choice(unique_entities)
        self.target = node
        return self

    def get_parameters(self) -> dict:
        positive = "" if self.positive else "not "
        return {
            'target': self.target,
            'index': self.index + 1,
            'positive': positive,
            'entity': self.entity_target,
        }



@dataclass
class TupleDedupCountSizeConstraint(Constraint):
    """target.dedup_count(S) op value — count of distinct elements in S within target."""
    set_target: Any = None
    op: ComparisonOp = ComparisonOp.EQ
    value: int = 0

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg. "target.dedup_count(S) == 3"
        return f"{self.target.name}.dedup_count({self.set_target}) {self.op.value} {self.value}"

    def is_applicable(self, node: OperatorNode) -> bool:
        bag_tuple_types = {
            NodeType.CHOOSE_REPLACE_TUPLE,
        }
        return node.node_type in bag_tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None, ) -> 'TupleDedupCountSizeConstraint':
        """Assign concrete set and value for dedup_count constraint."""
        if not self.set_target:
            set_refs = _get_set_references(node, bindings)
            if set_refs:
                # Pick a random set from references
                self.set_target = random.choice(set_refs)
            else:
                return None
        if self.op == ComparisonOp.EQ:
            self.op = random.choice(list(ComparisonOp))
        if self.value <= 0:
            # Calculate set_target size from bindings
            set_target_size = 1
            if bindings and self.set_target in bindings:
                target_expr = bindings[self.set_target]
                if hasattr(target_expr, 'entitys') and target_expr.entitys:
                    if isinstance(target_expr.entitys, (set, frozenset)):
                        set_target_size = len(target_expr.entitys)
                    elif isinstance(target_expr.entitys, dict):
                        set_target_size = len(target_expr.entitys)
            max_dedup = node.get_max_dedup_count(set_target_size)
            self.value = random.randint(0, max(1, max_dedup))
        self.target = node
        return self

    def get_parameters(self) -> dict:
        return {
            'target': self.target,
            'count_obj': self.set_target,
            'comparator': self.op.value,
            'param': self.value,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['tuple'] = set_names.get(params['target'].name, params['target'].name)
        if 'comparator' in params:
            params['comparator'] = COMPARATOR2STR.get(params['comparator'], params['comparator'])
        return template.format(**params)


@dataclass
class NonEmptyConstraint(Constraint):
    """|target| > 0 — target is non-empty."""
    index: Optional[int] = None  # For non-empty constraints on compose[i]

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        # eg: "|target| > 0"
        return f"|{self.target.name}| > 0"

    def is_applicable(self, node: OperatorNode) -> bool:
        container_types = {NodeType.COMPOSE}
        none_k_param = node.params.get('k') is None
        if node.node_type == NodeType.COMPOSE and not none_k_param:
            return True
        return False

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'NonEmptyConstraint':
        """Non-empty is a fixed constraint — no parameters needed, mutates self."""
        if node.node_type in {NodeType.COMPOSE,}:
            k = node.params.get('k', 5)
            self.index = random.randint(0, max(0, k - 1))
        else:
            self.index = None
        self.target = IndexedAccessNode(parent=node, index=self.index) if self.index is not None else node
        if isinstance(self.target, IndexedAccessNode):
            self.target.name = f"{node.name}[{self.index}]"
        return self

    def get_parameters(self) -> dict:
        return {
            'target': self.target,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['target'] = set_names.get(params['target'].name, params['target'].name)
        return template.format(**params)


@dataclass
class EqualityConstraint(Constraint):
    """A == B or A != B — structural equality of two expressions."""
    left: Any = None
    right: Any = None
    op: ComparisonOp = ComparisonOp.EQ
    negated: bool = False

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        return f"{self.left} {self.op.value} {self.right}"

    def is_applicable(self, node: OperatorNode) -> bool:
        # Applicable to all container types
        container_types = {
            NodeType.SET, NodeType.BAG, NodeType.TUPLE,
            NodeType.COMPOSE, NodeType.PARTITION,
            NodeType.CHOOSE, NodeType.CHOOSE_REPLACE,
            NodeType.CHOOSE_TUPLE, NodeType.CHOOSE_REPLACE_TUPLE,
            NodeType.SEQUENCE, NodeType.CIRCLE,
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in container_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'EqualityConstraint'| None:
        """Assign left and right to two different named bindings."""
        if bindings is None:
            bindings = {}
        # Get all binding names that are container types
        container_types = {
            NodeType.SET, NodeType.BAG, NodeType.TUPLE,
            NodeType.COMPOSE, NodeType.PARTITION,
            NodeType.CHOOSE, NodeType.CHOOSE_REPLACE,
            NodeType.CHOOSE_TUPLE, NodeType.CHOOSE_REPLACE_TUPLE,
            NodeType.SEQUENCE, NodeType.CIRCLE,
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        candidates = [
            (name, expr) for name, expr in bindings.items()
            if isinstance(expr, OperatorNode) and expr.node_type in container_types
        ]
        if len(candidates) < 2:
            return None
        selected = random.sample(candidates, 2)
        self.left = selected[0][0]
        self.right = selected[1][0]
        self.op = ComparisonOp.EQ
        self.target = node
        return self

    def get_parameters(self) -> dict:
        return {
            'left_name': self.left,
            'right_name': self.right,
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        params = self.get_parameters()
        params['left_name'] = set_names.get(params['left_name'], params['left_name'])
        params['right_name'] = set_names.get(params['right_name'], params['right_name'])
        return template.format(**params)


@dataclass
class PredecessorConstraint(Constraint):
    """(a, b) in s — a immediately precedes b in a tuple (a at position i, b at i+1)."""
    a: Any = None
    b: Any = None
    negated: bool = False

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        neg = "not " if self.negated else ""
        return f"({self.a}, {self.b}) {neg}in {self.target.name}"

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.SEQUENCE,
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in tuple_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'PredecessorConstraint':
        """Assign a and b to two different entities from the node."""
        entities = list(node.unique_entities)
        if len(entities) < 2:
            return None
        self.a, self.b = random.sample(entities, 2)
        self.target = node
        return self

    def get_parameters(self) -> dict:
        return {
            'entity1': self.a,
            'entity2': self.b,
            'target': self.target,
            'positive': "positive" if not self.negated else "negative",
        }

    def fromat_template(self, template: str, set_names: dict) -> str:
        tmpl_dict = template
        key_name = 'negative' if self.negated else 'positive'
        tmpl = tmpl_dict.get(key_name, '')
        params = self.get_parameters()
        if hasattr(params.get('target'), 'name'):
            params['target'] = set_names.get(params['target'].name, params['target'].name)
        return tmpl.format(**params)


@dataclass
class LinearCardinalityConstraint(Constraint):
    """|A + B| op n — linear cardinality of two bindings."""
    left: Any = None
    right: Any = None
    op: ComparisonOp = ComparisonOp.EQ
    value: int = 0
    negated: bool = False
    indexs: Optional[tuple] = None  # For constraints on compose[i] and compose[j]

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        return f"|{self.left.name}| + |{self.right.name}| {self.op.value} {self.value}"

    def is_applicable(self, node: OperatorNode) -> bool:
        container_types = {
            NodeType.COMPOSE
        }
        return node.node_type in container_types

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'LinearCardinalityConstraint':
        """Assign left and right to two different named bindings with container types."""
        if bindings is None:
            bindings = {}
        container_types = {
            NodeType.SET, NodeType.BAG,
            NodeType.COMPOSE,
            NodeType.CHOOSE, NodeType.CHOOSE_REPLACE,
        }
        import random
        all_candidates = [
            (name, expr) for name, expr in bindings.items() if expr.node_type not in [NodeType.PARTITION,NodeType.COMPOSE, ]
        ]
        operat_candidates = [
            (name, expr) for name, expr in all_candidates
            if isinstance(expr, OperatorNode) and expr.node_type not in NONE_CONSTRAINT_OPS
        ]
        if len(operat_candidates) < 2 or len(all_candidates) < 2:
            return None
        else:
            self.left = random.choice(all_candidates)[1]
            self.right = random.choice(operat_candidates)[1]
        entitys = list(self.left.unique_entities.union(self.right.unique_entities))
        self.op = random.choice(list(ComparisonOp))
        self.value = random.randint(1, max(1, len(entitys)))
        self.target = node
        return self

    def get_parameters(self) -> dict:
        return {
            'left': self.left,
            'right': self.right,
            'comparator': self.op.value,
            'value': self.value,
        }

@dataclass
class SequenceCountConstraint(Constraint):
    """Count occurrences of entity relationships in sequences."""
    target: Any = None
    count_type: str = "next_to"  # "next_to" | "predecessor" | "less_than"
    entity1: Any = None
    entity2: Any = None
    op: ComparisonOp = ComparisonOp.EQ
    value: int = 0

    def __repr__(self) -> str:
        if self.target == None:
            return ""
        if self.count_type == "next_to":
            out_str = f"{self.target.name}.count(next_to({self.entity1}, {self.entity2})) {self.op.value} {self.value}"
        elif self.count_type == "predecessor":
            out_str = f"{self.target.name}.count(({self.entity1}, {self.entity2})) {self.op.value} {self.value}"
        elif self.count_type == "less_than":    
            out_str = f"{self.target.name}.count(({self.entity1} < {self.entity2})) {self.op.value} {self.value}"
        return out_str

    def is_applicable(self, node: OperatorNode) -> bool:
        tuple_types = {
            NodeType.CHOOSE_REPLACE_SEQUENCE,
        }
        return node.node_type in tuple_types

    def _count_next_to(self, sequence: list) -> int:
        """Count adjacent pairs where entity1 and entity2 are next to each other (either direction)."""
        count = 0
        for i in range(len(sequence) - 1):
            pair = {sequence[i], sequence[i + 1]}
            if self.entity1 in pair and self.entity2 in pair:
                count += 1
        return count

    def _count_predecessor(self, sequence: list) -> int:
        """Count adjacent pairs where entity1 is immediately before entity2."""
        count = 0
        for i in range(len(sequence) - 1):
            if sequence[i] == self.entity1 and sequence[i + 1] == self.entity2:
                count += 1
        return count

    def _count_less_than(self, sequence: list) -> int:
        """Count all position pairs (i<j) where entity1 appears before entity2."""
        count = 0
        for i in range(len(sequence)):
            for j in range(i + 1, len(sequence)):
                if sequence[i] == self.entity1 and sequence[j] == self.entity2:
                    count += 1
        return count

    def assignParameters(self, node: OperatorNode, bindings: dict = None) -> 'SequenceCountConstraint':
        entities = list(node.unique_entities)
        if len(entities) < 2:
            return None
        self.entity1 = random.sample(entities, 1)[0]
        self.entity2 = random.sample(entities, 1)[0]
        self.count_type = random.choice(["next_to", "predecessor", "less_than"])
        self.op = random.choice(list(ComparisonOp))
        k = len(entities)
        if self.count_type == "less_than":
            max_count = k * (k - 1) // 2
        else:
            max_count = k - 1
        self.value = random.randint(0, max(0, max_count))
        self.target = node
        return self

    def get_parameters(self) -> dict:
        return {
            'target': self.target,
            'count_type': self.count_type,
            'entity1': self.entity1,
            'entity2': self.entity2,
            'comparator': self.op.value,
            'value': self.value,
        }


ALL_CONSTRAINTS = [
    CardinalityConstraint(), CountConstraint(), MemberConstraint(),
    NextToConstraint(), TogetherConstraint(),
    SubsetConstraint(), DisjointConstraint(),
    CompositeConstraint(), QuantifiedConstraint(),
    LessThanConstraint(), IndexMemberConstraint(),
    TupleDedupCountSizeConstraint(), NonEmptyConstraint(),
    PredecessorConstraint(),
    LinearCardinalityConstraint(),IndexEqualMemberConstraint(),
    SequenceCountConstraint(),
]
