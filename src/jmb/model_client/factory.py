"""Factory for creating model clients."""

from typing import Optional

from .base import ModelClient
from .openai_like import OpenAILikeClient
from .anthropic_client import AnthropicClient
from ..types import ModelConfig, ModelFamily
from ..config import get_api_key, EnvironmentConfig


def create_model_client(
    model_config: ModelConfig,
    env_config: EnvironmentConfig
) -> ModelClient:
    """Create a model client based on the model configuration."""
    api_key = get_api_key(model_config, env_config)
    
    if model_config.family == ModelFamily.OPENAI:
        if not api_key:
            raise ValueError(f"API key required for OpenAI model {model_config.name}")
        return OpenAILikeClient(model_config, api_key)
    elif model_config.family == ModelFamily.ANTHROPIC:
        if not api_key:
            raise ValueError(f"API key required for Anthropic model {model_config.name}")
        return AnthropicClient(model_config, api_key)
    elif model_config.family in [ModelFamily.DEEPSEEK, ModelFamily.GEMMA, ModelFamily.STARCODER, ModelFamily.LOCAL]:
        # These are typically OpenAI-compatible (including LM Studio)
        return OpenAILikeClient(model_config, api_key)
    else:
        raise ValueError(f"Unsupported model family: {model_config.family}")
