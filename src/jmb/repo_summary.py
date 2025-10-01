"""Repository tree summarization and file retrieval."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

from .prompts import extract_stacktrace_files


def create_repo_tree(
    repo_path: Path,
    max_entries: int = 1000,
    exclude_patterns: Optional[List[str]] = None
) -> str:
    """Create a text representation of the repository tree structure."""
    if exclude_patterns is None:
        exclude_patterns = [
            '.git', 'node_modules', '.gradle', 'target', 'build', 
            '.idea', '.vscode', '__pycache__', '.pytest_cache',
            '*.class', '*.jar', '*.war', '*.ear'
        ]
    
    tree_lines = []
    entry_count = 0
    
    def should_exclude(path: Path) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path)
        for pattern in exclude_patterns:
            if pattern.startswith('*'):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False
    
    def walk_directory(dir_path: Path, prefix: str = "", depth: int = 0, max_depth: int = 6):
        """Recursively walk directory and build tree representation."""
        nonlocal entry_count
        
        if entry_count >= max_entries or depth > max_depth:
            return
        
        try:
            items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for i, item in enumerate(items):
                if entry_count >= max_entries:
                    break
                
                if should_exclude(item):
                    continue
                
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                tree_lines.append(f"{prefix}{current_prefix}{item.name}")
                entry_count += 1
                
                if item.is_dir() and entry_count < max_entries:
                    extension = "    " if is_last else "│   "
                    walk_directory(item, prefix + extension, depth + 1, max_depth)
                    
        except PermissionError:
            tree_lines.append(f"{prefix}└── [Permission Denied]")
        except Exception as e:
            tree_lines.append(f"{prefix}└── [Error: {str(e)}]")
    
    # Start with the root directory
    tree_lines.append(f"{repo_path.name}/")
    walk_directory(repo_path)
    
    if entry_count >= max_entries:
        tree_lines.append(f"\n[Tree truncated - showing first {max_entries} entries]")
    
    return "\n".join(tree_lines)


def get_file_snippet(
    file_path: Path,
    line_number: int,
    context_lines: int = 5
) -> Optional[str]:
    """Get a code snippet around a specific line number."""
    try:
        if not file_path.exists() or not file_path.is_file():
            return None
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if line_number < 1 or line_number > len(lines):
            return None
        
        # Calculate start and end lines (0-indexed)
        start_line = max(0, line_number - 1 - context_lines)
        end_line = min(len(lines), line_number - 1 + context_lines + 1)
        
        snippet_lines = []
        for i in range(start_line, end_line):
            line_num = i + 1
            marker = ">>> " if line_num == line_number else "    "
            snippet_lines.append(f"{marker}{line_num:4d}: {lines[i].rstrip()}")
        
        return "\n".join(snippet_lines)
        
    except Exception:
        return None


def get_file_content(file_path: Path, max_lines: int = 100) -> Optional[str]:
    """Get file content with line numbers, truncated if too long."""
    try:
        if not file_path.exists() or not file_path.is_file():
            return None
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True
        else:
            truncated = False
        
        content_lines = []
        for i, line in enumerate(lines, 1):
            content_lines.append(f"{i:4d}: {line.rstrip()}")
        
        content = "\n".join(content_lines)
        if truncated:
            content += f"\n[Content truncated - showing first {max_lines} lines]"
        
        return content
        
    except Exception:
        return None


def retrieve_stacktrace_files(
    repo_path: Path,
    logs: str,
    max_files: int = 5,
    context_lines: int = 10
) -> Dict[str, str]:
    """Retrieve code snippets for files mentioned in stacktrace."""
    stacktrace_files = extract_stacktrace_files(logs)
    
    retrieved_snippets = {}
    for file_path_str in stacktrace_files[:max_files]:
        file_path = repo_path / file_path_str
        
        if file_path.exists() and file_path.is_file():
            # Try to find the line number from the stacktrace
            line_number = extract_line_from_stacktrace(logs, file_path_str)
            
            if line_number:
                snippet = get_file_snippet(file_path, line_number, context_lines)
            else:
                snippet = get_file_content(file_path, max_lines=50)
            
            if snippet:
                retrieved_snippets[file_path_str] = snippet
    
    return retrieved_snippets


def extract_line_from_stacktrace(logs: str, file_path: str) -> Optional[int]:
    """Extract line number for a specific file from stacktrace."""
    import re
    
    # Pattern to match: at com.example.Class.method(Class.java:123)
    pattern = rf'at\s+[\w.$]+\({re.escape(file_path)}:(\d+)\)'
    matches = re.findall(pattern, logs)
    
    if matches:
        # Return the first line number found
        return int(matches[0])
    
    return None


def get_java_files(repo_path: Path, max_files: int = 20) -> List[Path]:
    """Get a list of Java files in the repository."""
    java_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip common build directories
        dirs[:] = [d for d in dirs if d not in {'.git', 'target', 'build', '.gradle'}]
        
        for file in files:
            if file.endswith('.java'):
                java_files.append(Path(root) / file)
                if len(java_files) >= max_files:
                    break
        
        if len(java_files) >= max_files:
            break
    
    return java_files


def get_build_files(repo_path: Path) -> Dict[str, Path]:
    """Get build configuration files."""
    build_files = {}
    
    # Maven
    pom_file = repo_path / "pom.xml"
    if pom_file.exists():
        build_files["pom.xml"] = pom_file
    
    # Gradle
    gradle_files = [
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts"
    ]
    
    for gradle_file in gradle_files:
        file_path = repo_path / gradle_file
        if file_path.exists():
            build_files[gradle_file] = file_path
    
    return build_files


def analyze_repository_structure(repo_path: Path) -> Dict[str, any]:
    """Analyze the repository structure and return metadata."""
    java_files = get_java_files(repo_path, max_files=100)
    build_files = get_build_files(repo_path)
    
    # Count files by directory
    dir_counts = {}
    for java_file in java_files:
        parent_dir = java_file.parent.relative_to(repo_path)
        dir_counts[str(parent_dir)] = dir_counts.get(str(parent_dir), 0) + 1
    
    return {
        "total_java_files": len(java_files),
        "build_files": list(build_files.keys()),
        "directory_structure": dir_counts,
        "has_maven": "pom.xml" in build_files,
        "has_gradle": any(f.startswith("build.gradle") for f in build_files),
        "main_directories": sorted(dir_counts.keys())[:10]  # Top 10 directories
    }
