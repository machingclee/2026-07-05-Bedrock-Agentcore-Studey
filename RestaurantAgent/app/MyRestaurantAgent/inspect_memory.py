#!/usr/bin/env python3
"""Inspect AgentCore Memory — events and extracted records for a given actor."""

import os
import sys
from bedrock_agentcore.memory import MemoryClient

REGION = os.getenv("AWS_REGION", "us-east-1")
MEMORY_ID = os.getenv("MEMORY_RESTAURANTMEMORY_ID", os.getenv("MEMORY_ID", ""))


def inspect(actor_id: str, max_events: int = 20) -> None:
    client = MemoryClient(region_name=REGION)

    print(f"{'='*60}")
    print(f"Memory ID : {MEMORY_ID}")
    print(f"Actor ID  : {actor_id}")
    print(f"{'='*60}")

    # ── Discover session IDs from memory records ─────────────────────
    session_ids: set[str] = set()
    try:
        resp = client.list_memory_records(
            memoryId=MEMORY_ID,
            namespace_path="/strategies/",
        )
        for r in resp.get("memoryRecordSummaries", []):
            for ns in r.get("namespaces", []):
                parts = ns.split("/")
                if "sessions" in parts:
                    idx = parts.index("sessions")
                    if idx + 1 < len(parts):
                        session_ids.add(parts[idx + 1])
    except Exception as err:
        print(f"  Error discovering sessions: {err}")

    print(f"Found {len(session_ids)} session(s): {session_ids or '(none)'}")

    # ── Raw events per session ───────────────────────────────────────
    for sid in sorted(session_ids):
        print(f"\n─── Raw Events — session {sid} (last {max_events}) ───")
        try:
            events = client.list_events(
                memory_id=MEMORY_ID,
                actor_id=actor_id,
                session_id=sid,
                max_results=max_events,
            )
            if not events:
                print("  (no events)")
                continue
            for i, e in enumerate(events, 1):
                role = e.get("role", "?")
                content = e.get("content", {})
                if isinstance(content, dict):
                    text = content.get("text", str(content))
                else:
                    text = str(content)
                ts = str(e.get("timestamp", ""))[:19]
                print(f"  [{i}] {role}: {text[:150]}")
                if ts:
                    print(f"       {ts}")
        except Exception as err:
            print(f"  Error: {err}")

    # If no session IDs found, try actor_id as session_id
    if not session_ids:
        print(f"\n─── Raw Events — session {actor_id} (fallback) ───")
        try:
            events = client.list_events(
                memory_id=MEMORY_ID,
                actor_id=actor_id,
                session_id=actor_id,
                max_results=max_events,
            )
            if not events:
                print("  (no events)")
            else:
                for i, e in enumerate(events, 1):
                    role = e.get("role", "?")
                    content = e.get("content", {})
                    text = content.get("text", str(content)) if isinstance(content, dict) else str(content)
                    print(f"  [{i}] {role}: {text[:150]}")
        except Exception as err:
            print(f"  Error: {err}")

    # ── Memory records ───────────────────────────────────────────────
    print(f"\n─── Memory Records ───")
    try:
        resp = client.list_memory_records(
            memoryId=MEMORY_ID,
            namespace_path="/strategies/",
        )
        summaries = resp.get("memoryRecordSummaries", [])
        mine = [
            r for r in summaries
            if any(actor_id in ns for ns in r.get("namespaces", []))
        ]
        if not summaries:
            print("  (no records)")
        elif not mine:
            print(f"  (none for this actor among {len(summaries)} total)")
        else:
            for r in mine:
                strategy = r.get("memoryStrategyId", "?")
                content = r.get("content", {})
                text = content.get("text", str(content)) if isinstance(content, dict) else str(content)
                for ns in r.get("namespaces", []):
                    print(f"  strategy: {strategy}")
                    print(f"  namespace: {ns}")
                    print(f"  content:   {text[:300]}")
                    ts = str(r.get("createdAt", ""))[:19]
                    if ts:
                        print(f"  created:   {ts}")
                    print()
    except Exception as err:
        print(f"  Error: {err}")

    # ── Strategies ───────────────────────────────────────────────────
    print(f"─── Strategies ───")
    try:
        strategies = client.get_memory_strategies(MEMORY_ID)
        if not strategies:
            print("  (none)")
        for s in strategies:
            print(f"  {s.get('type', '?'):15s}  name={s.get('name', '?')}  "
                  f"status={s.get('status', '?')}")
    except Exception as err:
        print(f"  Error: {err}")


if __name__ == "__main__":
    actor = sys.argv[1] if len(sys.argv) > 1 else "anonymous"
    inspect(actor)
