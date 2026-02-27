"""Notion poller - discovers and claims tasks."""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from notion_client import Client

from novaos.db.supabase_client import get_db, SupabaseClient
from novaos.core.state_machine import RunState


class NotionPoller:
    """Polls Notion for tasks ready for agent processing."""
    
    def __init__(self, db: SupabaseClient = None):
        self.notion = Client(auth=os.getenv("NOTION_TOKEN"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")
        self.db = db or get_db()
    
    def query_ready_tasks(self) -> List[Dict[str, Any]]:
        """
        Query Notion for tasks with:
        - Status = "Agent's Turn"
        - novaos_run_id is empty (not yet claimed)
        """
        try:
            response = self.notion.databases.query(
                database_id=self.database_id,
                filter={
                    "and": [
                        {
                            "property": "Status",
                            "status": {
                                "equals": "Agent's Turn"
                            }
                        }
                    ]
                }
            )
            
            tasks = []
            for page in response.get("results", []):
                properties = page.get("properties", {})
                
                # Check if already claimed (novaos_run_id exists)
                run_id_prop = properties.get("novaos_run_id", {})
                if run_id_prop.get("rich_text"):
                    # Already claimed, skip
                    continue
                
                task = {
                    "page_id": page["id"],
                    "url": page["url"],
                    "title": self._extract_title(properties),
                    "description": self._extract_description(properties),
                    "repo": self._extract_repo(properties),
                    "created_time": page["created_time"]
                }
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f"Error querying Notion: {e}")
            return []
    
    def _extract_title(self, properties: Dict) -> str:
        """Extract title from page properties."""
        title_prop = properties.get("Name", properties.get("Title", {}))
        if "title" in title_prop:
            return "".join([t["plain_text"] for t in title_prop["title"]])
        return "Untitled"
    
    def _extract_description(self, properties: Dict) -> str:
        """Extract description if available."""
        # Look for common description fields
        for key in ["Description", "description", "Notes", "notes", "Content", "content"]:
            if key in properties:
                prop = properties[key]
                if "rich_text" in prop:
                    return "".join([t["plain_text"] for t in prop["rich_text"]])
        return ""
    
    def _extract_repo(self, properties: Dict) -> str:
        """Extract target repo from properties."""
        # Look for repo field
        for key in ["Repo", "Repository", "repo", "repository", "Project", "project"]:
            if key in properties:
                prop = properties[key]
                if "select" in prop and prop["select"]:
                    return prop["select"]["name"]
                if "rich_text" in prop:
                    text = "".join([t["plain_text"] for t in prop["rich_text"]])
                    if text:
                        return text
        # Default based on context or raise error
        return "papkot-ai"  # Default for v0.1
    
    def claim_task(self, task: Dict[str, Any]) -> Optional[str]:
        """
        Claim a task atomically.
        
        1. Insert into Supabase (unique constraint prevents duplicates)
        2. Update Notion with run_id
        
        Returns run_id if successful, None if already claimed.
        """
        page_id = task["page_id"]
        
        # Try to claim in Supabase first (atomic due to unique constraint)
        run_id = self.db.claim_task(
            notion_page_id=page_id,
            title=task["title"],
            description=task["description"],
            repo=task["repo"]
        )
        
        if not run_id:
            # Already claimed
            print(f"Task {page_id} already claimed, skipping")
            return None
        
        # Update Notion with run_id
        try:
            self.notion.pages.update(
                page_id=page_id,
                properties={
                    "novaos_run_id": {
                        "rich_text": [
                            {
                                "text": {"content": run_id}
                            }
                        ]
                    }
                }
            )
            print(f"Claimed task {page_id} with run_id {run_id}")
            return run_id
            
        except Exception as e:
            # If Notion update fails, we should rollback the claim
            # For v0.1, we'll log and let it timeout
            print(f"Error updating Notion (claim will timeout): {e}")
            return run_id
    
    def poll_and_claim(self) -> List[str]:
        """
        Main polling loop.
        
        Returns list of newly claimed run_ids.
        """
        print(f"[{datetime.utcnow().isoformat()}] Polling Notion...")
        
        # Release stale claims first
        released = self.db.release_stale_claims(timeout_minutes=30)
        if released > 0:
            print(f"Released {released} stale claims")
        
        # Query for ready tasks
        tasks = self.query_ready_tasks()
        print(f"Found {len(tasks)} ready tasks")
        
        # Claim each task
        claimed = []
        for task in tasks:
            run_id = self.claim_task(task)
            if run_id:
                claimed.append(run_id)
        
        print(f"Claimed {len(claimed)} tasks")
        return claimed


def run_poller_once():
    """Run one poll cycle (for cron/testing)."""
    poller = NotionPoller()
    return poller.poll_and_claim()


if __name__ == "__main__":
    # Test mode
    import sys
    sys.path.insert(0, "/Users/mmi/Go/NovaStudio/projects/nova-os")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    claimed = run_poller_once()
    print(f"Claimed: {claimed}")
