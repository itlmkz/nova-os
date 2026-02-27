"""State machine definitions and transitions for NovaOS."""
from enum import Enum
from typing import Set, Dict, List


class RunState(str, Enum):
    """Valid states for a run."""
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    WORKING = "WORKING"
    VALIDATING = "VALIDATING"
    MERGING = "MERGING"
    DONE = "DONE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class IssueState(str, Enum):
    """Valid states for an issue."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


# Valid state transitions
VALID_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.PENDING: {RunState.CLAIMED},
    RunState.CLAIMED: {RunState.WORKING, RunState.FAILED, RunState.BLOCKED},
    RunState.WORKING: {RunState.VALIDATING, RunState.FAILED, RunState.BLOCKED},
    RunState.VALIDATING: {RunState.MERGING, RunState.BLOCKED, RunState.FAILED},
    RunState.MERGING: {RunState.DONE, RunState.FAILED, RunState.BLOCKED},
    RunState.BLOCKED: {RunState.WORKING, RunState.MERGING, RunState.FAILED},
    RunState.FAILED: set(),  # Terminal state
    RunState.DONE: set(),    # Terminal state
}


def is_valid_transition(from_state: RunState, to_state: RunState) -> bool:
    """Check if transition is allowed."""
    if from_state not in VALID_TRANSITIONS:
        return False
    return to_state in VALID_TRANSITIONS[from_state]


def get_allowed_transitions(state: RunState) -> List[RunState]:
    """Get list of allowed next states."""
    if state not in VALID_TRANSITIONS:
        return []
    return list(VALID_TRANSITIONS[state])


def get_terminal_states() -> Set[RunState]:
    """Get states that cannot transition further."""
    return {RunState.DONE, RunState.FAILED}


def requires_human_approval(state: RunState) -> bool:
    """Check if state requires human intervention."""
    return state == RunState.BLOCKED
