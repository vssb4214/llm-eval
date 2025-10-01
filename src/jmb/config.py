"""Configuration management for the benchmark system."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, validator

from .types import BenchmarkConfig, ModelConfig, ModelFamily


class EnvironmentConfig(BaseModel):
    """Environment configuration loaded from .env file."""
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: Optional[str] = None
    local_base_url: Optional[str] = None
    local_api_key: Optional[str] = None
    
    # Cost tracking
    openai_gpt4_cost_per_1k_input: float = 0.03
    openai_gpt4_cost_per_1k_output: float = 0.06
    anthropic_claude_cost_per_1k_input: float = 0.015
    anthropic_claude_cost_per_1k_output: float = 0.075


def load_env_config(env_file: Optional[Path] = None) -> EnvironmentConfig:
    """Load environment configuration from .env file."""
    config = EnvironmentConfig()
    
    if env_file and env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Map environment variables to config fields
                    if key == "OPENAI_API_KEY":
                        config.openai_api_key = value
                    elif key == "OPENAI_BASE_URL":
                        config.openai_base_url = value
                    elif key == "ANTHROPIC_API_KEY":
                        config.anthropic_api_key = value
                    elif key == "LOCAL_BASE_URL":
                        config.local_base_url = value
                    elif key == "LOCAL_API_KEY":
                        config.local_api_key = value
                    elif key == "OPENAI_GPT4_COST_PER_1K_INPUT":
                        config.openai_gpt4_cost_per_1k_input = float(value)
                    elif key == "OPENAI_GPT4_COST_PER_1K_OUTPUT":
                        config.openai_gpt4_cost_per_1k_output = float(value)
                    elif key == "ANTHROPIC_CLAUDE_COST_PER_1K_INPUT":
                        config.anthropic_claude_cost_per_1k_input = float(value)
                    elif key == "ANTHROPIC_CLAUDE_COST_PER_1K_OUTPUT":
                        config.anthropic_claude_cost_per_1k_output = float(value)
    
    # Also check actual environment variables
    config.openai_api_key = config.openai_api_key or os.getenv("OPENAI_API_KEY")
    config.openai_base_url = os.getenv("OPENAI_BASE_URL", config.openai_base_url)
    config.anthropic_api_key = config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    config.local_base_url = config.local_base_url or os.getenv("LOCAL_BASE_URL")
    config.local_api_key = config.local_api_key or os.getenv("LOCAL_API_KEY")
    
    return config


def resolve_env_vars(text: str, env_config: EnvironmentConfig) -> str:
    """Resolve environment variable references in text."""
    def replace_var(match):
        var_name = match.group(1)
        if var_name == "OPENAI_BASE_URL":
            return env_config.openai_base_url
        elif var_name == "OPENAI_API_KEY":
            return env_config.openai_api_key or ""
        elif var_name == "ANTHROPIC_API_KEY":
            return env_config.anthropic_api_key or ""
        elif var_name == "LOCAL_BASE_URL":
            return env_config.local_base_url or ""
        elif var_name == "LOCAL_API_KEY":
            return env_config.local_api_key or ""
        else:
            return os.getenv(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, text)


def load_models_config(models_file: Path, env_config: EnvironmentConfig) -> List[ModelConfig]:
    """Load models configuration from YAML file."""
    with open(models_file, 'r') as f:
        data = yaml.safe_load(f)
    
    models = []
    for model_data in data.get('models', []):
        # Resolve environment variables
        resolved_data = {}
        for key, value in model_data.items():
            if isinstance(value, str):
                resolved_data[key] = resolve_env_vars(value, env_config)
            else:
                resolved_data[key] = value
        
        # Create ModelConfig
        model_config = ModelConfig(**resolved_data)
        models.append(model_config)
    
    return models


def get_api_key(model_config: ModelConfig, env_config: EnvironmentConfig) -> Optional[str]:
    """Get API key for a model configuration."""
    if not model_config.api_key_env:
        return None
    elif model_config.api_key_env == "OPENAI_API_KEY":
        return env_config.openai_api_key
    elif model_config.api_key_env == "ANTHROPIC_API_KEY":
        return env_config.anthropic_api_key
    elif model_config.api_key_env == "LOCAL_API_KEY":
        return env_config.local_api_key
    else:
        return os.getenv(model_config.api_key_env)


def validate_model_config(model_config: ModelConfig, env_config: EnvironmentConfig) -> List[str]:
    """Validate a model configuration and return any errors."""
    errors = []
    
    # Check API key availability (only if api_key_env is specified)
    if model_config.api_key_env:
        api_key = get_api_key(model_config, env_config)
        if not api_key:
            errors.append(f"API key not found for {model_config.name} (env: {model_config.api_key_env})")
    
    # Validate endpoint URL
    if not model_config.endpoint.startswith(('http://', 'https://')):
        errors.append(f"Invalid endpoint URL for {model_config.name}: {model_config.endpoint}")
    
    # Validate model family
    if model_config.family not in ModelFamily:
        errors.append(f"Unknown model family for {model_config.name}: {model_config.family}")
    
    return errors


def load_benchmark_config(
    cases_dir: Path,
    models_file: Path,
    output_dir: Path,
    env_file: Optional[Path] = None,
    **kwargs
) -> tuple[BenchmarkConfig, List[ModelConfig], EnvironmentConfig]:
    """Load complete benchmark configuration."""
    # Load environment config
    env_config = load_env_config(env_file)
    
    # Load models config
    models = load_models_config(models_file, env_config)
    
    # Validate models
    all_errors = []
    valid_models = []
    for model in models:
        errors = validate_model_config(model, env_config)
        if errors:
            all_errors.extend([f"{model.name}: {error}" for error in errors])
        else:
            valid_models.append(model)
    
    if all_errors:
        print("Model configuration errors:")
        for error in all_errors:
            print(f"  - {error}")
        print()
    
    # Create benchmark config
    benchmark_config = BenchmarkConfig(
        cases_dir=cases_dir,
        models_config=models_file,
        output_dir=output_dir,
        **kwargs
    )
    
    return benchmark_config, valid_models, env_config


def find_env_file() -> Optional[Path]:
    """Find .env file in current directory or parent directories."""
    current = Path.cwd()
    for _ in range(5):  # Look up to 5 levels up
        env_file = current / ".env"
        if env_file.exists():
            return env_file
        current = current.parent
        if current == current.parent:  # Reached root
            break
    return None
