"""Expression DAG for combinatorial problem representation."""
from dag.expr_node import (
    ExprNode,
    NodeType,
    InputType,
    SetNode,
    BagNode,
    TupleNode,
    OperatorNode,
)

# These imports will be available as tasks complete
# Using try/except to allow partial imports during early development
try:
    from dag.problem_structure import ProblemStructure
except ImportError:
    ProblemStructure = None

try:
    from dag.constraints import (
        Constraint,
        CountConstraint,
        MemberConstraint,
        CardinalityConstraint,
        PositionConstraint,
        AdjacentConstraint,
        TogetherConstraint,
        SubsetConstraint,
        DisjointConstraint,
        CompositeConstraint,
        QuantifiedConstraint,
    )
except ImportError:
    Constraint = None
    CountConstraint = None
    MemberConstraint = None
    CardinalityConstraint = None
    PositionConstraint = None
    AdjacentConstraint = None
    TogetherConstraint = None
    SubsetConstraint = None
    DisjointConstraint = None
    CompositeConstraint = None
    QuantifiedConstraint = None

try:
    from dag.dag_builder import DAGBuilder
except ImportError:
    DAGBuilder = None

try:
    from dag.code_generator import DAGCodeGenerator
except ImportError:
    DAGCodeGenerator = None

__all__ = [
    "ExprNode",
    "NodeType",
    "InputType",
    "SetNode",
    "BagNode",
    "TupleNode",
    "OperatorNode",
    "ProblemStructure",
    "Constraint",
    "CountConstraint",
    "MemberConstraint",
    "CardinalityConstraint",
    "PositionConstraint",
    "AdjacentConstraint",
    "TogetherConstraint",
    "SubsetConstraint",
    "DisjointConstraint",
    "CompositeConstraint",
    "QuantifiedConstraint",
    "DAGBuilder",
    "DAGCodeGenerator",
]
