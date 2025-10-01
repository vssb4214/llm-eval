"""Pydantic models and type definitions for the benchmark system."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class BuildSystem(str, Enum):
    """Supported build systems."""
    MAVEN = "maven"
    GRADLE = "gradle"


class ModelFamily(str, Enum):
    """Supported model families."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMMA = "gemma"
    STARCODER = "starcoder"
    LOCAL = "local"


class LocalizationEntry(BaseModel):
    """A single localization entry from model output."""
    file: str = Field(..., description="File path relative to repo root")
    line: int = Field(..., ge=1, description="Line number (1-indexed)")
    reason: str = Field(..., description="Reasoning for this localization")


class ModelOutput(BaseModel):
    """Expected JSON output from models."""
    localization: List[LocalizationEntry] = Field(
        ..., min_items=1, description="List of localized fault locations"
    )
    patch_unified_diff: str = Field(..., description="Unified diff patch")
    notes: Optional[str] = Field(None, description="Additional notes from model")

    @validator('localization')
    def validate_localization(cls, v):
        if not v:
            raise ValueError("At least one localization entry is required")
        return v


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    name: str = Field(..., description="Model name/identifier")
    family: ModelFamily = Field(..., description="Model family")
    endpoint: str = Field(..., description="API endpoint URL")
    api_key_env: Optional[str] = Field(None, description="Environment variable for API key")
    model: str = Field(..., description="Model identifier for API")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(4096, ge=1, le=32768, description="Maximum tokens to generate")
    cost_per_1k_input: float = Field(0.0, ge=0.0, description="Cost per 1K input tokens")
    cost_per_1k_output: float = Field(0.0, ge=0.0, description="Cost per 1K output tokens")


class TestCase(BaseModel):
    """A single test case for benchmarking."""
    case_id: str = Field(..., description="Unique case identifier")
    suite: str = Field(..., description="Test suite name")
    project: str = Field(..., description="Project name")
    repo_url: str = Field(..., description="Git repository URL")
    bug_sha: str = Field(..., description="Git commit SHA with the bug")
    build_system: BuildSystem = Field(..., description="Build system type")
    logs: str = Field(..., description="Build/test failure logs")
    failing_test: Optional[str] = Field(None, description="Specific failing test name")
    truth_file: Optional[str] = Field(None, description="Ground truth file path")
    truth_line: Optional[int] = Field(None, description="Ground truth line number")
    case_dir: Path = Field(..., description="Directory containing case files")

    @classmethod
    def from_directory(cls, case_dir: Path) -> "TestCase":
        """Load test case from directory structure."""
        case_id = case_dir.name
        
        # Read required files
        repo_url = (case_dir / "repo_url.txt").read_text().strip()
        bug_sha = (case_dir / "bug_sha.txt").read_text().strip()
        build_system = BuildSystem((case_dir / "build_system.txt").read_text().strip())
        logs = (case_dir / "logs.txt").read_text()
        
        # Read optional files
        failing_test = None
        failing_test_file = case_dir / "failing_test.txt"
        if failing_test_file.exists():
            failing_test = failing_test_file.read_text().strip()
        
        truth_file = None
        truth_file_path = case_dir / "truth_file.txt"
        if truth_file_path.exists():
            truth_file = truth_file_path.read_text().strip()
        
        truth_line = None
        truth_line_file = case_dir / "truth_line.txt"
        if truth_line_file.exists():
            truth_line = int(truth_line_file.read_text().strip())
        
        # Extract suite and project from case_id or repo_url
        suite = case_id.split('-')[0] if '-' in case_id else "unknown"
        project = repo_url.split('/')[-1].replace('.git', '') if repo_url else "unknown"
        
        return cls(
            case_id=case_id,
            suite=suite,
            project=project,
            repo_url=repo_url,
            bug_sha=bug_sha,
            build_system=build_system,
            logs=logs,
            failing_test=failing_test,
            truth_file=truth_file,
            truth_line=truth_line,
            case_dir=case_dir
        )


class BuildResult(BaseModel):
    """Result of build and test execution."""
    build_pass: bool = Field(..., description="Whether build succeeded")
    test_pass: bool = Field(..., description="Whether tests passed")
    build_duration: float = Field(..., description="Build duration in seconds")
    test_duration: float = Field(..., description="Test duration in seconds")
    build_output: str = Field(..., description="Build stdout/stderr")
    test_output: str = Field(..., description="Test stdout/stderr")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class PatchResult(BaseModel):
    """Result of patch application."""
    apply_success: bool = Field(..., description="Whether patch applied successfully")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    files_touched: int = Field(0, description="Number of files modified")
    loc_added: int = Field(0, description="Lines of code added")
    loc_deleted: int = Field(0, description="Lines of code deleted")
    loc_modified: int = Field(0, description="Lines of code modified")
    build_files_modified: bool = Field(False, description="Whether build files were modified")


class ScoringMetrics(BaseModel):
    """Comprehensive scoring metrics for a single run."""
    # Fix Success (55 points)
    build_pass: bool = Field(False, description="Build success (20 points)")
    test_pass: bool = Field(False, description="Test success (25 points)")
    minimality_score: float = Field(0.0, ge=0.0, le=10.0, description="Minimality score (10 points)")
    
    # Localization (20 points)
    localization_top1_correct: bool = Field(False, description="Top-1 localization correct (12 points)")
    localization_top3_hit: bool = Field(False, description="Top-3 localization hit (8 points)")
    
    # Operations (15 points)
    latency_score: float = Field(0.0, ge=0.0, le=10.0, description="Latency score (10 points)")
    token_efficiency_score: float = Field(0.0, ge=0.0, le=5.0, description="Token efficiency score (5 points)")
    
    # Reliability (10 points)
    json_valid: bool = Field(False, description="JSON output valid (5 points)")
    patch_valid: bool = Field(False, description="Patch application valid (5 points)")
    
    # Composite scores
    fix_success_score: float = Field(0.0, ge=0.0, le=55.0, description="Fix success composite score")
    localization_score: float = Field(0.0, ge=0.0, le=20.0, description="Localization composite score")
    ops_score: float = Field(0.0, ge=0.0, le=15.0, description="Operations composite score")
    reliability_score: float = Field(0.0, ge=0.0, le=10.0, description="Reliability composite score")
    total_score: float = Field(0.0, ge=0.0, le=100.0, description="Total composite score")


class RunResult(BaseModel):
    """Complete result for a single model run on a test case."""
    # Metadata
    run_id: str = Field(..., description="Unique run identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Run timestamp")
    case_id: str = Field(..., description="Test case identifier")
    model_name: str = Field(..., description="Model name")
    model_family: str = Field(..., description="Model family")
    seed: int = Field(..., description="Random seed used")
    temperature: float = Field(..., description="Temperature used")
    
    # Input data
    suite: str = Field(..., description="Test suite")
    project: str = Field(..., description="Project name")
    bug_sha: str = Field(..., description="Bug commit SHA")
    build_system: str = Field(..., description="Build system")
    
    # Model output
    model_output: Optional[ModelOutput] = Field(None, description="Parsed model output")
    model_output_raw: Optional[str] = Field(None, description="Raw model output")
    json_parse_error: Optional[str] = Field(None, description="JSON parsing error")
    
    # Localization results
    pred_file: Optional[str] = Field(None, description="Predicted file")
    pred_line: Optional[int] = Field(None, description="Predicted line")
    truth_file: Optional[str] = Field(None, description="Ground truth file")
    truth_line: Optional[int] = Field(None, description="Ground truth line")
    
    # Patch and build results
    patch_result: Optional[PatchResult] = Field(None, description="Patch application result")
    build_result: Optional[BuildResult] = Field(None, description="Build and test result")
    
    # Performance metrics
    latency_sec: float = Field(0.0, description="Total latency in seconds")
    input_tokens: int = Field(0, description="Input token count")
    output_tokens: int = Field(0, description="Output token count")
    total_tokens: int = Field(0, description="Total token count")
    cost_usd: float = Field(0.0, description="Estimated cost in USD")
    
    # Scoring
    scoring: Optional[ScoringMetrics] = Field(None, description="Scoring metrics")
    
    # Artifacts
    artifacts_dir: Optional[Path] = Field(None, description="Directory containing artifacts")
    retries: int = Field(0, description="Number of retries attempted")
    tool_call_failures: int = Field(0, description="Number of tool call failures")
    notes: Optional[str] = Field(None, description="Additional notes")

    def to_csv_row(self) -> Dict[str, Any]:
        """Convert to CSV row format."""
        return {
            "run_id": self.run_id,
            "timestamp_iso": self.timestamp.isoformat(),
            "case_id": self.case_id,
            "suite": self.suite,
            "project": self.project,
            "bug_sha": self.bug_sha,
            "build_system": self.build_system,
            "model_name": self.model_name,
            "model_family": self.model_family,
            "model_size_b": 0,  # TODO: Add model size estimation
            "endpoint": "",  # TODO: Add endpoint info
            "temperature": self.temperature,
            "max_tokens": 0,  # TODO: Add max_tokens
            "seed": self.seed,
            "localization_top1_correct": self.scoring.localization_top1_correct if self.scoring else False,
            "localization_top3_hit": self.scoring.localization_top3_hit if self.scoring else False,
            "pred_file": self.pred_file,
            "pred_line": self.pred_line,
            "truth_file": self.truth_file,
            "truth_line": self.truth_line,
            "stacktrace_used": True,  # TODO: Add stacktrace usage flag
            "retrieval_used": False,  # TODO: Add retrieval usage flag
            "retrieval_docs_n": 0,  # TODO: Add retrieval doc count
            "patch_generated": self.model_output is not None,
            "patch_apply_ok": self.patch_result.apply_success if self.patch_result else False,
            "build_pass": self.build_result.build_pass if self.build_result else False,
            "test_pass": self.build_result.test_pass if self.build_result else False,
            "files_touched": self.patch_result.files_touched if self.patch_result else 0,
            "loc_added": self.patch_result.loc_added if self.patch_result else 0,
            "loc_deleted": self.patch_result.loc_deleted if self.patch_result else 0,
            "loc_modified": self.patch_result.loc_modified if self.patch_result else 0,
            "latency_sec": self.latency_sec,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "retries": self.retries,
            "tool_call_failures": self.tool_call_failures,
            "notes": self.notes,
            "artifacts_dir": str(self.artifacts_dir) if self.artifacts_dir else "",
        }


class BenchmarkConfig(BaseModel):
    """Configuration for running benchmarks."""
    cases_dir: Path = Field(..., description="Directory containing test cases")
    models_config: Path = Field(..., description="Path to models.yaml")
    output_dir: Path = Field(..., description="Output directory for results")
    seeds: List[int] = Field(default=[0], description="Random seeds to use")
    temperature: float = Field(0.2, description="Temperature for model generation")
    max_retries: int = Field(1, description="Maximum retries per run")
    timeout_seconds: int = Field(600, description="Timeout per run in seconds")
    allow_build_file_edits: bool = Field(False, description="Allow editing build files")
    enable_retrieval: bool = Field(False, description="Enable retrieval augmentation")
    max_repo_tree_entries: int = Field(1000, description="Maximum repo tree entries")
    max_log_length: int = Field(10000, description="Maximum log length")
