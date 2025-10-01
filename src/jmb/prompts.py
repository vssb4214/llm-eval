"""Prompting system for Java maintenance tasks."""

from typing import Dict, Any, Optional

from .types import TestCase


# JSON schema for model output validation
MODEL_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["localization", "patch_unified_diff"],
    "properties": {
        "localization": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["file", "line", "reason"],
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "reason": {"type": "string"}
                }
            },
            "minItems": 1
        },
        "patch_unified_diff": {"type": "string"},
        "notes": {"type": "string"}
    }
}


SYSTEM_PROMPT = """You are a senior Java maintenance engineer with expertise in debugging, fault localization, and creating minimal patches. Your task is to:

1. Analyze build/test failure logs to identify the root cause
2. Localize the fault to specific file(s) and line number(s) with ±5 lines tolerance
3. Create a minimal unified diff patch that fixes the issue
4. Ensure the patch compiles and makes tests pass without changing functionality

Guidelines:
- Focus on the actual error cause, not symptoms
- Provide precise file paths relative to the repository root
- Use line numbers from the current codebase (1-indexed)
- Create minimal patches that only fix the specific issue
- Do not modify build files (pom.xml, build.gradle) unless absolutely necessary
- Do not change method signatures or public APIs unless required
- Include clear reasoning for your localization choices

You must respond with valid JSON only, following this exact schema:
{
  "localization": [
    {
      "file": "path/to/file.java",
      "line": 42,
      "reason": "Explanation of why this location is the root cause"
    }
  ],
  "patch_unified_diff": "--- a/path/to/file.java\\n+++ b/path/to/file.java\\n@@ -40,6 +40,7 @@\\n ...",
  "notes": "Additional context or considerations"
}"""


def create_user_prompt(
    test_case: TestCase,
    repo_tree: str,
    logs: str,
    max_repo_entries: int = 1000,
    max_log_length: int = 10000
) -> str:
    """Create user prompt for a test case."""
    
    # Truncate logs if too long
    if len(logs) > max_log_length:
        logs = logs[:max_log_length] + "\n\n[LOGS TRUNCATED - showing first 10,000 characters]"
    
    # Truncate repo tree if too many entries
    repo_lines = repo_tree.split('\n')
    if len(repo_lines) > max_repo_entries:
        repo_tree = '\n'.join(repo_lines[:max_repo_entries]) + f"\n\n[REPO TREE TRUNCATED - showing first {max_repo_entries} entries]"
    
    prompt = f"""PROJECT BUILD: {test_case.build_system.value.upper()}
REPO TREE (truncated):
{repo_tree}

LOGS (truncated):
{logs}

GOAL:
- Identify the root cause file + line (±5 lines tolerance)
- Provide a minimal unified diff that compiles and makes tests pass
- Keep existing functionality; fix only the error cause
- Do not modify build configuration files unless essential

Return JSON per schema only."""

    return prompt


def create_retrieval_prompt(
    test_case: TestCase,
    repo_tree: str,
    logs: str,
    retrieved_snippets: Dict[str, str],
    max_repo_entries: int = 1000,
    max_log_length: int = 10000
) -> str:
    """Create user prompt with retrieved code snippets."""
    
    # Truncate logs if too long
    if len(logs) > max_log_length:
        logs = logs[:max_log_length] + "\n\n[LOGS TRUNCATED - showing first 10,000 characters]"
    
    # Truncate repo tree if too many entries
    repo_lines = repo_tree.split('\n')
    if len(repo_lines) > max_repo_entries:
        repo_tree = '\n'.join(repo_lines[:max_repo_entries]) + f"\n\n[REPO TREE TRUNCATED - showing first {max_repo_entries} entries]"
    
    # Add retrieved snippets
    snippets_section = ""
    if retrieved_snippets:
        snippets_section = "\n\nRETRIEVED CODE SNIPPETS:\n"
        for file_path, snippet in retrieved_snippets.items():
            snippets_section += f"\n--- {file_path} ---\n{snippet}\n"
    
    prompt = f"""PROJECT BUILD: {test_case.build_system.value.upper()}
REPO TREE (truncated):
{repo_tree}

LOGS (truncated):
{logs}{snippets_section}

GOAL:
- Identify the root cause file + line (±5 lines tolerance)
- Provide a minimal unified diff that compiles and makes tests pass
- Keep existing functionality; fix only the error cause
- Do not modify build configuration files unless essential

Return JSON per schema only."""

    return prompt


def extract_stacktrace_files(logs: str) -> list[str]:
    """Extract Java file paths from stacktrace in logs."""
    import re
    
    # Pattern to match Java file paths in stacktraces
    # Matches patterns like: at com.example.Class.method(Class.java:123)
    pattern = r'at\s+[\w.$]+\(([\w/]+\.java):(\d+)\)'
    matches = re.findall(pattern, logs)
    
    # Return unique file paths
    files = list(set(match[0] for match in matches))
    return files


def create_minimal_prompt(
    test_case: TestCase,
    logs: str,
    max_log_length: int = 5000
) -> str:
    """Create a minimal prompt for quick testing."""
    
    # Truncate logs if too long
    if len(logs) > max_log_length:
        logs = logs[:max_log_length] + "\n\n[LOGS TRUNCATED]"
    
    prompt = f"""PROJECT: {test_case.project}
BUILD SYSTEM: {test_case.build_system.value}

LOGS:
{logs}

Create a minimal patch to fix this issue. Return JSON with localization and patch_unified_diff."""

    return prompt
