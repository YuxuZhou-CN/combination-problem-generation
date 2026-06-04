from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import os
@dataclass
class Template:
    story_template: str
    entity_pool: List[str]
    entity_type: str
    entity_unit: str
    empty_entity: str
    types: Dict[str, str]
    inference_rules: Dict[str, str]
    operation_descriptions: Dict[str, str]
    constraint_descriptions: Dict[str, str]
    comparator2str: Dict[str, str]
    positive_bool2txt: Dict[str, str]
    question_templates: Dict[str, str]

class TemplateManager:
    """模板管理器 - 支持语言模板和背景模板"""
    def __init__(self, template_file_path):
        self.template_file_path = template_file_path
        self.templates: Dict[str, Template] = {}
        self._load_templates()

    
    def _load_templates(self):
        """加载语言模板文件"""
        template_file = self.template_file_path
        with open(template_file, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            self._parse_templates(template_data)
    def _parse_templates(self, template_data: dict):
        """解析背景模板数据"""
        for theme_name, theme_data in template_data.items():
            if isinstance(theme_data, dict):
                self.templates[theme_name] = Template(
                    story_template=theme_data.get("story_template", ""),
                    entity_pool=theme_data.get("entity_pool", []),
                    entity_type=theme_data.get("entity_type", ""),
                    empty_entity=theme_data.get("empty_entity", ""),
                    entity_unit=theme_data.get("entity_unit", ""),
                    types=theme_data.get("types", {}),
                    inference_rules=theme_data.get("inference_rules", {}),
                    operation_descriptions=theme_data.get("operation_descriptions", {}),
                    constraint_descriptions=theme_data.get("constraint_descriptions", {}),
                    question_templates=theme_data.get("question_templates", {}),
                    comparator2str=theme_data.get("comparator2str", {}),
                    positive_bool2txt=theme_data.get("positive_bool2txt", {})
                )
    def get_template(self, category: str) -> Optional[Template]:
        """获取指定类型的语言模板"""
        return self.templates.get(category, {})
    
    def format_template(self, template: Template, variables: Dict[str, str]) -> str:
        """格式化模板"""
        try:
            return template.pattern.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for template formatting")
    def list_available_themes(self) -> List[str]:
        """列出可用的主题"""
        return list(self.templates.keys())
    def get_theme_operations(self, theme: str) -> Dict[str, str]:
        """获取主题的操作描述"""
        template = self.get_template(theme)
        return template.operation_descriptions if template else {}
    def get_theme_constraints(self, theme: str) -> Dict[str, str]:
        """获取主题的约束描述"""
        template = self.get_template(theme)
        return template.constraint_descriptions if template else {}
    def get_theme_entities(self, theme: str) -> List[str]:
        """获取主题的实体池"""
        template = self.get_template(theme)
        return template.entity_pool if template else []
    def get_theme_questions(self, theme: str) -> Dict[str, str]:
        """获取主题的提问模板"""
        template = self.get_template(theme)
        return template.question_templates if template else {}
if __name__ == "__main__":
    tm = TemplateManager("template_en")
    print("Available themes:", tm.list_available_themes())
    math_template = tm.get_template("MATH")
    if math_template:
        print("Math Story Template:", math_template.story_template)
        print("Entity Pool:", math_template.entity_pool)
        print("Inference Rules:", math_template.inference_rules)
        print("Operation Descriptions:", math_template.operation_descriptions)
        print("Constraint Descriptions:", math_template.constraint_descriptions)
        print("Question Templates:", math_template.question_templates)
