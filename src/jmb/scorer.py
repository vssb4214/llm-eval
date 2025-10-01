"""Comprehensive scoring system for benchmark results."""

import json
from typing import Dict, List, Optional, Tuple

from .types import (
    ScoringMetrics, RunResult, ModelOutput, BuildResult, PatchResult,
    TestCase
)


class BenchmarkScorer:
    """Scores benchmark results across multiple dimensions."""
    
    def __init__(self):
        self.localization_tolerance = 5  # ±5 lines tolerance for localization
    
    def score_run(
        self,
        run_result: RunResult,
        test_case: TestCase
    ) -> ScoringMetrics:
        """Score a complete run result."""
        
        # Fix Success (55 points)
        fix_success_score = self._score_fix_success(
            run_result.build_result,
            run_result.patch_result
        )
        
        # Localization (20 points)
        localization_score = self._score_localization(
            run_result.model_output,
            test_case
        )
        
        # Operations (15 points)
        ops_score = self._score_operations(run_result)
        
        # Reliability (10 points)
        reliability_score = self._score_reliability(
            run_result.model_output,
            run_result.patch_result
        )
        
        # Calculate composite scores
        total_score = fix_success_score + localization_score + ops_score + reliability_score
        
        return ScoringMetrics(
            # Fix Success components
            build_pass=run_result.build_result.build_pass if run_result.build_result else False,
            test_pass=run_result.build_result.test_pass if run_result.build_result else False,
            minimality_score=self._calculate_minimality_score(run_result.patch_result),
            
            # Localization components
            localization_top1_correct=self._check_top1_localization(
                run_result.model_output, test_case
            ),
            localization_top3_hit=self._check_top3_localization(
                run_result.model_output, test_case
            ),
            
            # Operations components
            latency_score=self._calculate_latency_score(run_result.latency_sec),
            token_efficiency_score=self._calculate_token_efficiency_score(run_result),
            
            # Reliability components
            json_valid=run_result.model_output is not None,
            patch_valid=run_result.patch_result.apply_success if run_result.patch_result else False,
            
            # Composite scores
            fix_success_score=fix_success_score,
            localization_score=localization_score,
            ops_score=ops_score,
            reliability_score=reliability_score,
            total_score=total_score
        )
    
    def _score_fix_success(self, build_result: Optional[BuildResult], patch_result: Optional[PatchResult]) -> float:
        """Score fix success (55 points total)."""
        score = 0.0
        
        # Build success (20 points)
        if build_result and build_result.build_pass:
            score += 20.0
        
        # Test success (25 points)
        if build_result and build_result.test_pass:
            score += 25.0
        
        # Minimality (10 points)
        score += self._calculate_minimality_score(patch_result)
        
        return score
    
    def _score_localization(self, model_output: Optional[ModelOutput], test_case: TestCase) -> float:
        """Score localization accuracy (20 points total)."""
        score = 0.0
        
        if not model_output or not model_output.localization:
            return score
        
        # Top-1 localization (12 points)
        if self._check_top1_localization(model_output, test_case):
            score += 12.0
        
        # Top-3 localization (8 points)
        if self._check_top3_localization(model_output, test_case):
            score += 8.0
        
        return score
    
    def _score_operations(self, run_result: RunResult) -> float:
        """Score operational efficiency (15 points total)."""
        score = 0.0
        
        # Latency score (10 points)
        score += self._calculate_latency_score(run_result.latency_sec)
        
        # Token efficiency score (5 points)
        score += self._calculate_token_efficiency_score(run_result)
        
        return score
    
    def _score_reliability(self, model_output: Optional[ModelOutput], patch_result: Optional[PatchResult]) -> float:
        """Score reliability (10 points total)."""
        score = 0.0
        
        # JSON validity (5 points)
        if model_output is not None:
            score += 5.0
        
        # Patch validity (5 points)
        if patch_result and patch_result.apply_success:
            score += 5.0
        
        return score
    
    def _calculate_minimality_score(self, patch_result: Optional[PatchResult]) -> float:
        """Calculate minimality score (10 points max)."""
        if not patch_result:
            return 0.0
        
        # Base score for successful patch
        base_score = 5.0
        
        # Penalty for excessive changes
        files_penalty = min(2.0, patch_result.files_touched * 0.5)
        loc_penalty = min(3.0, (patch_result.loc_added + patch_result.loc_deleted) * 0.1)
        
        # Bonus for very minimal changes
        if patch_result.files_touched == 1 and (patch_result.loc_added + patch_result.loc_deleted) <= 3:
            base_score += 2.0
        
        score = max(0.0, base_score - files_penalty - loc_penalty)
        return min(10.0, score)
    
    def _check_top1_localization(self, model_output: Optional[ModelOutput], test_case: TestCase) -> bool:
        """Check if top-1 localization is correct."""
        if not model_output or not model_output.localization:
            return False
        
        if not test_case.truth_file or not test_case.truth_line:
            return False
        
        top_localization = model_output.localization[0]
        
        # Check file match
        if top_localization.file != test_case.truth_file:
            return False
        
        # Check line match with tolerance
        line_diff = abs(top_localization.line - test_case.truth_line)
        return line_diff <= self.localization_tolerance
    
    def _check_top3_localization(self, model_output: Optional[ModelOutput], test_case: TestCase) -> bool:
        """Check if any of top-3 localizations are correct."""
        if not model_output or not model_output.localization:
            return False
        
        if not test_case.truth_file or not test_case.truth_line:
            return False
        
        # Check top 3 localizations
        for localization in model_output.localization[:3]:
            # Check file match
            if localization.file == test_case.truth_file:
                # Check line match with tolerance
                line_diff = abs(localization.line - test_case.truth_line)
                if line_diff <= self.localization_tolerance:
                    return True
        
        return False
    
    def _calculate_latency_score(self, latency_seconds: float) -> float:
        """Calculate latency score (10 points max)."""
        # Target: 120 seconds for full score
        # Linear decay after 120 seconds
        if latency_seconds <= 120.0:
            return 10.0
        else:
            # Decay to 0 at 600 seconds (10 minutes)
            decay_rate = 10.0 / (600.0 - 120.0)
            score = 10.0 - (latency_seconds - 120.0) * decay_rate
            return max(0.0, score)
    
    def _calculate_token_efficiency_score(self, run_result: RunResult) -> float:
        """Calculate token efficiency score (5 points max)."""
        if run_result.total_tokens == 0:
            return 0.0
        
        # Target: 2000 tokens for full score
        # Linear decay after 2000 tokens
        if run_result.total_tokens <= 2000:
            return 5.0
        else:
            # Decay to 0 at 8000 tokens
            decay_rate = 5.0 / (8000.0 - 2000.0)
            score = 5.0 - (run_result.total_tokens - 2000.0) * decay_rate
            return max(0.0, score)
    
    def calculate_aggregate_scores(self, results: List[RunResult]) -> Dict[str, float]:
        """Calculate aggregate scores across multiple runs."""
        if not results:
            return {}
        
        # Group by model
        model_scores = {}
        for result in results:
            model_name = result.model_name
            if model_name not in model_scores:
                model_scores[model_name] = []
            
            # Get scoring from result (assuming it's already calculated)
            if result.scoring:
                model_scores[model_name].append(result.scoring.total_score)
        
        # Calculate statistics
        aggregate = {}
        for model_name, scores in model_scores.items():
            if scores:
                aggregate[model_name] = {
                    "mean": sum(scores) / len(scores),
                    "median": sorted(scores)[len(scores) // 2],
                    "min": min(scores),
                    "max": max(scores),
                    "count": len(scores)
                }
        
        return aggregate
    
    def calculate_success_rates(self, results: List[RunResult]) -> Dict[str, Dict[str, float]]:
        """Calculate success rates for different metrics."""
        if not results:
            return {}
        
        # Group by model
        model_results = {}
        for result in results:
            model_name = result.model_name
            if model_name not in model_results:
                model_results[model_name] = []
            model_results[model_name].append(result)
        
        success_rates = {}
        for model_name, model_runs in model_results.items():
            total_runs = len(model_runs)
            if total_runs == 0:
                continue
            
            # Count successes
            build_successes = sum(1 for r in model_runs if r.build_result and r.build_result.build_pass)
            test_successes = sum(1 for r in model_runs if r.build_result and r.build_result.test_pass)
            patch_successes = sum(1 for r in model_runs if r.patch_result and r.patch_result.apply_success)
            json_successes = sum(1 for r in model_runs if r.model_output is not None)
            
            success_rates[model_name] = {
                "build_success_rate": build_successes / total_runs,
                "test_success_rate": test_successes / total_runs,
                "patch_success_rate": patch_successes / total_runs,
                "json_success_rate": json_successes / total_runs,
                "total_runs": total_runs
            }
        
        return success_rates


def create_scorer() -> BenchmarkScorer:
    """Create a benchmark scorer instance."""
    return BenchmarkScorer()
