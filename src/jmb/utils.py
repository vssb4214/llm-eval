"""Utility functions for the benchmark system."""

import json
import re
from typing import Any, Dict, Optional

from .types import ModelOutput


def safe_json_parse(text: str) -> Optional[ModelOutput]:
    """Safely parse JSON from model output with error handling."""
    if not text or not text.strip():
        return None
    
    # Try to extract JSON from the text
    json_text = extract_json_from_text(text)
    if not json_text:
        return None
    
    try:
        data = json.loads(json_text)
        return ModelOutput(**data)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        # Try to repair common JSON issues
        repaired_json = repair_json(json_text)
        if repaired_json:
            try:
                data = json.loads(repaired_json)
                return ModelOutput(**data)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        return None


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract JSON content from text that might contain other content."""
    # Look for JSON object boundaries
    start_patterns = [
        r'\{',  # Start with {
        r'```json\s*\{',  # Start with ```json {
        r'```\s*\{',  # Start with ``` {
    ]
    
    for pattern in start_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Find the matching closing brace
            start_pos = match.start()
            if '```' in pattern:
                start_pos = match.end() - 1  # Position after the opening {
            
            # Count braces to find the end
            brace_count = 0
            in_string = False
            escape_next = False
            
            for i, char in enumerate(text[start_pos:], start_pos):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            return text[start_pos:i+1]
            
            # If we get here, try to find the end of the text block
            end_match = re.search(r'```', text[start_pos:], re.IGNORECASE)
            if end_match:
                return text[start_pos:start_pos + end_match.start()]
    
    return None


def repair_json(json_text: str) -> Optional[str]:
    """Attempt to repair common JSON issues."""
    if not json_text:
        return None
    
    # Remove trailing commas
    json_text = re.sub(r',\s*}', '}', json_text)
    json_text = re.sub(r',\s*]', ']', json_text)
    
    # Fix unescaped quotes in strings
    # This is a simple heuristic - might not work for all cases
    json_text = re.sub(r'(?<!\\)"(?=.*")', '\\"', json_text)
    
    # Fix missing quotes around keys
    json_text = re.sub(r'(\w+):', r'"\1":', json_text)
    
    return json_text


def redact_secrets(text: str) -> str:
    """Redact potential secrets from text."""
    # Common secret patterns
    patterns = [
        (r'api[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)', r'api_key="REDACTED"'),
        (r'token["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)', r'token="REDACTED"'),
        (r'password["\s]*[:=]["\s]*([^\s"]+)', r'password="REDACTED"'),
        (r'secret["\s]*[:=]["\s]*([a-zA-Z0-9_-]+)', r'secret="REDACTED"'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'REDACTED_EMAIL'),
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 'REDACTED_CARD'),
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def estimate_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """Estimate token count for text using tiktoken."""
    try:
        import tiktoken
        
        # Get encoding for the model
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))
    except ImportError:
        # Fallback estimation: ~4 characters per token
        return len(text) // 4


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def create_summary_stats(results: list) -> Dict[str, Any]:
    """Create summary statistics from results."""
    if not results:
        return {}
    
    total_runs = len(results)
    successful_runs = sum(1 for r in results if r.scoring and r.scoring.total_score > 0)
    
    # Calculate average scores
    scores = [r.scoring.total_score for r in results if r.scoring]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Calculate success rates
    build_successes = sum(1 for r in results if r.build_result and r.build_result.build_pass)
    test_successes = sum(1 for r in results if r.build_result and r.build_result.test_pass)
    patch_successes = sum(1 for r in results if r.patch_result and r.patch_result.apply_success)
    
    return {
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "success_rate": successful_runs / total_runs if total_runs > 0 else 0,
        "average_score": avg_score,
        "build_success_rate": build_successes / total_runs if total_runs > 0 else 0,
        "test_success_rate": test_successes / total_runs if total_runs > 0 else 0,
        "patch_success_rate": patch_successes / total_runs if total_runs > 0 else 0,
    }
