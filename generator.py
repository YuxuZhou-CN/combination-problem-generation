"""DAG-based combinatorial problem generator."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Type, Tuple
import random
from dag.expr_node import (
    ExprNode, SetNode, BagNode, TupleNode, OperatorNode, IndexedAccessNode,
    NodeType, InputType
)
from dag.operator_registry import OPERATOR_SIGNATURES, get_signature, get_output_type
from dag.dag_builder import DAGBuilder
from dag.problem_structure import ProblemStructure
from properties import PropertyTracker, PropertyType
from samplerule import RuleSamplingPolicy
from cofola.solver import solve
from cofola.parser.parser import parse
from dag.constraints import *
from loggers import get_logger
from dag.constraints import ALL_CONSTRAINTS
logger = get_logger(__name__)

class CombinationProblemGenerator:
    def __init__(
        self,
        entity_count: int = 5,  # Number of entities
        entity_multiplicity_range: Optional[Tuple[int, int]] = None, # Entity multiplicity range, e.g. (2, 4) means entities appear 2 to 4 times
        initial_set_bag_count: int = 3,         # Number of initially generated sets/bags
        allowed_operators: Optional[List[NodeType]] = None, # List of allowed operators, e.g. [NodeType.CHOOSE, NodeType.SEQUENCE]
        operator_count: int = 3, # Number of operators to generate
        allowed_constraints: Optional[List[Constraint]] = None, # List of allowed constraint types, e.g. ['cardinality', 'member']
        constraint_count: int = 2,  # Number of constraints to generate
        random_seed: Optional[int] = None, # Random seed for reproducibility
        depth: int = None,  # Parameter for validating problem DAG depth
        operator_chain: Optional[List[NodeType]] = None,  # Operator chain sequence, auto-sampled if None
    ):
        self.entity_count = entity_count
        self.entity_multiplicity_range = entity_multiplicity_range
        self.initial_set_bag_count = initial_set_bag_count
        self.allowed_operators = allowed_operators or list(OPERATOR_SIGNATURES.keys())
        self.operator_count = operator_count
        self.allowed_constraints = allowed_constraints or ALL_CONSTRAINTS
        self.constraint_count = constraint_count

        self.entitys = []  # Track generated entity names for reference in constraints and operations
        self.depth = depth
        self.operator_chain = operator_chain
        self._chain_index = 0  # Track current position in chain during generation

        # Config conflict detection
        if self.depth is not None and self.operator_count < self.depth:
            raise ValueError(f"Config conflict: operator_count({self.operator_count}) < depth({self.depth})")

        # Validate operator_chain if provided
        if self.operator_chain is not None:
            if self.depth is not None and len(self.operator_chain) != self.depth:
                raise ValueError(f"operator_chain length ({len(self.operator_chain)}) must equal depth ({self.depth})")
            for op in self.operator_chain:
                if op not in self.allowed_operators:
                    raise ValueError(f"operator {op.name} not in allowed_operators")

        if random_seed is not None:
            random.seed(random_seed)

        self.builder = DAGBuilder()
        # Pool: maps InputType to list of available ExprNode
        self.available_pool: Dict[InputType, List[ExprNode]] = {
            InputType.SET: [],
            InputType.BAG: [],
        }
        self.operator_nodes: List[OperatorNode] = []
        self.property_tracker: Optional[PropertyTracker] = None
        self.policy = RuleSamplingPolicy()

    def _compute_current_max_depth(self) -> int:
        """Compute the maximum depth of current generation result."""
        if not self.operator_nodes:
            return 0
        return max(node.depth for node in self.operator_nodes)

    def _enumerate_compatible_chains(self) -> List[List[NodeType]]:
        """Enumerate all compatible operator chains of length depth.

        A chain is compatible if each operator accepts the input type produced
        by the previous operator in the chain (or Set/Bag for the first operator).
        """
        if self.depth is None or self.depth <= 0:
            return []

        chains: List[List[NodeType]] = []

        def build_chain(current_depth: int, current_input_type: InputType, current_chain: List[NodeType]):
            if current_depth == self.depth:
                chains.append(current_chain.copy())
                return

            for op_type in self.allowed_operators:
                sig = get_signature(op_type)
                if sig is None:
                    continue

                # Check if operator accepts current input type
                if current_input_type in sig.input_types:
                    # Determine output type of this operator
                    output_type = get_output_type(op_type)
                    if output_type == InputType.SET:
                        next_input_type = InputType.SET
                    elif output_type == InputType.BAG:
                        next_input_type = InputType.BAG
                    elif output_type == InputType.TUPLE:
                        next_input_type = InputType.TUPLE
                    elif output_type == InputType.TUPLE_OF_SETS:
                        next_input_type = InputType.TUPLE_OF_SETS
                    elif output_type == InputType.TUPLE_OF_BAGS:
                        next_input_type = InputType.TUPLE_OF_BAGS
                    else:
                        continue

                    current_chain.append(op_type)
                    build_chain(current_depth + 1, next_input_type, current_chain)
                    current_chain.pop()

        # Start with Set as first input (most common case)
        build_chain(0, InputType.SET, [])

        # Also try starting with Bag if any operator accepts it
        build_chain(0, InputType.BAG, [])

        return chains

    def _sample_operator_chain(self) -> List[NodeType]:
        """Sample or return the operator chain for generation.

        If operator_chain is specified, returns it directly.
        If depth is None, returns empty list (use random selection).
        Otherwise enumerates compatible chains and samples one randomly.
        """
        if self.operator_chain is not None:
            return self.operator_chain

        if self.depth is None:
            return []  # No chain guidance when depth is None

        compatible_chains = self._enumerate_compatible_chains()
        if not compatible_chains:
            raise ValueError(f"No compatible chains found for depth={self.depth} with allowed_operators={self.allowed_operators}")

        return random.choice(compatible_chains)

    def _generate_entities(self) -> List[str]:
        """Generate entity names."""
        entities = []
        for i in range(self.entity_count):
            entity_id = self.property_tracker.request_id(PropertyType.ENTITY)
            entities.append(f"e_{entity_id}")
        self.entitys.extend(entities)
        return entities

    def _add_to_pool(self, node: ExprNode) -> None:
        """Add a node to the pool based on its output type."""
        if isinstance(node, SetNode):
            self.available_pool[InputType.SET].append(node)
        elif isinstance(node, BagNode):
            self.available_pool[InputType.BAG].append(node)
        elif isinstance(node, OperatorNode):
            output_type = node.output_type
            if node.node_type == NodeType.PARTITION:
                return  # PARTITION outputs specially, not directly added to pool
            elif output_type == InputType.TUPLE_OF_BAGS:
                # Unwrap: create IndexedAccessNode for each element and add to BAG pool
                k = node.params.get('k', 2)
                for i in range(0, k):  # 0-based indices
                    indexed_node = self.builder.index_access(node, i)
                    self.available_pool[indexed_node.output_type].append(indexed_node)
            elif output_type == InputType.TUPLE_OF_SETS:
                # Unwrap: create IndexedAccessNode for each element and add to SET pool
                k = node.params.get('k', 2)
                for i in range(0, k):  # 0-based indices
                    indexed_node = self.builder.index_access(node, i)
                    self.available_pool[indexed_node.output_type].append(indexed_node)
            elif output_type in self.available_pool:
                self.available_pool[output_type].append(node)

    def _create_initial_sets_bags(self) -> None:
        """Create initial set/bag nodes and add to pool.

        Randomly chooses between Bag and Set types for each initial node.
        First node has exactly entity_count entities.
        Subsequent nodes have ≤ entity_count entities.
        """
        entities = self._generate_entities()
        logger.info(f"Generated {len(entities)} entities: {entities}")
        seen_sets: set = set()  # Track unique sets to ensure no duplicates

        for i in range(self.initial_set_bag_count):
            is_bag = random.choice([True, False])  # Randomly choose Bag or Set

            if is_bag:
                # Use default multiplicity range if not specified
                multiplicity_range = self.entity_multiplicity_range or (1, self.entity_count)
                elements = {}
                if i == 0:
                    # First bag: distribute entity_count across entities (not all entities required to appear)
                    target_sum = self.entity_count
                    remaining = target_sum
                    for idx, entity in enumerate(entities):
                        if idx == len(entities) - 1:
                            elements[entity] = remaining
                        else:
                            remaining_slots = len(entities) - idx - 1
                            if remaining > remaining_slots:
                                count = random.randint(0, min(remaining - remaining_slots, multiplicity_range[1]))
                            else:
                                count = 0
                            elements[entity] = count
                            remaining -= count
                    # Remove zero-count entries
                    elements = {k: v for k, v in elements.items() if v > 0}
                else:
                    # Subsequent bags: random size 1 to entity_count
                    target_sum = random.randint(1, self.entity_count)
                    remaining = target_sum
                    for idx, entity in enumerate(entities):
                        if idx == len(entities) - 1:
                            elements[entity] = remaining
                        else:
                            remaining_slots = len(entities) - idx - 1
                            if remaining > remaining_slots:
                                # Give minimum 1 to preserve this entity
                                count = 1
                            else:
                                # Not enough remaining for everyone, give 0 to preserve for last
                                count = 0
                            elements[entity] = count
                            remaining -= count
                    # Remove zero-count entries
                    elements = {k: v for k, v in elements.items() if v > 0}

                node = self.builder.create_bag(elements)
                logger.debug(f"Created bag node '{node.name}' with {sum(elements.values())} entity count")
            else:
                # Set mode
                if i == 0:
                    elements = entities[:]  # Include all entities
                    set_key = tuple(sorted(elements))
                    seen_sets.add(set_key)
                    node = self.builder.create_set(elements)
                    logger.debug(f"Created set node '{node.name}' with {len(elements)} elements")
                else:
                    # Generate unique sets until we find one we haven't seen
                    attempts = 0
                    max_attempts = 100
                    target_size = random.randint(1, self.entity_count)
                    while attempts < max_attempts:
                        candidate = tuple(sorted(random.sample(entities, target_size)))
                        if candidate not in seen_sets:
                            elements = list(candidate)
                            break
                        target_size = random.randint(1, self.entity_count)
                        attempts += 1
                    else:
                        # Fallback: use systematic approach
                        remaining_sizes = set(range(1, self.entity_count + 1))
                        for size in remaining_sizes:
                            candidate = tuple(sorted(entities[:size]))
                            if candidate not in seen_sets:
                                elements = list(candidate)
                                break
                        else:
                            elements = random.sample(entities, max(1, self.entity_count))

                    set_key = tuple(sorted(elements))
                    seen_sets.add(set_key)
                    node = self.builder.create_set(elements)
                    logger.debug(f"Created set node '{node.name}' with {len(elements)} elements")

            self._add_to_pool(node)

    def _select_inputs_for_operator(self, operator_type: NodeType) -> Optional[List[ExprNode]]:
        """
        Select compatible inputs for an operator from the pool.
        Returns None if not enough compatible inputs available.
        """
        sig = get_signature(operator_type)
        if sig is None:
            return None
        required_types = sig.input_types
        unique_types = list(dict.fromkeys(required_types))
        if len(unique_types) == 1:
            input_count = len(required_types)
            selected_inputs = self._select_inputs_by_count(unique_types[0], input_count)
            return selected_inputs
        else:
            chosen_type = random.choice(unique_types)
            selected_inputs = self._select_inputs_by_count(chosen_type, 1)
            return selected_inputs

    def _select_inputs_by_count(self, input_type: InputType, count: int) -> Optional[List[ExprNode]]:
        if count == 0:
            return []
        selected = []
        candidates = self.available_pool.get(input_type, []).copy()
        if len(candidates) < count:
            return None
        for _ in range(count): # sample with weighted probabilities based on policy
            if self.depth is not None:
                # Use output-type depth-guided weighting when depth is set
                weighted_probs = self.policy.get_weighted_probs_by_output_type(
                    candidates,
                    self.property_tracker,
                    current_max_depth=self._compute_current_max_depth(),
                    target_depth=self.depth
                )
            else:
                weighted_probs = self.policy.get_weighted_probs(candidates, self.property_tracker)
            sel = random.choices(
                list(weighted_probs.keys()),
                weights=list(weighted_probs.values()),
            )
            candidates.remove(sel[0])
            selected.append(sel[0])
        return selected

    def _sample_k_param(self, operator_type: NodeType, inputs: List[ExprNode]) -> int:
        max_k = len(inputs[0].unique_entities)
        if hasattr(inputs[0], 'params'):
            k_param = inputs[0].params.get('k', max_k)
            max_k = min(max_k, k_param)
        if operator_type in [NodeType.COMPOSE,NodeType.PARTITION]:
            return random.randint(2, max_k) if max_k > 2 else 2
        elif operator_type in [NodeType.CHOOSE, NodeType.CHOOSE_TUPLE]:
            return random.randint(2, max_k) if max_k > 2 else 2
        elif operator_type in [NodeType.CHOOSE_REPLACE, NodeType.CHOOSE_REPLACE_TUPLE, NodeType.CHOOSE_REPLACE_SEQUENCE]:
            if inputs[0].output_type == InputType.BAG:
                return random.randint(2, max_k*2)  if max_k > 2 else 2
            return random.randint(2, max_k*2)  if max_k > 2 else 2
        elif inputs[0].output_type == InputType.BAG:
            return random.randint(2, max_k*2)  if max_k > 2 else 2
        else:
            return random.randint(2, max_k) if max_k > 2 else 2
        return  0
    def _create_operator(self, operator_type: NodeType, inputs: List[ExprNode]) -> OperatorNode:
        """Create an operator node with given inputs."""
        assert len(inputs) > 0, "inputs must not be empty"
        params = {}
        params['k'] = self._sample_k_param(operator_type, inputs)
        params['reflection'] = random.choice([True, False])

        # Create node via builder
        if operator_type == NodeType.CHOOSE:
            node = self.builder.choose(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.CHOOSE_REPLACE:
            node = self.builder.choose_replace(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.CHOOSE_TUPLE:
            node = self.builder.choose_tuple(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.CHOOSE_REPLACE_TUPLE:
            node = self.builder.choose_tuple(inputs[0],k=params.get('k', 2), replace=True)
        elif operator_type == NodeType.SEQUENCE:
            node = self.builder.sequence(inputs[0])
        elif operator_type == NodeType.CIRCLE:
            node = self.builder.circle(inputs[0],reflection=params.get('reflection', False))
        elif operator_type == NodeType.COMPOSE:
            node = self.builder.compose(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.PARTITION:
            node = self.builder.partition(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.SET_UNION:
            node = self.builder.set_union(inputs[0],inputs[1])
        elif operator_type == NodeType.SET_INTERSECTION:
            node = self.builder.set_intersection(inputs[0],inputs[1])
        elif operator_type == NodeType.SET_DIFFERENCE:
            node = self.builder.set_difference(inputs[0],inputs[1])
        elif operator_type == NodeType.BAG_UNION:
            node = self.builder.bag_union(inputs[0],inputs[1])
        elif operator_type == NodeType.BAG_INTERSECTION:
            node = self.builder.bag_intersection(inputs[0],inputs[1])
        elif operator_type == NodeType.BAG_DIFFERENCE:
            node = self.builder.bag_difference(inputs[0],inputs[1])
        elif operator_type == NodeType.CHOOSE_REPLACE_SEQUENCE:
            node = self.builder.choose_replace_sequence(inputs[0],k=params.get('k', 2))
        elif operator_type == NodeType.TUPLE:
            node = self.builder.tuple(inputs[0])
        else:
            raise ValueError(f"Unsupported operator type: {operator_type}")
        logger.debug(f"Created operator {operator_type.name} as '{node.name}' with entities={node.entitys}")
        return node

    def generate(self, property_tracker: PropertyTracker) -> ProblemStructure:
        """Generate a problem using pool-based approach."""
        self.property_tracker = property_tracker
        logger.info("Starting problem generation")

        # Step 1: Create initial set/bag nodes
        self.entitys = []
        self._create_initial_sets_bags()
        logger.info(f"Initial pool: SET={len(self.available_pool[InputType.SET])}, BAG={len(self.available_pool[InputType.BAG])}")

        # Step 2: Generate operators
        attempts = 0
        max_attempts = self.operator_count * 150

        # Sample the operator chain once at the start
        chain = self._sample_operator_chain()
        self._chain_index = 0

        while len(self.operator_nodes) < self.operator_count and attempts < max_attempts:
            attempts += 1

            # Use chain to determine operator type if within chain length
            if self._chain_index < len(chain):
                operator_type = chain[self._chain_index]
                self._chain_index += 1
            else:
                # After chain is exhausted, use random selection
                operator_type = random.choice(self.allowed_operators)

            # Select compatible inputs from pool
            inputs = self._select_inputs_for_operator(operator_type)
            if inputs is None or len(inputs) == 0:
                continue

            # Create operator node
            op_node = self._create_operator(operator_type, inputs)

            # Verify operator has available entities
            if not op_node.unique_entities:
                # No entities available, discard and retry
                continue

            self.operator_nodes.append(op_node)

            # Add output to pool
            self._add_to_pool(op_node)
        logger.info(f"Generated {len(self.operator_nodes)} operator nodes")
        # Step 4: Add constraints
        self._add_constraints()
        logger.info("Problem generation complete")
        problem_structure = ProblemStructure(
            bindings=dict(self.builder.bindings),
            global_constraints=[]
        )
        problem_structure.entitys = self.entitys

        # Validate depth if depth parameter was specified
        if self.depth is not None:
            problem_structure.depth_validate(self.depth)

        return problem_structure

    def _add_constraints(self) -> None:
        """Add constraints to applicable operator nodes."""
        can_constraint_nodes = [node for node in self.operator_nodes if not node.is_deterministic]
        if can_constraint_nodes == []:
            return
        have_added_constraints = []
        sample_count = 0
        while sample_count < self.constraint_count * 30 and len(have_added_constraints) < self.constraint_count:
            sample_count += 1
            application_node = random.choice(can_constraint_nodes)
            applicable_constraints = [c for c in self.allowed_constraints if c.is_applicable(application_node)]
            if not applicable_constraints:
                return
            bindings = dict(self.builder.bindings)
            constraint_template = random.choice(applicable_constraints)
            import copy
            constraint_instance = copy.deepcopy(constraint_template)
            
            # Assign parameters with knowledge of target entities
            is_ok = constraint_instance.assignParameters(application_node, bindings)
            if is_ok and constraint_instance not in have_added_constraints:
                application_node.constraints.append(constraint_instance)
                logger.debug(f"Added {constraint_instance.__class__.__name__} to node '{application_node.name}': {constraint_instance}")
                have_added_constraints.append(constraint_instance)

    @classmethod
    def create_configured_generator(
        cls,
        root_type_name: str,
        depth: int = 4,
        entity_size: Tuple[int, int] = (5, 10),
        constraint_count: int = 2
    ) -> 'CombinationProblemGenerator':
        """Factory method to create a configured generator."""
        import random as rand_module
        rand_module.seed()

        type_configs = {
            "Bag": {
                "allowed_operators": [
                    NodeType.CHOOSE_REPLACE,
                    NodeType.CHOOSE,
                    NodeType.BAG_UNION,
                    NodeType.BAG_INTERSECTION,
                    NodeType.BAG_DIFFERENCE,
                ],
                "question_types": "Bag",
                "entity_multiplicity_range": (1, 4),
            },
            "BagChoose": {
                "allowed_operators": [NodeType.CHOOSE_REPLACE],
                "question_types": "Bag",
                "entity_multiplicity_range": (1, 4),
            },
            "SetChoose": {
                "allowed_operators": [NodeType.CHOOSE],
                "question_types": None,
            },
            "Compose": {
                "allowed_operators": [NodeType.COMPOSE, NodeType.CHOOSE],
                "question_types": None,
            },
            "all": {
                "allowed_operators": list(OPERATOR_SIGNATURES.keys()),
                "question_types": None,
            },
        }

        config = type_configs.get(root_type_name, type_configs["all"])
        return cls(
            entity_count=rand_module.randint(*entity_size),
            entity_multiplicity_range=config.get("entity_multiplicity_range"),
            allowed_operators=config["allowed_operators"],
            operator_count=depth,
            constraint_count=constraint_count,
            depth=depth,
        )

def main():
    # Type alias for root type configuration
    from translator.tree2cofola import TreeToCofolaConverter
    from properties import PropertyTracker
    print("=" * 60)
    print("DAG-based Problem Generator Demo")
    print("=" * 60)
    while True:
        try:
            gen = CombinationProblemGenerator(
                allowed_operators=list(OPERATOR_SIGNATURES.keys()),
                allowed_constraints=ALL_CONSTRAINTS,
                entity_count=10,
                initial_set_bag_count=1,
                operator_count=3,
                constraint_count=3,
                entity_multiplicity_range=(2, 4),
                depth=2,
                # operator_chain=[NodeType.CHOOSE, NodeType.COMPOSE, NodeType.CHOOSE_REPLACE]
            )
            tracker = PropertyTracker()
            problem = gen.generate(tracker)
            for binding in problem.bindings.values():
                for constraint in binding.constraints:
                    print(f"  Constraint: {constraint},{type(constraint)}")
            converter = TreeToCofolaConverter()
            code = converter.convert(problem)
            print(code)
            cofolaproblem = parse(code)
            # solutions = solve(cofolaproblem)
            # print(f"Number of solutions: {solutions}")
            print(code)
            break
        except:
            pass
    from translator.language_generator import LanguageGenerator
    from translator.template_manager import TemplateManager
    from translator.context_manager import TranslationContext, ThemeType
    lang_gen = LanguageGenerator(theme=ThemeType.MATH_EN,template_file_path="templates/template_en.json")
    lang_code = lang_gen.generate(problem, ThemeType.MATH_EN)
    print("\n" + "=" * 60)
    print("Generated Natural Language Description")
    print("=" * 60)
    print(lang_code)
    # for binding in problem.bindings.values():
    #     print(binding.name)
    #     for constraint in binding.constraints:
    #         print(f"  Constraint: {constraint},{type(constraint)}")
    print(problem.problem_depth())

if __name__ == "__main__":
    main()