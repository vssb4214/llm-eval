"""Base model client interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """Response from a model client."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    model_name: str = ""
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ModelClient(ABC):
    """Abstract base class for model clients."""
    
    def __init__(self, model_config, api_key: Optional[str] = None):
        self.model_config = model_config
        self.api_key = api_key
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate a response from the model."""
        pass
    
    def estimate_cost(self, response: ModelResponse) -> float:
        """Estimate the cost of a response."""
        input_cost = (response.input_tokens / 1000.0) * self.model_config.cost_per_1k_input
        output_cost = (response.output_tokens / 1000.0) * self.model_config.cost_per_1k_output
        return input_cost + output_cost
