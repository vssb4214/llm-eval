"""Main benchmark runner with workflow orchestration."""

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .builder import create_build_executor
from .config import load_benchmark_config, EnvironmentConfig
from .model_client.factory import create_model_client
from .patcher import create_patch_applier
from .prompts import SYSTEM_PROMPT, create_user_prompt, create_retrieval_prompt
from .repo_summary import create_repo_tree
from .retrieval import create_retriever
from .scorer import create_scorer
from .types import (
    BenchmarkConfig, ModelConfig, TestCase, RunResult, ModelOutput,
    BuildResult, PatchResult, ScoringMetrics
)
from .utils import safe_json_parse
from .vcs import create_repository_manager


class BenchmarkRunner:
    """Orchestrates the complete benchmark workflow."""
    
    def __init__(
        self,
        benchmark_config: BenchmarkConfig,
        models: List[ModelConfig],
        env_config: EnvironmentConfig
    ):
        self.config = benchmark_config
        self.models = models
        self.env_config = env_config
        self.console = Console()
        self.scorer = create_scorer()
        self.repo_manager = create_repository_manager(
            self.config.output_dir / "workspace"
        )
        self.build_executor = create_build_executor(self.config.timeout_seconds)
    
    async def run_benchmark(self) -> List[RunResult]:
        """Run the complete benchmark across all models and test cases."""
        self.console.print("[bold blue]Starting Java Maintenance Agent Benchmark[/bold blue]")
        
        # Load test cases
        test_cases = self._load_test_cases()
        self.console.print(f"Loaded {len(test_cases)} test cases")
        
        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run all combinations
        all_results = []
        total_runs = len(self.models) * len(test_cases) * len(self.config.seeds)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Running benchmark...", total=total_runs)
            
            for model_config in self.models:
                for test_case in test_cases:
                    for seed in self.config.seeds:
                        try:
                            result = await self._run_single_case(
                                model_config, test_case, seed, progress, task
                            )
                            all_results.append(result)
                        except Exception as e:
                            self.console.print(f"[red]Error in {model_config.name} on {test_case.case_id}: {str(e)}[/red]")
                            # Create error result
                            error_result = RunResult(
                                run_id=str(uuid.uuid4()),
                                case_id=test_case.case_id,
                                model_name=model_config.name,
                                model_family=model_config.family.value,
                                seed=seed,
                                temperature=self.config.temperature,
                                suite=test_case.suite,
                                project=test_case.project,
                                bug_sha=test_case.bug_sha,
                                build_system=test_case.build_system.value,
                                notes=f"Error: {str(e)}"
                            )
                            all_results.append(error_result)
                        
                        progress.advance(task)
        
        # Save results
        self._save_results(all_results)
        
        self.console.print(f"[green]Benchmark completed! {len(all_results)} runs completed.[/green]")
        return all_results
    
    async def _run_single_case(
        self,
        model_config: ModelConfig,
        test_case: TestCase,
        seed: int,
        progress: Progress,
        task_id
    ) -> RunResult:
        """Run a single model on a single test case."""
        run_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Update progress
        progress.update(
            task_id,
            description=f"Running {model_config.name} on {test_case.case_id} (seed {seed})"
        )
        
        # Create artifacts directory
        artifacts_dir = self.config.output_dir / "artifacts" / f"{run_id}"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize result
        result = RunResult(
            run_id=run_id,
            case_id=test_case.case_id,
            model_name=model_config.name,
            model_family=model_config.family.value,
            seed=seed,
            temperature=self.config.temperature,
            suite=test_case.suite,
            project=test_case.project,
            bug_sha=test_case.bug_sha,
            build_system=test_case.build_system.value,
            truth_file=test_case.truth_file,
            truth_line=test_case.truth_line,
            artifacts_dir=artifacts_dir
        )
        
        try:
            # Step 1: Setup repository
            repo_path = await self._setup_repository(test_case)
            
            # Step 2: Generate model response
            model_response = await self._generate_model_response(
                model_config, test_case, repo_path, artifacts_dir
            )
            
            if model_response:
                result.model_output = model_response["output"]
                result.model_output_raw = model_response["raw"]
                result.input_tokens = model_response["input_tokens"]
                result.output_tokens = model_response["output_tokens"]
                result.total_tokens = model_response["total_tokens"]
                result.cost_usd = model_response["cost"]
                
                # Step 3: Apply patch and test
                if result.model_output:
                    patch_result = await self._apply_patch_and_test(
                        result.model_output, repo_path, test_case, artifacts_dir
                    )
                    result.patch_result = patch_result["patch_result"]
                    result.build_result = patch_result["build_result"]
            
            # Step 4: Score the result
            result.scoring = self.scorer.score_run(result, test_case)
            
        except Exception as e:
            result.notes = f"Error: {str(e)}"
            self.console.print(f"[yellow]Warning: {str(e)}[/yellow]")
        
        finally:
            # Cleanup
            self.repo_manager.cleanup_case(test_case.case_id)
        
        # Calculate total latency
        result.latency_sec = time.time() - start_time
        
        return result
    
    async def _setup_repository(self, test_case: TestCase) -> Path:
        """Setup repository for a test case."""
        repo_path = self.repo_manager.clone_repository(
            test_case.repo_url, test_case.case_id
        )
        self.repo_manager.checkout_commit(repo_path, test_case.bug_sha)
        return repo_path
    
    async def _generate_model_response(
        self,
        model_config: ModelConfig,
        test_case: TestCase,
        repo_path: Path,
        artifacts_dir: Path
    ) -> Optional[Dict]:
        """Generate model response for a test case."""
        try:
            # Create model client
            model_client = create_model_client(model_config, self.env_config)
            
            # Create repository tree
            repo_tree = create_repo_tree(
                repo_path, max_entries=self.config.max_repo_tree_entries
            )
            
            # Create prompt
            if self.config.enable_retrieval:
                # Use retrieval-augmented prompt
                retriever = create_retriever(repo_path)
                retrieved_snippets = retriever.retrieve_for_logs(
                    test_case.logs, max_files=3
                )
                user_prompt = create_retrieval_prompt(
                    test_case, repo_tree, test_case.logs, retrieved_snippets,
                    self.config.max_repo_tree_entries, self.config.max_log_length
                )
            else:
                # Use standard prompt
                user_prompt = create_user_prompt(
                    test_case, repo_tree, test_case.logs,
                    self.config.max_repo_tree_entries, self.config.max_log_length
                )
            
            # Save prompts as artifacts
            with open(artifacts_dir / "system_prompt.txt", 'w') as f:
                f.write(SYSTEM_PROMPT)
            with open(artifacts_dir / "user_prompt.txt", 'w') as f:
                f.write(user_prompt)
            
            # Generate response
            response = await model_client.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=self.config.temperature
            )
            
            # Save raw response
            with open(artifacts_dir / "model_response_raw.txt", 'w') as f:
                f.write(response.content)
            
            # Parse JSON response
            model_output = safe_json_parse(response.content)
            
            if model_output:
                # Save parsed output
                with open(artifacts_dir / "model_output.json", 'w') as f:
                    json.dump(model_output.dict(), f, indent=2)
            
            # Calculate cost
            cost = model_client.estimate_cost(response)
            
            # Close client
            await model_client.close()
            
            return {
                "output": model_output,
                "raw": response.content,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "cost": cost
            }
            
        except Exception as e:
            self.console.print(f"[yellow]Model generation failed: {str(e)}[/yellow]")
            return None
    
    async def _apply_patch_and_test(
        self,
        model_output: ModelOutput,
        repo_path: Path,
        test_case: TestCase,
        artifacts_dir: Path
    ) -> Dict:
        """Apply patch and run tests."""
        # Create patch applier
        patch_applier = create_patch_applier(
            self.repo_manager, self.config.allow_build_file_edits
        )
        
        # Save patch
        patch_file = patch_applier.save_patch_artifact(
            model_output.patch_unified_diff, artifacts_dir
        )
        
        # Apply patch
        patch_result = patch_applier.apply_patch(
            repo_path, model_output.patch_unified_diff, test_case.case_id
        )
        
        # Run build and tests
        build_result = None
        if patch_result.apply_success:
            build_result = await self.build_executor.execute_build_and_test(
                repo_path, test_case.build_system, test_case.failing_test
            )
        
        return {
            "patch_result": patch_result,
            "build_result": build_result
        }
    
    def _load_test_cases(self) -> List[TestCase]:
        """Load all test cases from the cases directory."""
        test_cases = []
        
        for case_dir in self.config.cases_dir.iterdir():
            if case_dir.is_dir():
                try:
                    test_case = TestCase.from_directory(case_dir)
                    test_cases.append(test_case)
                except Exception as e:
                    self.console.print(f"[yellow]Failed to load case {case_dir.name}: {str(e)}[/yellow]")
        
        return test_cases
    
    def _save_results(self, results: List[RunResult]):
        """Save results to CSV and JSONL files."""
        # Save CSV
        csv_data = [result.to_csv_row() for result in results]
        df = pd.DataFrame(csv_data)
        csv_file = self.config.output_dir / "results.csv"
        df.to_csv(csv_file, index=False)
        
        # Save JSONL
        jsonl_file = self.config.output_dir / "results.jsonl"
        with open(jsonl_file, 'w') as f:
            for result in results:
                f.write(result.json() + '\n')
        
        self.console.print(f"Results saved to {csv_file} and {jsonl_file}")


def create_benchmark_runner(
    benchmark_config: BenchmarkConfig,
    models: List[ModelConfig],
    env_config: EnvironmentConfig
) -> BenchmarkRunner:
    """Create a benchmark runner instance."""
    return BenchmarkRunner(benchmark_config, models, env_config)
