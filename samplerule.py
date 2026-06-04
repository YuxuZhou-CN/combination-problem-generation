"""Rule sampling policy for DAG-based problem generation."""

from typing import List, Dict, Any
from dag.expr_node import NodeType
import random

class RuleSamplingPolicy:
    """Sampling policy for inference rules."""

    DERIVED_WEIGHT = 40.0
    INITIAL_WEIGHT = 20.0
    LOW_WEIGHT = 1.0
    DERIVED_OPERATORS = {
        NodeType.SET_UNION,
        NodeType.SET_INTERSECTION,
        NodeType.SET_DIFFERENCE,
        NodeType.BAG_UNION,
        NodeType.BAG_INTERSECTION,
        NodeType.BAG_DIFFERENCE,
    }
    LOW_OPERATORS = {
        NodeType.BAG,
        NodeType.SET,
    }

    def get_weight(self, node: Any) -> float:
        """Returns the sampling weight for a node based on its origin."""
        if node.node_type in self.LOW_OPERATORS:
            return self.LOW_WEIGHT
        if node.node_type in self.DERIVED_OPERATORS:
            return self.DERIVED_WEIGHT
        return self.INITIAL_WEIGHT

    def get_weighted_probs(self, candidates: List, context: Any) -> Dict:
        """Returns weights for each candidate based on node origin."""
        if not candidates:
            return {}
        weights = [self.get_weight(c) for c in candidates]
        total = sum(weights)
        return {c: w / total for c, w in zip(candidates, weights)}

    def get_weighted_probs_with_depth(
        self,
        candidates: List,
        context: Any,
        current_max_depth: int,
        target_depth: int
    ) -> Dict:
        """
        Get weighted probabilities with depth-guided boosting for non-deterministic operators.

        When current_max_depth < target_depth, non-deterministic operators receive
        boosted weights proportional to the depth gap.
        """
        if not candidates:
            return {}

        # Get base weights
        weights = {}
        for c in candidates:
            base_weight = self.get_weight(c)
            # Boost non-deterministic operators when depth is insufficient
            if current_max_depth < target_depth:
                if hasattr(c, 'is_deterministic') and not c.is_deterministic:
                    depth_gap = target_depth - current_max_depth
                    base_weight *= (depth_gap + 1)
            weights[c] = base_weight

        total = sum(weights.values())
        return {c: w / total for c, w in weights.items()}

    # Output type classification
    OUTPUT_TYPE_SET = {NodeType.CHOOSE, NodeType.SET_UNION, NodeType.SET_INTERSECTION, NodeType.SET_DIFFERENCE}
    OUTPUT_TYPE_BAG = {NodeType.CHOOSE_REPLACE, NodeType.BAG_UNION, NodeType.BAG_INTERSECTION, NodeType.BAG_DIFFERENCE}
    OUTPUT_TYPE_TUPLE_OF_SETS = {NodeType.COMPOSE, NodeType.PARTITION}
    OUTPUT_TYPE_TUPLE = {NodeType.CHOOSE_TUPLE, NodeType.CHOOSE_REPLACE_TUPLE, NodeType.SEQUENCE, NodeType.CIRCLE, NodeType.CHOOSE_REPLACE_SEQUENCE}

    def _get_output_type_category(self, node_type: NodeType) -> str:
        """Returns output type category: 'SET', 'BAG', 'TUPLE_OF_SETS', 'TUPLE'."""
        if node_type in self.OUTPUT_TYPE_SET:
            return 'SET'
        elif node_type in self.OUTPUT_TYPE_BAG:
            return 'BAG'
        elif node_type in self.OUTPUT_TYPE_TUPLE_OF_SETS:
            return 'TUPLE_OF_SETS'
        elif node_type in self.OUTPUT_TYPE_TUPLE:
            return 'TUPLE'
        else:
            # Default fallback: Unknown node types are treated as SET.
            # This is intentional as SET is the most common output type.
            return 'SET'

    def get_weighted_probs_by_output_type(
        self,
        candidates: List,
        context: Any,
        current_max_depth: int,
        target_depth: int
    ) -> Dict:
        """
        Get weighted probabilities with output-type-based depth guidance.

        Phase thresholds:
        - Early (< 60% target depth): SET×3, BAG×3, TUPLE_OF_SETS×2, TUPLE×0.1
        - Middle (60%-90%): SET×2, BAG×2, TUPLE_OF_SETS×3, TUPLE×1
        - Late (>= 90%): SET×1, BAG×1, TUPLE_OF_SETS×2, TUPLE×4
        """
        if target_depth is None:
            return self.get_weighted_probs(candidates, context)

        if not candidates:
            return {}

        # Compute depth ratio (capped at 1.0)
        ratio = min(current_max_depth / target_depth, 1.0) if target_depth > 0 else 0

        # Determine phase weights
        if ratio < 0.6:
            phase_weights = {'SET': 3.0, 'BAG': 3.0, 'TUPLE_OF_SETS': 2.0, 'TUPLE': 0.1}
        elif ratio < 0.9:
            phase_weights = {'SET': 2.0, 'BAG': 2.0, 'TUPLE_OF_SETS': 3.0, 'TUPLE': 1.0}
        else:
            phase_weights = {'SET': 1.0, 'BAG': 1.0, 'TUPLE_OF_SETS': 2.0, 'TUPLE': 4.0}

        # Compute weighted probabilities
        weights = {}
        for c in candidates:
            base_weight = self.get_weight(c)
            output_category = self._get_output_type_category(c.node_type)
            multiplier = phase_weights.get(output_category, 1.0)
            weights[c] = base_weight * multiplier

        total = sum(weights.values())
        return {c: w / total for c, w in weights.items()}

    def get_probs(self, node: Any, rules: List, context: Any) -> Dict:
        """Returns the probabilities with which each rule should be selected."""
        return {r: 1.0 / len(rules) for r in rules if rules}

    def sample(self, node: Any, rules: List, context: Any) -> Any:
        """
        Samples an inference rule by establishing which rules are applicable,
        and then choosing a rule according to its probability.
        """
        if not rules:
            return None
        return random.choice(rules)