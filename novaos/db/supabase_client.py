"""Supabase client for NovaOS - single source of truth."""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import uuid4

from supabase import create_client, Client


class SupabaseClient:
    """Manages all database operations with idempotency guarantees."""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY required")
        self.client: Client = create_client(self.url, self.key)
    
    def claim_task(self, notion_page_id: str, title: str, 
                   description: str, repo: str) -> Optional[str]:
        """
        Atomically claim a Notion task.
        
        Returns run_id if claimed, None if already claimed (idempotent).
        Uses unique constraint on notion_page_id to prevent races.
        """
        run_id = str(uuid4())
        
        try:
            # Try to insert - will fail if notion_page_id already exists
            result = self.client.table("runs").insert({
                "id": run_id,
                "notion_page_id": notion_page_id,
                "state": "CLAIMED",
                "title": title,
                "description": description,
                "repo": repo,
                "claimed_at": datetime.utcnow().isoformat(),
                "retry_count": 0
            }).execute()
            
            # Log the transition
            self.log_transition(run_id, None, "CLAIMED", "Task claimed from Notion")
            
            return run_id
            
        except Exception as e:
            # Unique constraint violation = already claimed
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                return None
            raise
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        result = self.client.table("runs").select("*").eq("id", run_id).execute()
        if result.data:
            return result.data[0]
        return None
    
    def get_run_by_notion(self, notion_page_id: str) -> Optional[Dict[str, Any]]:
        """Get run by Notion page ID."""
        result = self.client.table("runs").select("*").eq("notion_page_id", notion_page_id).execute()
        if result.data:
            return result.data[0]
        return None
    
    def update_run_state(self, run_id: str, new_state: str, 
                         reason: str = "", metadata: Dict = None) -> bool:
        """Update run state with transition logging."""
        # Get current state
        run = self.get_run(run_id)
        if not run:
            return False
        
        old_state = run.get("state")
        
        # Update the run
        update_data = {
            "state": new_state,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if new_state == "DONE":
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        if metadata:
            # Merge with existing metadata if any
            existing_metadata = run.get("metadata") or {}
            existing_metadata.update(metadata)
            update_data["metadata"] = existing_metadata
        
        self.client.table("runs").update(update_data).eq("id", run_id).execute()
        
        # Log transition
        self.log_transition(run_id, old_state, new_state, reason, metadata)
        
        return True
    
    def create_issue(self, run_id: str, issue_number: int, 
                     issue_url: str, title: str, worker_type: str,
                     description: str = "") -> bool:
        """Create run_issue record (idempotent per run_id + worker_type)."""
        try:
            # Check if issue already exists for this worker type
            existing = self.client.table("run_issues").select("*").eq("run_id", run_id).eq("worker_type", worker_type).execute()
            
            if existing.data:
                # Already exists, update it
                self.client.table("run_issues").update({
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                    "title": title,
                    "description": description,
                    "status": "open",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("run_id", run_id).eq("worker_type", worker_type).execute()
            else:
                # Create new
                self.client.table("run_issues").insert({
                    "run_id": run_id,
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                    "title": title,
                    "description": description,
                    "worker_type": worker_type,
                    "status": "open"
                }).execute()
            
            return True
        except Exception as e:
            print(f"Error creating issue: {e}")
            return False
    
    def update_issue_status(self, run_id: str, worker_type: str,
                           status: str, pr_url: str = None) -> bool:
        """Update issue status and PR URL."""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if pr_url:
            update_data["pr_url"] = pr_url
        
        self.client.table("run_issues").update(update_data).eq("run_id", run_id).eq("worker_type", worker_type).execute()
        return True
    
    def get_run_issues(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all issues for a run."""
        result = self.client.table("run_issues").select("*").eq("run_id", run_id).execute()
        return result.data or []
    
    def are_all_issues_closed(self, run_id: str) -> bool:
        """Check if all issues for a run are closed."""
        issues = self.get_run_issues(run_id)
        if not issues:
            return False
        return all(issue.get("status") == "closed" for issue in issues)
    
    def log_transition(self, run_id: str, from_state: Optional[str],
                       to_state: str, reason: str = "", 
                       metadata: Dict = None):
        """Log state transition for audit."""
        self.client.table("run_transitions").insert({
            "run_id": run_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "metadata": metadata or {}
        }).execute()
    
    def get_pending_runs(self) -> List[Dict[str, Any]]:
        """Get all runs in PENDING state (for poller)."""
        # Actually we query Notion directly, but this is useful for debugging
        result = self.client.table("runs").select("*").eq("state", "PENDING").execute()
        return result.data or []
    
    def get_claimed_runs(self) -> List[Dict[str, Any]]:
        """Get all claimed runs that haven't started working."""
        result = self.client.table("runs").select("*").eq("state", "CLAIMED").execute()
        return result.data or []
    
    def release_stale_claims(self, timeout_minutes: int = 30) -> int:
        """Release claims that haven't progressed in timeout_minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        # Find stale claimed runs
        result = self.client.table("runs").select("*").eq("state", "CLAIMED").lt("claimed_at", cutoff.isoformat()).execute()
        
        released = 0
        for run in result.data or []:
            self.update_run_state(
                run["id"], 
                "PENDING",
                f"Claim released after {timeout_minutes}min timeout"
            )
            released += 1
        
        return released


# Singleton instance
_db: Optional[SupabaseClient] = None


def get_db() -> SupabaseClient:
    """Get or create Supabase client singleton."""
    global _db
    if _db is None:
        _db = SupabaseClient()
    return _db
