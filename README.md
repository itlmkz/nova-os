# NovaOS v0.1

LangGraph-based task orchestration for Nova Studio portfolio companies.

## Architecture

Cron polls Notion -> LangGraph(Python) + Supabase -> GitHub Issues -> Goose Worker -> Validate -> Merge -> Telegram -> Notion Done

## Quick Start

1. Setup Supabase: Run schema.sql in Supabase SQL Editor
2. Configure: cp env.example .env && edit .env
3. Install: pip install -r requirements.txt
4. Run: python -m novaos.core.orchestrator

## State Machine

PENDING -> CLAIMED -> WORKING -> VALIDATING -> MERGING -> DONE
                |
              BLOCKED -> (human approval) -> MERGING
