import tracemalloc
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from cofola.solver import solve
from cofola.parser.parser import parse
from dataclasses import dataclass, field, asdict
from typing import List, Any
from pathlib import Path
import json
import logging
import os,resource,multiprocessing

logger = logging.getLogger(__name__)


@dataclass
class CombinationProblem:
    """Data class for a generated combinatorial problem."""
    idx: str
    entity_count: int
    initial_set_bag_count: int
    operator_count: int
    constraint_count: int
    allowed_constraints: List[str]
    allowed_operators: List[str]
    question_type: str
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


@dataclass
class SolveProgress:
    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    total_time_ms: int = 0
    completed: List[str] = field(default_factory=list)
    failed: List[dict] = field(default_factory=list)


class Solve:
    def __init__(self) -> None:
        """
        Purpose: 
        """
        



class ProgressTracker:
    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self._lock = threading.Lock()
        self.progress = self._load()

    def _load(self) -> SolveProgress:
        if self.progress_file.exists():
            with open(self.progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SolveProgress(**data)
        return SolveProgress()

    def save(self):
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.progress), f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.warning(f"Failed to save progress to {self.progress_file}: {e}")

    def mark_success(self, idx: str, solve_time_ms: int):
        with self._lock:
            self.progress.success_count += 1
            self.progress.total_time_ms += solve_time_ms
            self.progress.completed.append(idx)
            self.save()

    def mark_failed(self, idx: str, reason: str, solve_time_ms: int = 0):
        with self._lock:
            self.progress.failed_count += 1
            self.progress.total_time_ms += solve_time_ms
            self.progress.failed.append({"idx": idx, "reason": reason, "solve_time_ms": solve_time_ms})
            self.save()


def scan_problem_files(base_dir: str = "data/problems") -> List[tuple]:
    """Scan all problem_*.json files in base_dir and return list of (file_path, parsed_dict)."""
    base_path = Path(base_dir)
    results = []
    for problem_file in base_path.rglob("problem_*.json"):
        try:
            with open(problem_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                results.append((problem_file, data))
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.warning(f"Skipping file {problem_file}: {e}")
            continue
    return results

def solve_with_limit(cofola_code: str, timeout_seconds: float, memory_limit_mb: float) -> dict:
    """Solve cofola_code with time and memory limits."""
    def target(result_container):
        try:
            tracemalloc.start()
            start_time = time.time()
            solutions = solve(parse(cofola_code))
            end_time = time.time()
            peak_memory_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
            tracemalloc.stop()
            result_container["solution_count"] = solutions
            result_container["solve_time_ms"] = int((end_time - start_time) * 1000)
            result_container["peak_memory_mb"] = peak_memory_mb
            result_container["status"] = "success"
        except Exception as e:
            result_container["status"] = "error"
            result_container["error"] = str(e)

    manager = multiprocessing.Manager()
    result_container = manager.dict()
    process = multiprocessing.Process(target=target, args=(result_container,))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        return {"status": "timeout", "solve_time_ms": timeout_seconds * 1000}
    
    if "peak_memory_mb" in result_container and result_container["peak_memory_mb"] > memory_limit_mb:
        return {"status": "memory_exceeded", "solve_time_ms": result_container.get("solve_time_ms", 0), "peak_memory_mb": result_container["peak_memory_mb"]}

    return dict(result_container)
def solve_single_problem(
    problem_path: Path,
    problem_data: dict,
    output_base: Path,
    timeout_seconds: float,
    memory_limit_mb: float,
    tracker: ProgressTracker,
    problems_base: str = "data/problems"
) -> dict:
    """Solve single problem and write to result file."""
    idx = problem_data["idx"]
    cofola_code = problem_data.get("cofola_code", "")

    if not cofola_code:
        tracker.mark_failed(idx, "empty_cofola_code")
        return {"status": "error", "error": "empty cofola_code"}

    # Solve
    result = solve_with_limit(
        cofola_code, timeout_seconds, memory_limit_mb
    )

    # Build output
    output_data = {**problem_data}
    output_data["solution_count"] = result["solution_count"]
    output_data["solve_time_ms"] = result["solve_time_ms"]
    output_data["status"] = result["status"]
    if "peak_memory_mb" in result:
        output_data["peak_memory_mb"] = result["peak_memory_mb"]
    if "error" in result:
        output_data["error"] = result["error"]

    # Calculate relative path, preserving directory structure
    try:
        rel_path = problem_path.relative_to(Path("data/problems"))
    except ValueError:
        # If not in data/problems, use path relative to problems_base
        rel_path = problem_path.relative_to(Path(problems_base)) if problems_base else Path(problem_path.parent.name)

    output_dir = output_base / rel_path.parent if rel_path.parent != Path('.') else output_base
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"problem_{idx}_solved.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Update progress
    if result["status"] == "success":
        tracker.mark_success(idx, result["solve_time_ms"])
    else:
        tracker.mark_failed(idx, result["status"], result.get("solve_time_ms", 0))

    return result



def run_solver(
    thread_count: int = None,
    timeout_seconds: float = 60.0,
    memory_limit_mb: float = 1024.0,
    output_base: str = "data/single_solved",
    problems_base: str = "data/problems"
):
    """Main entry point."""
    if thread_count is None:
        thread_count = os.cpu_count() * 2

    output_path = Path(output_base)
    progress_file = output_path / "progress.json"

    tracker = ProgressTracker(progress_file)

    # Scan all problem files
    problem_files = scan_problem_files(problems_base)
    tracker.progress.total = len(problem_files)
    tracker.save()

    # Filter completed problems (resume support)
    pending = [
        (p, d) for p, d in problem_files
        if d["idx"] not in tracker.progress.completed
    ]

    print(f"Found {len(problem_files)} problems, {len(pending)} pending")

    # Multi-threaded execution
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        for problem_path, problem_data in pending:
            future = executor.submit(
                solve_single_problem,
                problem_path,
                problem_data,
                output_path,
                timeout_seconds,
                memory_limit_mb,
                tracker,
                problems_base
            )
            futures.append((future, problem_data["idx"]))

        for future, idx in futures:
            future.result()
      

    print(f"Solving complete. Success: {tracker.progress.success_count}, Failed: {tracker.progress.failed_count}")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Multi-threaded Cofola solver")
    parser.add_argument("--threads", type=int, default=2, help="Number of threads, default CPU*2")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-problem timeout (seconds)")
    parser.add_argument("--memory", type=float, default=20480.0, help="Memory limit (MB)")
    parser.add_argument("--output", type=str, default="data/exp_1_problems_solved/ops-CHOOSE", help="Output directory")
    parser.add_argument("--problems", type=str, default="data/exp_1_problems/ops-CHOOSE", help="Problems directory")

    args = parser.parse_args()

    run_solver(
        thread_count=args.threads,
        timeout_seconds=args.timeout,
        memory_limit_mb=args.memory,
        output_base=args.output,
        problems_base=args.problems
    )