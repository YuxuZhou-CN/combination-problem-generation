from translator.context_manager import ThemeType
from translator.template_manager import TemplateManager

# Pattern → entity type mapping
ENTITY_TYPE_PATTERNS = (
    (('boy', 'girl', 'student', 'person', 'member', 'alex', 'bob', 'friend'), 'person'),
    (('book', 'math_book', 'english_book'), 'book'),
    (('apple', 'orange', 'fruit', 'plant'), 'fruit'),
    (('card',), 'card'),
    (('coin', 'quarter', 'nickel', 'penny'), 'coin'),
    (('ball',), 'ball'),
    (('team',), 'team'),
    (('line',), 'line'),
)

class EntityNamer:
    _template_manager = None

    def _get_template_manager(self) -> TemplateManager:
        if EntityNamer._template_manager is None:
            EntityNamer._template_manager = TemplateManager("templates/all_templates.json")
        return EntityNamer._template_manager

    def infer_entity_type(self, name: str) -> str:
        """Infer entity type from variable name."""
        name_lower = name.lower()
        for patterns, etype in ENTITY_TYPE_PATTERNS:
            for p in patterns:
                if p in name_lower:
                    return etype
        return 'element'

    def get_entity_name(self, raw_entity: str, variable_name: str, theme: ThemeType) -> str:
        """Map raw entity (boy0) to contextual name (Alex)."""
        del variable_name  # unused, kept for API compatibility
        tm = self._get_template_manager()
        template = tm.get_template(theme.value)
        if template is None:
            return raw_entity
        pool = template.entity_pool
        if not pool:
            return raw_entity
        # Hash the raw entity to get a deterministic index
        idx = hash(raw_entity) % len(pool)
        return pool[idx]