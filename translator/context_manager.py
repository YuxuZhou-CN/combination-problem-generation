"""Translation context manager."""

from enum import Enum
from typing import Dict, List, Optional, Set, Any

from .template_manager import Template, TemplateManager
from dag.expr_node import ExprNode,NodeType,OperatorNode
from dag.constraints import *

class ThemeType(Enum):
    """主题类型枚举"""

    MATH_EN = "MATH_EN"
    MATH_CH = "MATH_CH"
    CARD_EN = "CARD_EN"
    CARD_CH = "CARD_CH"


class TranslationContext:
    """翻译上下文管理器"""

    ORDINALS = [
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
    ]

    def __init__(
        self,
        theme: ThemeType = ThemeType.MATH_EN,
        template_file_path: str = "./templates/template_en.json",
        templateManger: Optional[TemplateManager] = None,
    ) -> None:
        self.templateManger = templateManger or TemplateManager(template_file_path=template_file_path)
        self.template_manager = self.templateManger
        self.theme = theme
        self.template = self.templateManger.get_template(theme.value)
        if self.template is None:
            raise ValueError(f"Unknown theme: {theme.value}")
        self.entity_names: Dict[str, str] = {}
        self.set_names: Dict[str, str] = {}
        self.inference_rules_descriptions: List[Dict[ExprNode, str]] = []
        self.operation_descriptions: Dict[ExprNode, str] = {}
        self.constraint_descriptions: Dict[str, str] = {}
        self.used_names: typSet[str] = set()

    def _ordinal(self, n: int) -> str:
        """Convert 1-based index to ordinal string."""
        if 1 <= n <= len(self.ORDINALS):
            return self.ORDINALS[n - 1]
        return f"{n}th"

    def get_entity_name(self, entity: str) -> str:
        """获取实体的自然语言名称"""
        if entity not in self.entity_names:
            self.entity_names[entity] = self._generate_entity_name(entity)
        return self.entity_names[entity]

    def _generate_entity_name(self, entity: str) -> str:
        """根据主题和实体生成名称，建立元素_i与entity_i的对应关系"""
        template = self.template
        if template is None:
            raise ValueError(f"Unknown theme: {self.theme.value}")

        if entity.startswith("e_"):
            try:
                index = int(entity.split("_")[1]) - 1
                if index < len(template.entity_pool):
                    name = template.entity_pool[index]
                    if name not in self.used_names:
                        self.used_names.add(name)
                        return name
            except (ValueError, IndexError):
                pass

        for name in template.entity_pool:
            if name not in self.used_names:
                self.used_names.add(name)
                return name

        return f"{template.entity_type}_{len(self.entity_names) + 1}"


    def _generate_bag_entity_name(self, entitys: Dict):
        """根据主题生成实体名称"""
        template = self.templateManger.get_template(self.theme.value)
        if template is None:
            raise ValueError(f"Unknown theme: {self.theme.value}")

        entity_type = template.entity_type
        empty_entity = template.empty_entity
        entity_unit = template.entity_unit

        entity_counts = {}
        if len(entitys) == 0:
            return empty_entity.format(entity_type=entity_type)

        for entity, count in entitys.items():
            name = self.get_entity_name(entity)
            entity_counts[name] = count

        description_parts = []
        for name, count in entity_counts.items():
            description_parts.append(f"{name}:{count}{entity_unit}")
        return ",".join(description_parts)

    def map_set_to_str(self, node: ExprNode) -> None:
        """Manually map a set of entities to a specific name."""
        if node.node_type != NodeType.SET:
            return
        name = node.name # TODO :这里可以使用外部传入的模板来生成名称
        self.set_names[node.name] = name 
        set_template = self.template.types['set']
        entitys = []
        # TODO: 判断节点内实体是否连续，如果连续可以用省略版的模版
        for entity in node.entitys:
            entity_name = self.get_entity_name(entity)
            entitys.append(entity_name)
        params = {
            "set_name": name,
            "description": "、".join(entitys)
        }
        set_description = set_template.format(**params)
        self.operation_descriptions[node] = set_description
        self.set_names[node.name] = name

    def map_bag_to_str(self, node: ExprNode) -> None:
        """Manually map a bag of entities to a specific name."""
        if node.node_type != NodeType.BAG:
            return
        name = node.name  # TODO :这里可以使用外部传入的模板来生成名称
        self.set_names[node.name] = name
        bag_template = self.template.types["bag"]
        params = {
            "set_name": name,
            "description": self._generate_bag_entity_name(getattr(node, "entitys", {}) or {}),
        }
        bag_description = bag_template.format(**params)
        self.operation_descriptions[node] = bag_description
        self.set_names[node.name] = name

    def map_operator_to_str(self, node: ExprNode) -> None:
        """Manually map an operator to a specific description."""
        if not isinstance(node, OperatorNode):
            return
        template = self.template.operation_descriptions[node.node_type.value]

        output_name = node.name # TODO :这里可以使用外部传入的模板来生成名称

        params = {
            "source_name": self.tranfromNodeName(node.inputs[0]),
            "left_name": self.tranfromNodeName(node.inputs[0]),
            "right_name": self.tranfromNodeName(node.inputs[1]) if len(node.inputs) > 1 else "",
            "node_name": output_name,
            "k": node.params.get("k", ""),
            "reflection": ",two arrangements are considered the same if one can be rotated or reflected (flipped) to match the other." if node.params.get("reflection", True) else ".",
        }
        operation_description = template.format(**params)
        self.operation_descriptions[node] = operation_description
        self.set_names[node.name] = output_name
    

    def map_constraint_to_str(self, node: ExprNode) -> None:
        """Manually map an operator to a specific description."""
        if not isinstance(node, OperatorNode):
            return
        if node.constraints is None:
            return
        for constraint in node.constraints:
            params = constraint.get_parameters()
            params = self.transformParam(params)
            constraint_template = self.template.constraint_descriptions.get(constraint.__class__.__name__, "")
            if isinstance(constraint,(NextToConstraint,PredecessorConstraint,TogetherConstraint,LessThanConstraint)):
                constraint_template = constraint_template[params['positive']]
            if isinstance(constraint,SequenceCountConstraint):
                count_type = constraint.count_type
                count_type_template = constraint_template['count_type'][count_type]
                count_type_str = count_type_template.format(**params)
                params['count_type'] = count_type_str
                constraint_template = constraint_template['base']
            constraint_description = constraint_template.format(**params)
            if constraint_description == "":
                continue
            # Use a stable string key because constraint dataclasses are mutable and unhashable.
            self.constraint_descriptions[repr(constraint)] = constraint_description

    def map_question_to_str(self,nodes: List[ExprNode]) -> None:
        """Manually map a question node to a specific description."""
        question_template = self.template.question_templates
        uncertain_nodes = [node for node in nodes if not node.is_deterministic and node.node_type != NodeType.INDEXED_ACCESS]
        uncertain_str = ",".join([self.tranfromNodeName(node) for node in uncertain_nodes])
        question_description = question_template.format(uncertain_node_name=uncertain_str)
        return question_description
        
    
    # 节点名到模板名的映射
    def tranfromNodeName(self,node: OperatorNode) -> str:
        if node.node_type == NodeType.INDEXED_ACCESS:
            parent_name = node.parent.name
            index = node.index
            node_name = f"The {index + 1}th division group of {self.set_names[parent_name]}"
            self.set_names[node.name] = node_name
        
        return self.set_names.get(node.name, node.name)

    def transformParam(self,param:dict) -> dict:
        transformed_param = {}
        for key, value in param.items():
            if isinstance(value, ExprNode):
                transformed_param[key] = self.tranfromNodeName(value)
            elif isinstance(value,IndexAccess):
                transformed_param[key] = self.tranfromNodeName(value)
            elif key.startswith("en"):
                transformed_param[key] = self.get_entity_name(value)
            elif key=="comparator":
                transformed_param[key] = self.template.comparator2str.get(value, value)
            elif isinstance(value,list):
                transformed_param[key] = ",".join([self.get_entity_name(item) for item in value])
            elif key == "reflection":
                transformed_param[key] = " Two arrangements are considered the same if one can be rotated or reflected (flipped) to match the other."

            else:
                transformed_param[key] = value

        return transformed_param