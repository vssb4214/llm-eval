"""OpenAI-compatible model client implementation."""

import json
import time
from typing import Dict, Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import ModelClient, ModelResponse


class OpenAILikeClient(ModelClient):
    """Client for OpenAI-compatible APIs."""
    
    def __init__(self, model_config, api_key: Optional[str] = None):
        super().__init__(model_config, api_key)
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        self.client = httpx.AsyncClient(
            base_url=model_config.endpoint,
            headers=headers,
            timeout=300.0
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """Generate a response using OpenAI-compatible API."""
        start_time = time.time()
        
        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Prepare request payload
        payload = {
            "model": self.model_config.model,
            "messages": messages,
            "temperature": temperature or self.model_config.temperature,
            "max_tokens": max_tokens or self.model_config.max_tokens
        }
        
        # Only add response_format for models that support it
        # LM Studio doesn't support json_object, so we'll handle JSON parsing manually
        if "openai" in self.model_config.endpoint.lower() and "api.openai.com" in self.model_config.endpoint:
            payload["response_format"] = {"type": "json_object"}
        
        # Add any additional parameters
        payload.update(kwargs)
        
        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            
            latency = time.time() - start_time
            
            # Extract token usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
            
            return ModelResponse(
                content=message["content"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_seconds=latency,
                model_name=self.model_config.name,
                finish_reason=choice.get("finish_reason"),
                metadata={
                    "model": self.model_config.model,
                    "temperature": payload["temperature"],
                    "max_tokens": payload["max_tokens"]
                }
            )
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            raise RuntimeError(f"API request failed: {error_msg}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {str(e)}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {str(e)}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def __del__(self):
        """Ensure client is closed on deletion."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
        except:
            pass
