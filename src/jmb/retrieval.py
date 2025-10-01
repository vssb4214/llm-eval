"""Retrieval system for augmenting prompts with relevant code snippets."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .repo_summary import get_file_snippet, get_file_content, retrieve_stacktrace_files


class CodeRetriever:
    """Retrieves relevant code snippets for prompt augmentation."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    def retrieve_for_logs(self, logs: str, max_files: int = 5) -> Dict[str, str]:
        """Retrieve code snippets based on stacktrace in logs."""
        return retrieve_stacktrace_files(self.repo_path, logs, max_files)
    
    def retrieve_for_file_line(self, file_path: str, line_number: int, context: int = 10) -> Optional[str]:
        """Retrieve code snippet for a specific file and line."""
        full_path = self.repo_path / file_path
        return get_file_snippet(full_path, line_number, context)
    
    def retrieve_file_content(self, file_path: str, max_lines: int = 100) -> Optional[str]:
        """Retrieve full file content (truncated)."""
        full_path = self.repo_path / file_path
        return get_file_content(full_path, max_lines)
    
    def find_related_files(self, logs: str, max_files: int = 10) -> List[Path]:
        """Find Java files that might be related to the error."""
        related_files = []
        
        # Extract class names from stacktrace
        class_names = self._extract_class_names(logs)
        
        # Find files that match these class names
        for class_name in class_names:
            matching_files = self._find_files_by_class_name(class_name)
            related_files.extend(matching_files)
        
        # Remove duplicates and limit
        unique_files = list(set(related_files))[:max_files]
        return unique_files
    
    def _extract_class_names(self, logs: str) -> Set[str]:
        """Extract Java class names from stacktrace."""
        class_names = set()
        
        # Pattern: com.example.ClassName.method
        pattern = r'([a-zA-Z_$][a-zA-Z0-9_$]*\.)+([a-zA-Z_$][a-zA-Z0-9_$]*)'
        matches = re.findall(pattern, logs)
        
        for match in matches:
            # Get the last part (class name)
            class_name = match[-1]
            if len(class_name) > 2:  # Filter out very short names
                class_names.add(class_name)
        
        return class_names
    
    def _find_files_by_class_name(self, class_name: str) -> List[Path]:
        """Find Java files that contain a specific class name."""
        matching_files = []
        
        for java_file in self.repo_path.rglob("*.java"):
            try:
                with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if f"class {class_name}" in content or f"interface {class_name}" in content:
                        matching_files.append(java_file)
            except Exception:
                continue
        
        return matching_files
    
    def retrieve_error_context(self, logs: str, max_snippets: int = 3) -> Dict[str, str]:
        """Retrieve code snippets that provide context for the error."""
        snippets = {}
        
        # First, try stacktrace-based retrieval
        stacktrace_snippets = self.retrieve_for_logs(logs, max_files=max_snippets)
        snippets.update(stacktrace_snippets)
        
        # If we don't have enough snippets, try to find related files
        if len(snippets) < max_snippets:
            related_files = self.find_related_files(logs, max_files=max_snippets - len(snippets))
            
            for file_path in related_files:
                if len(snippets) >= max_snippets:
                    break
                
                relative_path = file_path.relative_to(self.repo_path)
                content = get_file_content(file_path, max_lines=50)
                
                if content:
                    snippets[str(relative_path)] = content
        
        return snippets


def create_retriever(repo_path: Path) -> CodeRetriever:
    """Create a code retriever instance."""
    return CodeRetriever(repo_path)
