"""Version control system operations for repository management."""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

import git
from git import Repo, InvalidGitRepositoryError


class RepositoryManager:
    """Manages Git repository operations for benchmark cases."""
    
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
    
    def clone_repository(self, repo_url: str, case_id: str) -> Path:
        """Clone a repository for a specific case."""
        case_workspace = self.workspace_dir / case_id
        case_workspace.mkdir(parents=True, exist_ok=True)
        
        repo_path = case_workspace / "repo"
        
        # Remove existing repo if it exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        try:
            # Clone the repository
            repo = Repo.clone_from(repo_url, repo_path)
            return repo_path
        except Exception as e:
            raise RuntimeError(f"Failed to clone repository {repo_url}: {str(e)}")
    
    def checkout_commit(self, repo_path: Path, commit_sha: str) -> None:
        """Checkout a specific commit in the repository."""
        try:
            repo = Repo(repo_path)
            
            # Ensure we have a clean working tree
            repo.git.checkout('-f', commit_sha)
            repo.git.clean('-fd')
            
            # Verify we're on the correct commit
            current_sha = repo.head.commit.hexsha
            if not current_sha.startswith(commit_sha):
                raise RuntimeError(f"Failed to checkout commit {commit_sha}, currently on {current_sha}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to checkout commit {commit_sha}: {str(e)}")
    
    def get_repository_info(self, repo_path: Path) -> dict:
        """Get information about the repository."""
        try:
            repo = Repo(repo_path)
            return {
                "url": repo.remotes.origin.url if repo.remotes.origin else "unknown",
                "current_commit": repo.head.commit.hexsha,
                "current_branch": repo.active_branch.name if repo.head.is_detached else "detached",
                "is_clean": not repo.is_dirty(),
                "untracked_files": repo.untracked_files
            }
        except Exception as e:
            return {"error": str(e)}
    
    def reset_repository(self, repo_path: Path) -> None:
        """Reset repository to clean state."""
        try:
            repo = Repo(repo_path)
            
            # Reset any staged changes
            repo.git.reset('--hard', 'HEAD')
            
            # Clean untracked files
            repo.git.clean('-fd')
            
            # Ensure we're not in a detached HEAD state
            if repo.head.is_detached:
                # Try to checkout the default branch
                try:
                    default_branch = repo.remotes.origin.refs.master.name.split('/')[-1]
                except:
                    try:
                        default_branch = repo.remotes.origin.refs.main.name.split('/')[-1]
                    except:
                        default_branch = "master"
                
                try:
                    repo.git.checkout(default_branch)
                except:
                    pass  # If we can't checkout default branch, stay detached
                    
        except Exception as e:
            raise RuntimeError(f"Failed to reset repository: {str(e)}")
    
    def apply_patch(self, repo_path: Path, patch_content: str) -> dict:
        """Apply a patch to the repository."""
        try:
            repo = Repo(repo_path)
            
            # Create a temporary patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(patch_content)
                patch_file = Path(f.name)
            
            try:
                # Apply the patch
                result = repo.git.apply('--index', str(patch_file))
                
                return {
                    "success": True,
                    "message": "Patch applied successfully",
                    "result": result
                }
                
            finally:
                # Clean up temporary file
                patch_file.unlink(missing_ok=True)
                
        except git.GitCommandError as e:
            return {
                "success": False,
                "message": f"Failed to apply patch: {str(e)}",
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error applying patch: {str(e)}",
                "error": str(e)
            }
    
    def get_diff(self, repo_path: Path) -> str:
        """Get the current diff of the repository."""
        try:
            repo = Repo(repo_path)
            return repo.git.diff()
        except Exception as e:
            return f"Error getting diff: {str(e)}"
    
    def get_status(self, repo_path: Path) -> dict:
        """Get the current status of the repository."""
        try:
            repo = Repo(repo_path)
            return {
                "is_dirty": repo.is_dirty(),
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
                "unstaged_files": [item.a_path for item in repo.index.diff(None)],
                "untracked_files": repo.untracked_files,
                "current_commit": repo.head.commit.hexsha,
                "current_branch": repo.active_branch.name if not repo.head.is_detached else "detached"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def cleanup_case(self, case_id: str) -> None:
        """Clean up workspace for a specific case."""
        case_workspace = self.workspace_dir / case_id
        if case_workspace.exists():
            shutil.rmtree(case_workspace)
    
    def cleanup_all(self) -> None:
        """Clean up all workspace directories."""
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
            self.workspace_dir.mkdir(parents=True, exist_ok=True)


def create_repository_manager(workspace_dir: Path) -> RepositoryManager:
    """Create a repository manager instance."""
    return RepositoryManager(workspace_dir)
