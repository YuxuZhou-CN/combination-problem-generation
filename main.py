"""Batch combinatorial problem generator entry point."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import List, Optional, Iterator, Any
from cofola.parser import parse
from dag.expr_node import NodeType
from dag.constraints import (
    CardinalityConstraint, CountConstraint, MemberConstraint,
    NextToConstraint, TogetherConstraint, SubsetConstraint,
    DisjointConstraint, CompositeConstraint, QuantifiedConstraint,
    LessThanConstraint, IndexMemberConstraint, TupleDedupCountSizeConstraint,
    NonEmptyConstraint, PredecessorConstraint, LinearCardinalityConstraint,
    IndexEqualMemberConstraint, Constraint,SequenceCountConstraint
)
from generator import CombinationProblemGenerator
from properties import PropertyTracker
from translator.tree2cofola import TreeToCofolaConverter
from translator.language_generator import LanguageGenerator
from translator.context_manager import ThemeType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Constants and Maps
# ============================================================================

CONSTRAINT_MAP = {
    "cardinality": CardinalityConstraint,
    "count": CountConstraint,
    "member": MemberConstraint,
    "next_to": NextToConstraint,
    "together": TogetherConstraint,
    "subset": SubsetConstraint,
    "disjoint": DisjointConstraint,
    "composite": CompositeConstraint,
    "quantified": QuantifiedConstraint,
    "less_than": LessThanConstraint,
    "index_member": IndexMemberConstraint,
    "tuple_dedup_count": TupleDedupCountSizeConstraint,
    "non_empty": NonEmptyConstraint,
    "predecessor": PredecessorConstraint,
    "linear_cardinality": LinearCardinalityConstraint,
    "index_equal_member": IndexEqualMemberConstraint,
    "SequenceCountConstraint": SequenceCountConstraint
}
OPERATOR_MAP = {name: member for name, member in NodeType.__members__.items()}

# ============================================================================
# Exceptions
# ============================================================================

class ConfigLoaderError(Exception):
    """Configuration loading error."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GeneratorConfig:
    """Single parameter configuration for problem generation."""
    entity_count: int
    operator_count: int
    constraint_count: int
    initial_set_bag_count: int
    entity_multiplicity_range: tuple[int, int]
    allowed_operators: List[NodeType]
    allowed_constraints: List[Constraint]
    num_problems: int
    depth: Optional[int] = None

    @property
    def folder_name(self) -> str:
        ops_str = "-".join(sorted([op.name for op in self.allowed_operators]))
        return f"ops-{ops_str}/entitycount-{self.entity_count}-operatorcount-{self.operator_count}-constraintcount-{self.constraint_count}"


@dataclass
class BatchConfig:
    """Top-level batch configuration."""
    thread_count: int
    output_base_dir: str
    entity_counts: List[int]
    operator_counts: List[int]
    constraint_counts: List[int]
    question_types: List[str]
    initial_set_bag_count: int
    entity_multiplicity_range: tuple[int, int]
    allowed_operators: List[str]
    allowed_constraints: List[str]
    num_problems_per_config: int
    depth: Optional[int] = None

    def expand_configs(self) -> Iterator[GeneratorConfig]:
        """Generate all parameter combinations."""
        for entity_count in self.entity_counts:
            for operator_count in self.operator_counts:
                for constraint_count in self.constraint_counts:
                    for question_type in self.question_types:
                        operators = [OPERATOR_MAP[name] for name in self.allowed_operators if name in OPERATOR_MAP]
                        constraints = [CONSTRAINT_MAP[name]() for name in self.allowed_constraints if name in CONSTRAINT_MAP]
                        yield GeneratorConfig(
                            entity_count=entity_count,
                            operator_count=operator_count,
                            constraint_count=constraint_count,
                            initial_set_bag_count=self.initial_set_bag_count,
                            entity_multiplicity_range=tuple(self.entity_multiplicity_range),
                            allowed_operators=operators,
                            allowed_constraints=constraints,
                            num_problems=self.num_problems_per_config,
                            depth=self.depth,
                        )


# ============================================================================
# Config Loader
# ============================================================================

class ConfigLoader:
    """Loads and parses JSON configuration file."""

    def __init__(self, config_path: str):
        self.config_path = config_path

    def load(self) -> BatchConfig:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise ConfigLoaderError(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ConfigLoaderError(f"Invalid JSON in config file: {e}")
        return BatchConfig(
            thread_count=data.get('thread_count', 4),
            output_base_dir=data.get('output_base_dir', 'data/problems/'),
            entity_counts=data.get('entity_counts', [5, 8, 10]),
            operator_counts=data.get('operator_counts', [2, 3, 4]),
            constraint_counts=data.get('constraint_counts', [1, 2, 3]),
            question_types=data.get('question_types', ['Set', 'Bag']),
            initial_set_bag_count=data.get('initial_set_bag_count', 3),
            entity_multiplicity_range=data.get('entity_multiplicity_range', [2, 4]),
            allowed_operators=data.get('allowed_operators', ['CHOOSE', 'SEQUENCE']),
            allowed_constraints=data.get('allowed_constraints', ['cardinality', 'member']),
            num_problems_per_config=data.get('num_problems_per_config', 50),
            depth=data.get('depth'),
        )


# ============================================================================
# CombinationProblem
# ============================================================================

@dataclass
class CombinationProblem:
    """Data class for a generated combinatorial problem."""
    idx: str
    entity_count: int
    initial_set_bag_count: int
    operator_count: int
    non_det_count: int
    constraint_count: int
    depth: Optional[int]
    allowed_constraints: List[str]
    allowed_operators: List[str]
    constraints: List[str]
    operators: List[str]
    cofola_code: str
    natural_language: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CombinationProblem':
        """Create from dictionary."""
        return cls(**data)


# ============================================================================
# Problem Writer
# ============================================================================

class ProblemWriter:
    """Writes problems to files with thread-safe folder creation."""

    def __init__(self, base_dir: str = "data/problems/"):
        self.base_dir = base_dir
        self._lock = threading.Lock()

    def _ensure_folder(self, folder_name: str) -> str:
        """Create folder if it doesn't exist (thread-safe)."""
        folder_path = os.path.join(self.base_dir, folder_name)
        with self._lock:
            os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def save(self, problem: CombinationProblem, folder_name: str) -> str:
        """Save problem to JSON file."""
        folder_path = self._ensure_folder(folder_name)
        file_path = os.path.join(folder_path, f"problem_{problem.idx}.json")
        with self._lock:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(problem.to_dict(), f, indent=2, ensure_ascii=False)
        return file_path


# ============================================================================
# Batch Problem Generator
# ============================================================================

class BatchProblemGenerator:
    """Multi-threaded batch problem generator."""

    def __init__(self, output_dir: str = "data/problems/"):
        self.output_dir = output_dir
        self.writer = ProblemWriter(base_dir=output_dir)

    def _generate_hash(self, code: str) -> str:
        """Generate short hash from cofola code."""
        return hashlib.sha256(code.encode()).hexdigest()[:16]

    def _extract_operators(self, problem) -> List[str]:
        """Extract operator type names from problem bindings."""
        operators = []
        for name, node in problem.bindings.items():
            if hasattr(node, 'operator') and node.operator:
                operators.append(node.operator.value)
        return operators

    def _extract_constraints(self, problem) -> List[str]:
        """Extract constraint type names from problem bindings."""
        constraints = []
        for binding in problem.bindings.values():
            for constraint in binding.constraints:
                constraint_type = type(constraint).__name__.replace('Constraint', '').lower()
                constraints.append(constraint_type)
        return constraints

    def _count_non_deterministic_operators(self, problem) -> int:
        """Count the number of non-deterministic operations in the problem."""
        if problem is None:
            return 0
        count = 0
        for name, node in problem.bindings.items():
            if node.node_type == NodeType.INDEXED_ACCESS:
                continue    
            if hasattr(node, 'is_deterministic'):
                if not node.is_deterministic:
                    count += 1
        return count

    def generate_single_problem(self, config: GeneratorConfig, max_retries: int = 100) -> Optional[CombinationProblem]:
        """Generate a single problem with depth validation and retry logic."""
        for attempt in range(max_retries):
            gen = CombinationProblemGenerator(
                entity_count=config.entity_count,
                entity_multiplicity_range=config.entity_multiplicity_range,
                initial_set_bag_count=config.initial_set_bag_count,
                allowed_operators=config.allowed_operators,
                operator_count=config.operator_count,
                allowed_constraints=config.allowed_constraints,
                constraint_count=config.constraint_count,
                depth=config.depth,
            )
            tracker = PropertyTracker()
            try:
                problem = gen.generate(tracker)
            except ValueError as e:
                # depth validation failed in generator.py, retry
                continue

            non_det_count = self._count_non_deterministic_operators(problem)
            actual_depth = problem.problem_depth()

            # Depth validation (double check for consistency)
            if config.depth is not None:
                if actual_depth != config.depth:
                    continue  # retry

            converter = TreeToCofolaConverter()
            cofola_code = converter.convert(problem)
            try:
                parse(cofola_code)
            except Exception:
                continue  # retry

            if non_det_count != config.operator_count:
                continue  # retry

            if len(self._extract_constraints(problem)) != config.constraint_count:
                continue  # retry

            lang_gen = LanguageGenerator(theme=ThemeType.MATH_EN)
            natural_language = lang_gen.generate(problem, ThemeType.MATH_EN)

            idx = self._generate_hash(cofola_code)
            operators = self._extract_operators(problem)
            constraints = self._extract_constraints(problem)
            allowed_operators_str = [op.value for op in config.allowed_operators]
            allowed_constraints_str = [type(c).__name__.replace('Constraint', '').lower() for c in config.allowed_constraints]

            return CombinationProblem(
                idx=idx,
                entity_count=config.entity_count,
                non_det_count=non_det_count,
                initial_set_bag_count=config.initial_set_bag_count,
                operator_count=config.operator_count,
                constraint_count=config.constraint_count,
                depth=actual_depth,
                allowed_constraints=allowed_constraints_str,
                allowed_operators=allowed_operators_str,
                constraints=constraints,
                operators=operators,
                cofola_code=cofola_code,
                natural_language=natural_language,
            )
        return None

    def generate_single_config(self, config: GeneratorConfig) -> List[CombinationProblem]:
        """Generate multiple problems for a single configuration."""
        problems = []
        for i in range(config.num_problems):
            problem = self.generate_single_problem(config)
            if problem:
                problems.append(problem)
                self.writer.save(problem, config.folder_name)
        return problems

    def generate_batch(self, batch_config: BatchConfig, progress_callback=None) -> dict:
        """Generate all problems across all configurations using thread pool."""
        total_success = 0
        total_failed = 0
        lock = threading.Lock()

        def worker(config: GeneratorConfig) -> tuple[int, int]:
            success, failed = 0, 0
            for i in range(config.num_problems):
                problem = self.generate_single_problem(config)
                if problem:
                    self.writer.save(problem, config.folder_name)
                    success += 1
                else:
                    failed += 1
                if progress_callback:
                    progress_callback(1)
            return success, failed

        configs = list(batch_config.expand_configs())

        with ThreadPoolExecutor(max_workers=batch_config.thread_count) as executor:
            futures = {executor.submit(worker, config): config for config in configs}
            for future in as_completed(futures):
                s, f = future.result()
                with lock:
                    total_success += s
                    total_failed += f

        return {
            "total_success": total_success,
            "total_failed": total_failed,
            "total_problems": sum(c.num_problems for c in configs),
        }


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Batch generate combinatorial problems')
    parser.add_argument('--config', '-c', type=str, default='config.json', help='Path to JSON configuration file')
    parser.add_argument('--output-dir', '-o', type=str, default=None, help='Override output directory from config')
    parser.add_argument('--single', action='store_true', help='Generate single problem and print to stdout')
    args = parser.parse_args()

    loader = ConfigLoader(args.config)
    config = loader.load()

    if args.output_dir:
        config.output_base_dir = args.output_dir

    logger.info(f"Loaded config: {config.thread_count} threads, {config.num_problems_per_config} problems per config")
    logger.info(f"Parameter combinations: {len(list(config.expand_configs()))}")

    generator = BatchProblemGenerator(output_dir=config.output_base_dir)

    if args.single:
        first_config = next(config.expand_configs())
        logger.info(f"Generating single problem with config: {first_config.folder_name}")
        problem = generator.generate_single_problem(first_config)
        if problem:
            print("=" * 60)
            print("Generated Problem")
            print("=" * 60)
            print(f"Hash: {problem.idx}")
            print(f"Config: {first_config.folder_name}")
            print(f"Cofola code:\n{problem.cofola_code}")
            print(f"\nNatural language:\n{problem.natural_language}")
        else:
            logger.error("Failed to generate problem")
            sys.exit(1)
    else:
        logger.info("Starting batch generation...")

        def progress_callback(count: int):
            print(f"Generated {count} problems...", end='\r')

        summary = generator.generate_batch(config, progress_callback)

        print("\n" + "=" * 60)
        print("Batch Generation Complete")
        print("=" * 60)
        print(f"Total problems: {summary['total_problems']}")
        print(f"Success: {summary['total_success']}")
        print(f"Failed: {summary['total_failed']}")
        print(f"Output directory: {config.output_base_dir}")


if __name__ == "__main__":
    main()
    print(OPERATOR_MAP.keys())