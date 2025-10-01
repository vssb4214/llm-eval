"""Build and test execution system for Maven/Gradle projects."""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .types import BuildResult, BuildSystem


class BuildExecutor:
    """Executes build and test commands for Java projects."""
    
    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds
    
    async def execute_build_and_test(
        self,
        repo_path: Path,
        build_system: BuildSystem,
        failing_test: Optional[str] = None
    ) -> BuildResult:
        """Execute build and test for a Java project."""
        
        # First, try to build the project
        build_result = await self._execute_build(repo_path, build_system)
        
        if not build_result["success"]:
            return BuildResult(
                build_pass=False,
                test_pass=False,
                build_duration=build_result["duration"],
                test_duration=0.0,
                build_output=build_result["output"],
                test_output="",
                error_message=build_result["error"]
            )
        
        # If build succeeded, run tests
        test_result = await self._execute_tests(repo_path, build_system, failing_test)
        
        return BuildResult(
            build_pass=True,
            test_pass=test_result["success"],
            build_duration=build_result["duration"],
            test_duration=test_result["duration"],
            build_output=build_result["output"],
            test_output=test_result["output"],
            error_message=test_result["error"]
        )
    
    async def _execute_build(self, repo_path: Path, build_system: BuildSystem) -> Dict[str, any]:
        """Execute build command."""
        if build_system == BuildSystem.MAVEN:
            return await self._execute_maven_build(repo_path)
        elif build_system == BuildSystem.GRADLE:
            return await self._execute_gradle_build(repo_path)
        else:
            return {
                "success": False,
                "duration": 0.0,
                "output": "",
                "error": f"Unsupported build system: {build_system}"
            }
    
    async def _execute_tests(
        self,
        repo_path: Path,
        build_system: BuildSystem,
        failing_test: Optional[str] = None
    ) -> Dict[str, any]:
        """Execute test command."""
        if build_system == BuildSystem.MAVEN:
            return await self._execute_maven_tests(repo_path, failing_test)
        elif build_system == BuildSystem.GRADLE:
            return await self._execute_gradle_tests(repo_path, failing_test)
        else:
            return {
                "success": False,
                "duration": 0.0,
                "output": "",
                "error": f"Unsupported build system: {build_system}"
            }
    
    async def _execute_maven_build(self, repo_path: Path) -> Dict[str, any]:
        """Execute Maven build command."""
        start_time = time.time()
        
        try:
            # Try to compile without tests first
            result = await self._run_command(
                ["mvn", "compile", "-q", "-DskipTests=true"],
                cwd=repo_path,
                timeout=self.timeout_seconds
            )
            
            duration = time.time() - start_time
            
            if result["returncode"] == 0:
                return {
                    "success": True,
                    "duration": duration,
                    "output": result["stdout"],
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "duration": duration,
                    "output": result["stdout"] + result["stderr"],
                    "error": f"Maven build failed with return code {result['returncode']}"
                }
                
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Maven build timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Maven build failed with exception: {str(e)}"
            }
    
    async def _execute_maven_tests(
        self,
        repo_path: Path,
        failing_test: Optional[str] = None
    ) -> Dict[str, any]:
        """Execute Maven test command."""
        start_time = time.time()
        
        try:
            # Build test command
            cmd = ["mvn", "test", "-q"]
            
            # If we know the failing test, try to run just that test
            if failing_test:
                cmd.extend(["-Dtest", failing_test])
            
            result = await self._run_command(
                cmd,
                cwd=repo_path,
                timeout=self.timeout_seconds
            )
            
            duration = time.time() - start_time
            
            # Maven returns 0 on success, non-zero on test failures
            # We consider it successful if it runs without compilation errors
            success = result["returncode"] == 0 or "BUILD SUCCESS" in result["stdout"]
            
            return {
                "success": success,
                "duration": duration,
                "output": result["stdout"] + result["stderr"],
                "error": None if success else f"Maven tests failed with return code {result['returncode']}"
            }
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Maven tests timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Maven tests failed with exception: {str(e)}"
            }
    
    async def _execute_gradle_build(self, repo_path: Path) -> Dict[str, any]:
        """Execute Gradle build command."""
        start_time = time.time()
        
        try:
            # Try to compile without tests first
            result = await self._run_command(
                ["./gradlew", "compileJava", "-q"],
                cwd=repo_path,
                timeout=self.timeout_seconds
            )
            
            duration = time.time() - start_time
            
            if result["returncode"] == 0:
                return {
                    "success": True,
                    "duration": duration,
                    "output": result["stdout"],
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "duration": duration,
                    "output": result["stdout"] + result["stderr"],
                    "error": f"Gradle build failed with return code {result['returncode']}"
                }
                
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Gradle build timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Gradle build failed with exception: {str(e)}"
            }
    
    async def _execute_gradle_tests(
        self,
        repo_path: Path,
        failing_test: Optional[str] = None
    ) -> Dict[str, any]:
        """Execute Gradle test command."""
        start_time = time.time()
        
        try:
            # Build test command
            cmd = ["./gradlew", "test", "-q"]
            
            # If we know the failing test, try to run just that test
            if failing_test:
                cmd.extend(["--tests", failing_test])
            
            result = await self._run_command(
                cmd,
                cwd=repo_path,
                timeout=self.timeout_seconds
            )
            
            duration = time.time() - start_time
            
            # Gradle returns 0 on success, non-zero on test failures
            success = result["returncode"] == 0
            
            return {
                "success": success,
                "duration": duration,
                "output": result["stdout"] + result["stderr"],
                "error": None if success else f"Gradle tests failed with return code {result['returncode']}"
            }
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Gradle tests timed out after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "duration": duration,
                "output": "",
                "error": f"Gradle tests failed with exception: {str(e)}"
            }
    
    async def _run_command(
        self,
        cmd: List[str],
        cwd: Path,
        timeout: int
    ) -> Dict[str, any]:
        """Run a command asynchronously with timeout."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return {
                "returncode": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore')
            }
            
        except asyncio.TimeoutError:
            # Kill the process if it times out
            try:
                process.kill()
                await process.wait()
            except:
                pass
            raise
    
    def check_build_tools(self, repo_path: Path) -> Dict[str, bool]:
        """Check if required build tools are available."""
        checks = {}
        
        # Check for Maven
        try:
            result = subprocess.run(
                ["mvn", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            checks["maven"] = result.returncode == 0
        except:
            checks["maven"] = False
        
        # Check for Gradle wrapper
        gradle_wrapper = repo_path / "gradlew"
        checks["gradle_wrapper"] = gradle_wrapper.exists() and gradle_wrapper.is_file()
        
        # Check for Gradle (system)
        try:
            result = subprocess.run(
                ["gradle", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            checks["gradle"] = result.returncode == 0
        except:
            checks["gradle"] = False
        
        return checks


def create_build_executor(timeout_seconds: int = 300) -> BuildExecutor:
    """Create a build executor instance."""
    return BuildExecutor(timeout_seconds)
