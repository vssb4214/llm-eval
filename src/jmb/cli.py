"""CLI interface for the Java Maintenance Agent Benchmark."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import load_benchmark_config, find_env_file
from .report import create_report_generator
from .runner import create_benchmark_runner
from .types import TestCase

app = typer.Typer(
    name="jmb",
    help="Java Maintenance Agent Benchmark - A→Z Automation",
    rich_markup_mode="rich"
)
console = Console()


@app.command()
def run(
    cases: Path = typer.Option(
        Path("bench/cases"),
        "--cases",
        "-c",
        help="Directory containing test cases"
    ),
    models: Path = typer.Option(
        Path("models.yaml"),
        "--models",
        "-m",
        help="Path to models configuration file"
    ),
    output: Path = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory for results (default: results/run-<timestamp>)"
    ),
    seeds: List[int] = typer.Option(
        [0, 1, 2],
        "--seeds",
        "-s",
        help="Random seeds to use for evaluation"
    ),
    temperature: float = typer.Option(
        0.2,
        "--temp",
        "-t",
        help="Temperature for model generation"
    ),
    retry: int = typer.Option(
        1,
        "--retry",
        "-r",
        help="Maximum retries per run"
    ),
    timeout: int = typer.Option(
        600,
        "--timeout",
        help="Timeout per run in seconds"
    ),
    allow_build_edits: bool = typer.Option(
        False,
        "--allow-build-file-edits",
        help="Allow editing build files (pom.xml, build.gradle)"
    ),
    enable_retrieval: bool = typer.Option(
        False,
        "--rag",
        help="Enable retrieval augmentation"
    ),
    max_repo_entries: int = typer.Option(
        1000,
        "--max-repo-entries",
        help="Maximum repository tree entries"
    ),
    max_log_length: int = typer.Option(
        10000,
        "--max-log-length",
        help="Maximum log length"
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env",
        help="Path to .env file (auto-detected if not provided)"
    )
):
    """Run the Java Maintenance Agent Benchmark."""
    
    # Auto-detect env file if not provided
    if env_file is None:
        env_file = find_env_file()
    
    # Set default output directory
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = Path(f"results/run-{timestamp}")
    
    console.print(f"[bold blue]Java Maintenance Agent Benchmark[/bold blue]")
    console.print(f"Cases: {cases}")
    console.print(f"Models: {models}")
    console.print(f"Output: {output}")
    console.print(f"Seeds: {seeds}")
    console.print(f"Temperature: {temperature}")
    console.print(f"Retries: {retry}")
    console.print(f"Timeout: {timeout}s")
    console.print(f"Allow build edits: {allow_build_edits}")
    console.print(f"Enable retrieval: {enable_retrieval}")
    console.print()
    
    # Load configuration
    try:
        benchmark_config, model_configs, env_config = load_benchmark_config(
            cases_dir=cases,
            models_file=models,
            output_dir=output,
            env_file=env_file,
            seeds=seeds,
            temperature=temperature,
            max_retries=retry,
            timeout_seconds=timeout,
            allow_build_file_edits=allow_build_edits,
            enable_retrieval=enable_retrieval,
            max_repo_tree_entries=max_repo_entries,
            max_log_length=max_log_length
        )
    except Exception as e:
        console.print(f"[red]Configuration error: {str(e)}[/red]")
        raise typer.Exit(1)
    
    # Validate configuration
    if not model_configs:
        console.print("[red]No valid model configurations found![/red]")
        console.print("Please check your models.yaml file and API keys.")
        raise typer.Exit(1)
    
    console.print(f"[green]Loaded {len(model_configs)} model configurations[/green]")
    for model in model_configs:
        console.print(f"  - {model.name} ({model.family.value})")
    
    # Create and run benchmark
    try:
        runner = create_benchmark_runner(benchmark_config, model_configs, env_config)
        results = asyncio.run(runner.run_benchmark())
        
        console.print(f"[green]Benchmark completed! {len(results)} runs finished.[/green]")
        
    except KeyboardInterrupt:
        console.print("[yellow]Benchmark interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Benchmark failed: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def report(
    input_dir: Path = typer.Argument(
        ...,
        help="Input directory containing benchmark results"
    ),
    output: Path = typer.Option(
        None,
        "--out",
        "-o",
        help="Output path for report (default: <input_dir>/report.md)"
    ),
    html: bool = typer.Option(
        False,
        "--html",
        help="Generate HTML report in addition to Markdown"
    ),
    template_dir: Path = typer.Option(
        Path("templates"),
        "--templates",
        help="Directory containing report templates"
    )
):
    """Generate a benchmark report from results."""
    
    if output is None:
        output = input_dir / "report.md"
    
    console.print(f"[bold blue]Generating benchmark report[/bold blue]")
    console.print(f"Input: {input_dir}")
    console.print(f"Output: {output}")
    console.print(f"HTML: {html}")
    console.print()
    
    # Check if results exist
    results_csv = input_dir / "results.csv"
    if not results_csv.exists():
        console.print(f"[red]Results file not found: {results_csv}[/red]")
        raise typer.Exit(1)
    
    try:
        # Load results
        import pandas as pd
        df = pd.read_csv(results_csv)
        
        # Convert to RunResult objects (simplified)
        from .types import RunResult
        results = []
        for _, row in df.iterrows():
            # Create a minimal RunResult for reporting
            result = RunResult(
                run_id=row['run_id'],
                case_id=row['case_id'],
                model_name=row['model_name'],
                model_family=row['model_family'],
                seed=row['seed'],
                temperature=row['temperature'],
                suite=row['suite'],
                project=row['project'],
                bug_sha=row['bug_sha'],
                build_system=row['build_system']
            )
            results.append(result)
        
        # Create dummy models and test cases for report generation
        models = []
        test_cases = []
        
        # Generate report
        report_generator = create_report_generator(template_dir)
        report_path = report_generator.generate_report(
            results=results,
            models=models,
            test_cases=test_cases,
            output_path=output,
            generate_html=html
        )
        
        console.print(f"[green]Report generated: {report_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Report generation failed: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    cases: Path = typer.Option(
        Path("bench/cases"),
        "--cases",
        "-c",
        help="Directory containing test cases"
    )
):
    """Validate test case structure and configuration."""
    
    console.print(f"[bold blue]Validating test cases in {cases}[/bold blue]")
    
    if not cases.exists():
        console.print(f"[red]Cases directory not found: {cases}[/red]")
        raise typer.Exit(1)
    
    # Find all case directories
    case_dirs = [d for d in cases.iterdir() if d.is_dir()]
    
    if not case_dirs:
        console.print("[yellow]No test cases found[/yellow]")
        return
    
    console.print(f"Found {len(case_dirs)} test cases")
    console.print()
    
    # Validate each case
    valid_cases = 0
    invalid_cases = 0
    
    for case_dir in case_dirs:
        console.print(f"Validating {case_dir.name}...")
        
        try:
            test_case = TestCase.from_directory(case_dir)
            console.print(f"  [green]✓ Valid[/green]")
            console.print(f"    Project: {test_case.project}")
            console.print(f"    Build: {test_case.build_system.value}")
            console.print(f"    Repo: {test_case.repo_url}")
            console.print(f"    SHA: {test_case.bug_sha}")
            valid_cases += 1
            
        except Exception as e:
            console.print(f"  [red]✗ Invalid: {str(e)}[/red]")
            invalid_cases += 1
        
        console.print()
    
    # Summary
    console.print(f"[bold]Validation Summary[/bold]")
    console.print(f"Valid cases: {valid_cases}")
    console.print(f"Invalid cases: {invalid_cases}")
    
    if invalid_cases > 0:
        console.print("[yellow]Some test cases have validation errors[/yellow]")
        raise typer.Exit(1)
    else:
        console.print("[green]All test cases are valid![/green]")


@app.command()
def list_models(
    models: Path = typer.Option(
        Path("models.yaml"),
        "--models",
        "-m",
        help="Path to models configuration file"
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env",
        help="Path to .env file (auto-detected if not provided)"
    )
):
    """List available model configurations."""
    
    # Auto-detect env file if not provided
    if env_file is None:
        env_file = find_env_file()
    
    console.print(f"[bold blue]Available Model Configurations[/bold blue]")
    console.print(f"Config file: {models}")
    console.print()
    
    try:
        from .config import load_models_config, load_env_config, validate_model_config
        
        env_config = load_env_config(env_file)
        model_configs = load_models_config(models, env_config)
        
        if not model_configs:
            console.print("[yellow]No model configurations found[/yellow]")
            return
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan")
        table.add_column("Family", style="green")
        table.add_column("Model", style="blue")
        table.add_column("Endpoint", style="yellow")
        table.add_column("Status", style="red")
        
        for model in model_configs:
            errors = validate_model_config(model, env_config)
            status = "✓ Valid" if not errors else f"✗ {len(errors)} errors"
            
            table.add_row(
                model.name,
                model.family.value,
                model.model,
                model.endpoint,
                status
            )
        
        console.print(table)
        
        # Show validation errors
        for model in model_configs:
            errors = validate_model_config(model, env_config)
            if errors:
                console.print(f"\n[red]Errors for {model.name}:[/red]")
                for error in errors:
                    console.print(f"  - {error}")
        
    except Exception as e:
        console.print(f"[red]Error loading models: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    from . import __version__
    console.print(f"Java Maintenance Agent Benchmark v{__version__}")


if __name__ == "__main__":
    app()
