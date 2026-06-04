"""Natural language generator."""

from __future__ import annotations

from re import Pattern
import re
from typing import Dict, List, Optional, Any
from .context_manager import TranslationContext, ThemeType
from .template_manager import TemplateManager
from dag.expr_node import SetNode, BagNode, TupleNode, OperatorNode

class LanguageGenerator:
    """自然语言生成器"""
    def __init__(self, theme=ThemeType.MATH_EN,template_file_path="templates/template_en.json"):
        self.context = TranslationContext(theme=theme, template_file_path=template_file_path)

    def generate(self, problem: 'ProblemStructure', theme: 'ThemeType' = None) -> str:
        """Walk DAG and produce natural language problem description.

        三步翻译：
        1. 集合定义（SetNode/BagNode）
        2. 操作翻译（OperatorNode）
        3. 约束翻译（所有约束）
        """
        from dag.expr_node import OperatorNode, SetNode, BagNode

        # Set theme
        if theme is not None:
            self.context.theme = theme

        # Reset name counters for each generation
        self._name_counts = {}
        parts = []
        for node in problem.all_nodes():
            self.context.map_set_to_str(node)
            self.context.map_bag_to_str(node)
            self.context.map_operator_to_str(node)
        for node in problem.all_nodes():
            self.context.map_constraint_to_str(node)
        parts.extend(self.context.operation_descriptions.values())
        parts.extend(self.context.constraint_descriptions.values())
        question_des = self.context.map_question_to_str(problem.all_nodes())
        parts.append(question_des)
        return '\n'.join(parts)
