"""Concurrency management for NovaOS.

v0.1 Policy:
- Global worker pool: 3 concurrent workers (configurable)
- Per-repo concurrency: 1 (serialized to avoid conflicts)
"""
import asyncio
from typing import Dict, Set
from dataclasses import dataclass


@dataclass
class ConcurrencyPolicy:
    """v0.1 concurrency settings."""
    global_pool_size: int = 3
    per_repo_concurrency: int = 1


class ConcurrencyManager:
    """Manages concurrent execution respecting policy."""
    
    def __init__(self, policy: ConcurrencyPolicy = None):
        self.policy = policy or ConcurrencyPolicy()
        
        # Global semaphore for worker pool
        self.global_semaphore = asyncio.Semaphore(self.policy.global_pool_size)
        
        # Per-repo locks (repo -> semaphore)
        self._repo_locks: Dict[str, asyncio.Semaphore] = {}
        
        # Track active runs per repo
        self._active_runs: Dict[str, Set[str]] = {}
    
    async def acquire_repo_lock(self, repo: str, run_id: str) -> bool:
        """
        Try to acquire lock for repo.
        
        Returns True if acquired, False if repo is busy.
        """
        if repo not in self._repo_locks:
            self._repo_locks[repo] = asyncio.Semaphore(self.policy.per_repo_concurrency)
            self._active_runs[repo] = set()
        
        # Try to acquire without blocking
        if self._repo_locks[repo].locked():
            return False
        
        await self._repo_locks[repo].acquire()
        self._active_runs[repo].add(run_id)
        return True
    
    def release_repo_lock(self, repo: str, run_id: str):
        """Release lock for repo."""
        if repo in self._active_runs and run_id in self._active_runs[repo]:
            self._active_runs[repo].discard(run_id)
        
        if repo in self._repo_locks:
            try:
                self._repo_locks[repo].release()
            except ValueError:
                # Already released
                pass
    
    def is_repo_busy(self, repo: str) -> bool:
        """Check if repo has active workers."""
        if repo not in self._active_runs:
            return False
        return len(self._active_runs[repo]) >= self.policy.per_repo_concurrency
    
    async def execute_with_limits(self, repo: str, run_id: str, coro):
        """
        Execute coroutine respecting both global and per-repo limits.
        
        Usage:
            result = await concurrency_manager.execute_with_limits(
                "papkot-ai", run_id, worker.execute()
            )
        """
        async with self.global_semaphore:
            # Try to acquire repo lock
            if not await self.acquire_repo_lock(repo, run_id):
                raise RepoBusyError(f"Repo {repo} is busy with another task")
            
            try:
                return await coro
            finally:
                self.release_repo_lock(repo, run_id)
    
    def get_status(self) -> Dict:
        """Get current concurrency status."""
        return {
            "global_limit": self.policy.global_pool_size,
            "global_available": self.policy.global_pool_size - (self.global_semaphore._value or 0),
            "per_repo_limit": self.policy.per_repo_concurrency,
            "active_repos": {
                repo: len(runs) 
                for repo, runs in self._active_runs.items()
            }
        }


class RepoBusyError(Exception):
    """Raised when trying to work on a repo that's already busy."""
    pass


# Singleton
_manager: ConcurrencyManager = None


def get_concurrency_manager() -> ConcurrencyManager:
    """Get singleton concurrency manager."""
    global _manager
    if _manager is None:
        _manager = ConcurrencyManager()
    return _manager
