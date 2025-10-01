"""Report generation with charts and leaderboards."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from .types import RunResult, ModelConfig, TestCase
from .utils import create_summary_stats


class ReportGenerator:
    """Generates comprehensive benchmark reports with charts and analysis."""
    
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.console = Console()
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
    
    def generate_report(
        self,
        results: List[RunResult],
        models: List[ModelConfig],
        test_cases: List[TestCase],
        output_path: Path,
        generate_html: bool = False
    ) -> Path:
        """Generate a comprehensive benchmark report."""
        self.console.print("[blue]Generating benchmark report...[/blue]")
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Analyze results
        analysis = self._analyze_results(results, models, test_cases)
        
        # Generate charts
        charts_dir = output_path.parent / "charts"
        charts_dir.mkdir(exist_ok=True)
        self._generate_charts(results, models, charts_dir)
        
        # Generate markdown report
        markdown_path = self._generate_markdown_report(analysis, output_path)
        
        # Generate HTML report if requested
        html_path = None
        if generate_html:
            html_path = self._generate_html_report(analysis, output_path)
        
        self.console.print(f"[green]Report generated: {markdown_path}[/green]")
        if html_path:
            self.console.print(f"[green]HTML report: {html_path}[/green]")
        
        return markdown_path
    
    def _analyze_results(
        self,
        results: List[RunResult],
        models: List[ModelConfig],
        test_cases: List[TestCase]
    ) -> Dict[str, Any]:
        """Analyze results and create comprehensive statistics."""
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame([result.to_csv_row() for result in results])
        
        # Overall statistics
        summary_stats = create_summary_stats(results)
        
        # Model leaderboard
        model_leaderboard = self._create_model_leaderboard(df, models)
        
        # Test case analysis
        test_case_analysis = self._create_test_case_analysis(df, test_cases)
        
        # Score distribution
        score_distribution = self._create_score_distribution(df)
        
        # Performance analysis
        performance_analysis = self._create_performance_analysis(df)
        
        # Error analysis
        error_analysis = self._create_error_analysis(results)
        
        # Build system analysis
        build_system_analysis = self._create_build_system_analysis(df)
        
        # Additional insights
        insights = self._create_insights(model_leaderboard, build_system_analysis, df)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_runs": len(results),
            "models": models,
            "test_cases": test_cases,
            "summary_stats": summary_stats,
            "model_leaderboard": model_leaderboard,
            "test_case_analysis": test_case_analysis,
            "score_distribution": score_distribution,
            "performance_analysis": performance_analysis,
            "error_analysis": error_analysis,
            "build_system_analysis": build_system_analysis,
            "insights": insights
        }
    
    def _create_model_leaderboard(self, df: pd.DataFrame, models: List[ModelConfig]) -> List[Dict]:
        """Create model leaderboard with performance metrics."""
        leaderboard = []
        
        for model in models:
            model_df = df[df['model_name'] == model.name]
            if model_df.empty:
                continue
            
            # Calculate metrics
            total_runs = len(model_df)
            successful_runs = len(model_df[model_df['test_pass'] == True])
            success_rate = successful_runs / total_runs if total_runs > 0 else 0
            
            # Average scores (assuming we have scoring data)
            avg_score = 0  # TODO: Calculate from scoring data
            avg_fix_success = 0
            avg_localization = 0
            avg_ops = 0
            avg_reliability = 0
            
            # Success rates
            build_success_rate = model_df['build_pass'].mean()
            test_success_rate = model_df['test_pass'].mean()
            patch_success_rate = model_df['patch_apply_ok'].mean()
            json_success_rate = model_df['patch_generated'].mean()
            
            # Performance metrics
            avg_latency = model_df['latency_sec'].mean()
            avg_tokens = model_df['total_tokens'].mean()
            avg_cost = model_df['cost_usd'].mean()
            
            leaderboard.append({
                "name": model.name,
                "family": model.family.value,
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "success_rate": success_rate,
                "avg_score": avg_score,
                "avg_fix_success": avg_fix_success,
                "avg_localization": avg_localization,
                "avg_ops": avg_ops,
                "avg_reliability": avg_reliability,
                "build_success_rate": build_success_rate,
                "test_success_rate": test_success_rate,
                "patch_success_rate": patch_success_rate,
                "json_success_rate": json_success_rate,
                "avg_latency": avg_latency,
                "avg_tokens": avg_tokens,
                "avg_cost": avg_cost
            })
        
        # Sort by average score
        leaderboard.sort(key=lambda x: x['avg_score'], reverse=True)
        return leaderboard
    
    def _create_test_case_analysis(self, df: pd.DataFrame, test_cases: List[TestCase]) -> List[Dict]:
        """Create test case analysis."""
        analysis = []
        
        for case in test_cases:
            case_df = df[df['case_id'] == case.case_id]
            if case_df.empty:
                continue
            
            # Model results for this case
            model_results = []
            for model_name in case_df['model_name'].unique():
                model_case_df = case_df[case_df['model_name'] == model_name]
                model_results.append({
                    "name": model_name,
                    "score": 0,  # TODO: Calculate from scoring data
                    "build_success_rate": model_case_df['build_pass'].mean(),
                    "test_success_rate": model_case_df['test_pass'].mean(),
                    "patch_success_rate": model_case_df['patch_apply_ok'].mean()
                })
            
            # Sort by score
            model_results.sort(key=lambda x: x['score'], reverse=True)
            
            analysis.append({
                "case_id": case.case_id,
                "suite": case.suite,
                "project": case.project,
                "build_system": case.build_system.value,
                "total_runs": len(case_df),
                "model_results": model_results,
                "top_models": model_results[:3]
            })
        
        return analysis
    
    def _create_score_distribution(self, df: pd.DataFrame) -> Dict[str, int]:
        """Create score distribution analysis."""
        # TODO: Implement when scoring data is available
        return {
            "very_low": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "excellent": 0
        }
    
    def _create_performance_analysis(self, df: pd.DataFrame) -> Dict[str, int]:
        """Create performance analysis."""
        # Fast vs Slow, Good vs Poor
        fast_good = len(df[(df['latency_sec'] <= 120) & (df['test_pass'] == True)])
        fast_poor = len(df[(df['latency_sec'] <= 120) & (df['test_pass'] == False)])
        slow_good = len(df[(df['latency_sec'] > 120) & (df['test_pass'] == True)])
        slow_poor = len(df[(df['latency_sec'] > 120) & (df['test_pass'] == False)])
        
        # Token efficiency
        efficient_good = len(df[(df['total_tokens'] <= 2000) & (df['test_pass'] == True)])
        inefficient_poor = len(df[(df['total_tokens'] > 2000) & (df['test_pass'] == False)])
        
        return {
            "fast_good": fast_good,
            "fast_poor": fast_poor,
            "slow_good": slow_good,
            "slow_poor": slow_poor,
            "efficient_good": efficient_good,
            "inefficient_poor": inefficient_poor
        }
    
    def _create_error_analysis(self, results: List[RunResult]) -> Dict[str, int]:
        """Create error analysis."""
        error_counts = {}
        
        for result in results:
            if result.notes and "Error:" in result.notes:
                error_type = "Unknown Error"
                if "timeout" in result.notes.lower():
                    error_type = "Timeout"
                elif "json" in result.notes.lower():
                    error_type = "JSON Parse Error"
                elif "patch" in result.notes.lower():
                    error_type = "Patch Apply Error"
                elif "build" in result.notes.lower():
                    error_type = "Build Error"
                
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return error_counts
    
    def _create_build_system_analysis(self, df: pd.DataFrame) -> List[Dict]:
        """Create build system analysis."""
        analysis = []
        
        for build_system in df['build_system'].unique():
            build_df = df[df['build_system'] == build_system]
            
            analysis.append({
                "name": build_system,
                "total_runs": len(build_df),
                "success_rate": build_df['test_pass'].mean(),
                "avg_score": 0  # TODO: Calculate from scoring data
            })
        
        return analysis
    
    def _create_insights(
        self,
        model_leaderboard: List[Dict],
        build_system_analysis: List[Dict],
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Create key insights and recommendations."""
        
        # Best performing model
        best_model = model_leaderboard[0] if model_leaderboard else None
        
        # Best build system
        best_build_system = max(build_system_analysis, key=lambda x: x['success_rate']) if build_system_analysis else None
        
        # Most reliable model (highest reliability score)
        most_reliable_model = max(model_leaderboard, key=lambda x: x['avg_reliability']) if model_leaderboard else None
        
        # Fastest model
        fastest_model = min(model_leaderboard, key=lambda x: x['avg_latency']) if model_leaderboard else None
        
        # Overall metrics
        overall_test_pass_rate = df['test_pass'].mean()
        patch_apply_success_rate = df['patch_apply_ok'].mean()
        avg_localization_accuracy = 0  # TODO: Calculate from scoring data
        
        return {
            "best_model": best_model,
            "best_build_system": best_build_system,
            "most_reliable_model": most_reliable_model,
            "fastest_model": fastest_model,
            "overall_test_pass_rate": overall_test_pass_rate,
            "patch_apply_success_rate": patch_apply_success_rate,
            "avg_localization_accuracy": avg_localization_accuracy
        }
    
    def _generate_charts(self, results: List[RunResult], models: List[ModelConfig], charts_dir: Path):
        """Generate charts and visualizations."""
        df = pd.DataFrame([result.to_csv_row() for result in results])
        
        # Model performance comparison
        self._create_model_comparison_chart(df, models, charts_dir)
        
        # Success rate by model
        self._create_success_rate_chart(df, models, charts_dir)
        
        # Latency distribution
        self._create_latency_chart(df, charts_dir)
        
        # Build system comparison
        self._create_build_system_chart(df, charts_dir)
    
    def _create_model_comparison_chart(self, df: pd.DataFrame, models: List[ModelConfig], charts_dir: Path):
        """Create model performance comparison chart."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        model_names = []
        success_rates = []
        
        for model in models:
            model_df = df[df['model_name'] == model.name]
            if not model_df.empty:
                model_names.append(model.name)
                success_rates.append(model_df['test_pass'].mean() * 100)
        
        bars = ax.bar(model_names, success_rates)
        ax.set_ylabel('Success Rate (%)')
        ax.set_title('Model Performance Comparison')
        ax.set_ylim(0, 100)
        
        # Add value labels on bars
        for bar, rate in zip(bars, success_rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                   f'{rate:.1f}%', ha='center', va='bottom')
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(charts_dir / 'model_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_success_rate_chart(self, df: pd.DataFrame, models: List[ModelConfig], charts_dir: Path):
        """Create success rate breakdown chart."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        model_names = []
        build_rates = []
        test_rates = []
        patch_rates = []
        
        for model in models:
            model_df = df[df['model_name'] == model.name]
            if not model_df.empty:
                model_names.append(model.name)
                build_rates.append(model_df['build_pass'].mean() * 100)
                test_rates.append(model_df['test_pass'].mean() * 100)
                patch_rates.append(model_df['patch_apply_ok'].mean() * 100)
        
        x = range(len(model_names))
        width = 0.25
        
        ax.bar([i - width for i in x], build_rates, width, label='Build Pass', alpha=0.8)
        ax.bar(x, test_rates, width, label='Test Pass', alpha=0.8)
        ax.bar([i + width for i in x], patch_rates, width, label='Patch Apply', alpha=0.8)
        
        ax.set_ylabel('Success Rate (%)')
        ax.set_title('Success Rate Breakdown by Model')
        ax.set_xticks(x)
        ax.set_xticklabels(model_names, rotation=45, ha='right')
        ax.legend()
        ax.set_ylim(0, 100)
        
        plt.tight_layout()
        plt.savefig(charts_dir / 'success_rates.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_latency_chart(self, df: pd.DataFrame, charts_dir: Path):
        """Create latency distribution chart."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(df['latency_sec'], bins=20, alpha=0.7, edgecolor='black')
        ax.set_xlabel('Latency (seconds)')
        ax.set_ylabel('Frequency')
        ax.set_title('Latency Distribution')
        ax.axvline(df['latency_sec'].mean(), color='red', linestyle='--', 
                  label=f'Mean: {df["latency_sec"].mean():.1f}s')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(charts_dir / 'latency_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_build_system_chart(self, df: pd.DataFrame, charts_dir: Path):
        """Create build system comparison chart."""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        build_systems = df['build_system'].unique()
        success_rates = []
        
        for build_system in build_systems:
            build_df = df[df['build_system'] == build_system]
            success_rates.append(build_df['test_pass'].mean() * 100)
        
        bars = ax.bar(build_systems, success_rates)
        ax.set_ylabel('Success Rate (%)')
        ax.set_title('Success Rate by Build System')
        ax.set_ylim(0, 100)
        
        # Add value labels
        for bar, rate in zip(bars, success_rates):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                   f'{rate:.1f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(charts_dir / 'build_system_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _generate_markdown_report(self, analysis: Dict[str, Any], output_path: Path) -> Path:
        """Generate markdown report using Jinja2 template."""
        template = self.jinja_env.get_template('report.md.j2')
        content = template.render(**analysis)
        
        markdown_path = output_path.with_suffix('.md')
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return markdown_path
    
    def _generate_html_report(self, analysis: Dict[str, Any], output_path: Path) -> Path:
        """Generate HTML report."""
        # For now, just convert markdown to HTML using a simple approach
        # In a real implementation, you might use markdown2 or similar
        html_path = output_path.with_suffix('.html')
        
        # Simple HTML wrapper
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Java Maintenance Agent Benchmark Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .chart {{ text-align: center; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Java Maintenance Agent Benchmark Report</h1>
    <p><strong>Generated:</strong> {analysis['timestamp']}</p>
    <p><strong>Total Runs:</strong> {analysis['total_runs']}</p>
    
    <div class="chart">
        <img src="charts/model_comparison.png" alt="Model Comparison" style="max-width: 100%;">
    </div>
    
    <div class="chart">
        <img src="charts/success_rates.png" alt="Success Rates" style="max-width: 100%;">
    </div>
    
    <!-- Add more content as needed -->
</body>
</html>
        """
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_path


def create_report_generator(template_dir: Path) -> ReportGenerator:
    """Create a report generator instance."""
    return ReportGenerator(template_dir)
