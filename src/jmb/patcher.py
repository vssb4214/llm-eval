"""Patch application and validation system."""

import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .types import PatchResult
from .vcs import RepositoryManager


class PatchValidator:
    """Validates and analyzes patches before application."""
    
    def __init__(self, allow_build_file_edits: bool = False):
        self.allow_build_file_edits = allow_build_file_edits
        self.build_file_patterns = [
            r'pom\.xml$',
            r'build\.gradle$',
            r'build\.gradle\.kts$',
            r'settings\.gradle$',
            r'settings\.gradle\.kts$',
            r'\.mvn/',
            r'gradle/',
            r'gradlew$',
            r'gradlew\.bat$',
            r'mvnw$',
            r'mvnw\.cmd$'
        ]
    
    def validate_patch(self, patch_content: str) -> Tuple[bool, Optional[str]]:
        """Validate a patch for basic syntax and safety."""
        if not patch_content.strip():
            return False, "Empty patch content"
        
        # Check if it looks like a unified diff
        if not patch_content.startswith(('---', 'diff --git')):
            return False, "Patch does not appear to be a unified diff"
        
        # Parse patch to check for build file modifications
        if not self.allow_build_file_edits:
            build_file_violations = self._check_build_file_modifications(patch_content)
            if build_file_violations:
                return False, f"Build file modifications detected: {', '.join(build_file_violations)}"
        
        # Check for potentially dangerous operations
        dangerous_patterns = [
            r'rm\s+',
            r'rmdir\s+',
            r'del\s+',
            r'rm\s+-rf',
            r'chmod\s+',
            r'chown\s+'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, patch_content, re.IGNORECASE):
                return False, f"Potentially dangerous operation detected: {pattern}"
        
        return True, None
    
    def _check_build_file_modifications(self, patch_content: str) -> List[str]:
        """Check if patch modifies build files."""
        violations = []
        
        # Extract file paths from patch
        file_paths = self._extract_file_paths(patch_content)
        
        for file_path in file_paths:
            for pattern in self.build_file_patterns:
                if re.search(pattern, file_path, re.IGNORECASE):
                    violations.append(file_path)
                    break
        
        return violations
    
    def _extract_file_paths(self, patch_content: str) -> List[str]:
        """Extract file paths from a unified diff."""
        file_paths = []
        
        # Pattern for unified diff file headers
        pattern = r'^---\s+a/(.+)$|^\+\+\+\s+b/(.+)$'
        
        for line in patch_content.split('\n'):
            match = re.match(pattern, line)
            if match:
                file_path = match.group(1) or match.group(2)
                if file_path and file_path not in file_paths:
                    file_paths.append(file_path)
        
        return file_paths
    
    def analyze_patch(self, patch_content: str) -> Dict[str, any]:
        """Analyze a patch and return statistics."""
        file_paths = self._extract_file_paths(patch_content)
        
        # Count lines added/removed/modified
        lines_added = 0
        lines_deleted = 0
        lines_modified = 0
        
        in_hunk = False
        for line in patch_content.split('\n'):
            if line.startswith('@@'):
                in_hunk = True
                continue
            
            if in_hunk and line.startswith('+') and not line.startswith('+++'):
                lines_added += 1
            elif in_hunk and line.startswith('-') and not line.startswith('---'):
                lines_deleted += 1
            elif in_hunk and line.startswith(' '):
                lines_modified += 1
        
        return {
            "files_touched": len(file_paths),
            "loc_added": lines_added,
            "loc_deleted": lines_deleted,
            "loc_modified": lines_modified,
            "file_paths": file_paths,
            "build_files_modified": any(
                any(re.search(pattern, path, re.IGNORECASE) for pattern in self.build_file_patterns)
                for path in file_paths
            )
        }


class PatchApplier:
    """Applies patches to repositories with validation and rollback."""
    
    def __init__(self, repo_manager: RepositoryManager, allow_build_file_edits: bool = False):
        self.repo_manager = repo_manager
        self.validator = PatchValidator(allow_build_file_edits)
    
    def apply_patch(
        self,
        repo_path: Path,
        patch_content: str,
        case_id: str
    ) -> PatchResult:
        """Apply a patch to a repository with validation and error handling."""
        
        # Validate patch first
        is_valid, error_message = self.validator.validate_patch(patch_content)
        if not is_valid:
            return PatchResult(
                apply_success=False,
                error_message=error_message,
                files_touched=0,
                loc_added=0,
                loc_deleted=0,
                loc_modified=0,
                build_files_modified=False
            )
        
        # Analyze patch
        analysis = self.validator.analyze_patch(patch_content)
        
        # Save current state for rollback
        try:
            current_status = self.repo_manager.get_status(repo_path)
            if current_status.get("is_dirty", False):
                # Repository is dirty, reset it first
                self.repo_manager.reset_repository(repo_path)
        except Exception as e:
            return PatchResult(
                apply_success=False,
                error_message=f"Failed to prepare repository: {str(e)}",
                files_touched=analysis["files_touched"],
                loc_added=analysis["loc_added"],
                loc_deleted=analysis["loc_deleted"],
                loc_modified=analysis["loc_modified"],
                build_files_modified=analysis["build_files_modified"]
            )
        
        # Apply the patch
        try:
            result = self.repo_manager.apply_patch(repo_path, patch_content)
            
            if result["success"]:
                return PatchResult(
                    apply_success=True,
                    error_message=None,
                    files_touched=analysis["files_touched"],
                    loc_added=analysis["loc_added"],
                    loc_deleted=analysis["loc_deleted"],
                    loc_modified=analysis["loc_modified"],
                    build_files_modified=analysis["build_files_modified"]
                )
            else:
                return PatchResult(
                    apply_success=False,
                    error_message=result["message"],
                    files_touched=analysis["files_touched"],
                    loc_added=analysis["loc_added"],
                    loc_deleted=analysis["loc_deleted"],
                    loc_modified=analysis["loc_modified"],
                    build_files_modified=analysis["build_files_modified"]
                )
                
        except Exception as e:
            return PatchResult(
                apply_success=False,
                error_message=f"Unexpected error applying patch: {str(e)}",
                files_touched=analysis["files_touched"],
                loc_added=analysis["loc_added"],
                loc_deleted=analysis["loc_deleted"],
                loc_modified=analysis["loc_modified"],
                build_files_modified=analysis["build_files_modified"]
            )
    
    def rollback_patch(self, repo_path: Path) -> bool:
        """Rollback any applied patches."""
        try:
            self.repo_manager.reset_repository(repo_path)
            return True
        except Exception:
            return False
    
    def save_patch_artifact(self, patch_content: str, artifacts_dir: Path) -> Path:
        """Save patch content as an artifact."""
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        patch_file = artifacts_dir / "patch.diff"
        
        with open(patch_file, 'w', encoding='utf-8') as f:
            f.write(patch_content)
        
        return patch_file


def create_patch_applier(
    repo_manager: RepositoryManager,
    allow_build_file_edits: bool = False
) -> PatchApplier:
    """Create a patch applier instance."""
    return PatchApplier(repo_manager, allow_build_file_edits)
