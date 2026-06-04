"""Base DAG inference rule class."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from dag.expr_node import ExprNode

class DAGInferenceRule(ABC):
    """Base class for DAG inference rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name for debugging."""
        pass

    @abstractmethod
    def is_applicable(self, target: ExprNode) -> bool:
        """Check if rule can be applied to target node."""
        pass

    @abstractmethod
    def get_parametrization(self, target: ExprNode, context: 'ProblemContext') -> dict:
        """Generate parametrization for the rule application."""
        pass
