"""Cofola code generator using DAG structure."""

from typing import Optional
from dag.code_generator import DAGCodeGenerator
from dag.problem_structure import ProblemStructure


class TreeToCofolaConverter:
    """Converts DAG to Cofola DSL code."""

    def __init__(self):
        self.code_generator = DAGCodeGenerator()

    def convert(self, problem: ProblemStructure, optimize: bool = False) -> str:
        """Convert ProblemStructure to Cofola DSL code."""
        code = self.code_generator.generate(problem)
        if optimize:
            code = self._optimize(code)
        return code

    def _optimize(self, code: str) -> str:
        """Simple code optimization."""
        lines = code.split('\n')
        optimized = []
        seen = set()
        for line in lines:
            if '=' in line and not line.strip().startswith('#'):
                var = line.split('=')[0].strip()
                if var not in seen:
                    seen.add(var)
                    optimized.append(line)
            else:
                optimized.append(line)
        return '\n'.join(optimized)


def generate_cofola_code(problem: ProblemStructure) -> str:
    """Generate Cofola DSL code from ProblemStructure."""
    converter = TreeToCofolaConverter()
    return converter.convert(problem)
