"""Operator registry - defines input/output types for each operator."""
from dag.expr_node import InputType, NodeType
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class OperatorSignature:
    """Defines input types and output type for an operator."""
    node_type: NodeType
    input_types: List[InputType]  # Required inputs in order
    output_type: InputType
    param_schema: Dict[str, Any] = field(default_factory=dict)
    input_to_output_map: Dict[InputType, InputType] = field(default_factory=dict)  # 新增

# Registry of all operators with their signatures
OPERATOR_SIGNATURES: Dict[NodeType, OperatorSignature] = {
    NodeType.CHOOSE: OperatorSignature(
        node_type=NodeType.CHOOSE,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.SET,
        param_schema={'k': (1, 'int')},
        input_to_output_map={InputType.SET: InputType.SET, InputType.BAG: InputType.BAG},
    ),
    NodeType.CHOOSE_REPLACE: OperatorSignature(
        node_type=NodeType.CHOOSE_REPLACE,
        input_types=[InputType.SET],  # 不支持 BAG 输入
        output_type=InputType.BAG,
        param_schema={'k': (1, 'int')},
        input_to_output_map={InputType.SET: InputType.BAG},
    ),
    NodeType.CHOOSE_TUPLE: OperatorSignature(
        node_type=NodeType.CHOOSE_TUPLE,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.TUPLE,
        param_schema={'k': (1, 'int')},
        input_to_output_map={InputType.SET: InputType.TUPLE, InputType.BAG: InputType.TUPLE},
    ),
    NodeType.CHOOSE_REPLACE_TUPLE: OperatorSignature(
        node_type=NodeType.CHOOSE_REPLACE_TUPLE,
        input_types=[InputType.SET], # 不支持 BAG 输入
        output_type=InputType.TUPLE,
        param_schema={'k': (1, 'int')},
        input_to_output_map={InputType.SET: InputType.TUPLE},
    ),
    NodeType.SEQUENCE: OperatorSignature(
        node_type=NodeType.SEQUENCE,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.TUPLE,
        input_to_output_map={InputType.SET: InputType.TUPLE, InputType.BAG: InputType.TUPLE},
    ),
    NodeType.CIRCLE: OperatorSignature(
        node_type=NodeType.CIRCLE,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.TUPLE,
        param_schema={'reflection': (False, 'bool')},
        input_to_output_map={InputType.SET: InputType.TUPLE, InputType.BAG: InputType.TUPLE},
    ),
    NodeType.COMPOSE: OperatorSignature(
        node_type=NodeType.COMPOSE,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.TUPLE_OF_SETS,
        param_schema={'k': (2, 'int')},
        input_to_output_map={InputType.SET: InputType.TUPLE_OF_SETS, InputType.BAG: InputType.TUPLE_OF_SETS},
    ),
    NodeType.PARTITION: OperatorSignature(
        node_type=NodeType.PARTITION,
        input_types=[InputType.SET, InputType.BAG],
        output_type=InputType.TUPLE_OF_SETS,
        param_schema={'k': (2, 'int')},
        input_to_output_map={InputType.SET: InputType.TUPLE_OF_SETS, InputType.BAG: InputType.TUPLE_OF_SETS},
    ),
    # Binary operators
    NodeType.SET_UNION: OperatorSignature(
        node_type=NodeType.SET_UNION,
        input_types=[InputType.SET, InputType.SET],
        output_type=InputType.SET,
    ),
    NodeType.SET_INTERSECTION: OperatorSignature(
        node_type=NodeType.SET_INTERSECTION,
        input_types=[InputType.SET, InputType.SET],
        output_type=InputType.SET,
    ),
    NodeType.SET_DIFFERENCE: OperatorSignature(
        node_type=NodeType.SET_DIFFERENCE,
        input_types=[InputType.SET, InputType.SET],
        output_type=InputType.SET,
    ),
    NodeType.BAG_UNION: OperatorSignature(
        node_type=NodeType.BAG_UNION,
        input_types=[InputType.BAG, InputType.BAG],
        output_type=InputType.BAG,
    ),
    NodeType.BAG_INTERSECTION: OperatorSignature(
        node_type=NodeType.BAG_INTERSECTION,
        input_types=[InputType.BAG, InputType.BAG],
        output_type=InputType.BAG,
    ),
    NodeType.BAG_DIFFERENCE: OperatorSignature(
        node_type=NodeType.BAG_DIFFERENCE,
        input_types=[InputType.BAG, InputType.BAG],
        output_type=InputType.BAG,
    ),

    NodeType.CHOOSE_REPLACE_SEQUENCE: OperatorSignature(
        node_type=NodeType.CHOOSE_REPLACE_SEQUENCE,
        input_types=[InputType.SET], # 不支持 BAG 输入
        output_type=InputType.TUPLE,
        param_schema={'k': (1, 'int')},
        input_to_output_map={InputType.SET: InputType.TUPLE},
    ),
    
    NodeType.TUPLE: OperatorSignature(
        node_type=NodeType.TUPLE,
        input_types=[InputType.SET],
        output_type=InputType.TUPLE,
    ),
}

def get_signature(node_type: NodeType) -> Optional[OperatorSignature]:
    return OPERATOR_SIGNATURES.get(node_type)

def get_output_type(node_type: NodeType, input_type: InputType = None) -> InputType:
    sig = get_signature(node_type)
    if sig is None:
        return InputType.ANY
    if input_type is not None and sig.input_to_output_map:
        return sig.input_to_output_map.get(input_type, sig.output_type)
    return sig.output_type

def get_input_types(node_type: NodeType) -> List[InputType]:
    sig = get_signature(node_type)
    return sig.input_types if sig else []