#!/usr/bin/env python3
"""
AlgorithmPhaseReport.py -- Writes algorithm state to algorithm-phase.json

Usage:
  python AlgorithmPhaseReport.py phase --phase OBSERVE --task "Auth rebuild" --sla Standard
  python AlgorithmPhaseReport.py criterion --id 1 --desc "JWT rejects expired tokens" --type criterion --status pending
  python AlgorithmPhaseReport.py criterion --id 1 --status completed --evidence "Tests pass"
  python AlgorithmPhaseReport.py agent --name engineer-1 --type Engineer --status active --task "JWT middleware"
  python AlgorithmPhaseReport.py capabilities --list "Task Tool,Engineer Agents,Skills"
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

STATE_DIR = os.path.join(str(Path.home()), ".claude", "MEMORY", "STATE")
STATE_FILE = os.path.join(STATE_DIR, "algorithm-phase.json")


def read_state() -> dict[str, Any]:
    try:
        raw = Path(STATE_FILE).read_text().strip()
        if not raw or raw == "{}":
            raise ValueError("empty")
        return json.loads(raw)
    except Exception:
        return {
            "active": False,
            "sessionId": "",
            "taskDescription": "",
            "currentPhase": "IDLE",
            "phaseStartedAt": int(time.time() * 1000),
            "algorithmStartedAt": int(time.time() * 1000),
            "sla": "Standard",
            "criteria": [],
            "agents": [],
            "capabilities": [],
            "phaseHistory": [],
        }


def write_state(state: dict[str, Any]) -> None:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        Path(STATE_FILE).write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def get_arg(args: list[str], flag: str) -> Optional[str]:
    try:
        idx = args.index(flag)
        if idx + 1 >= len(args):
            return None
        return args[idx + 1]
    except ValueError:
        return None


def main() -> None:
    try:
        argv = sys.argv[1:]
        if not argv:
            print("Usage: AlgorithmPhaseReport.py <phase|criterion|agent|capabilities> [options]")
            sys.exit(0)

        command = argv[0]
        rest = argv[1:]
        state = read_state()

        if command == "phase":
            phase = get_arg(rest, "--phase")
            task = get_arg(rest, "--task")
            sla = get_arg(rest, "--sla")
            session_id = get_arg(rest, "--session")
            prd_path = get_arg(rest, "--prd")

            if not phase:
                print("--phase required", file=sys.stderr)
                sys.exit(1)

            # Close previous phase in history
            current = state.get("currentPhase", "IDLE")
            if current and current not in ("IDLE", phase):
                for h in state.get("phaseHistory", []):
                    if h.get("phase") == current and not h.get("completedAt"):
                        h["completedAt"] = int(time.time() * 1000)
                        h["criteriaCount"] = len(state.get("criteria", []))
                        h["agentCount"] = len(state.get("agents", []))

            state["active"] = phase not in ("IDLE", "COMPLETE")
            state["currentPhase"] = phase
            state["phaseStartedAt"] = int(time.time() * 1000)

            if task:
                state["taskDescription"] = task
            if sla:
                state["sla"] = sla
            if session_id:
                state["sessionId"] = session_id
            if prd_path:
                state["prdPath"] = prd_path

            if not state.get("algorithmStartedAt") or phase == "OBSERVE":
                state["algorithmStartedAt"] = int(time.time() * 1000)

            state.setdefault("phaseHistory", []).append({
                "phase": phase,
                "startedAt": int(time.time() * 1000),
                "criteriaCount": len(state.get("criteria", [])),
                "agentCount": len(state.get("agents", [])),
            })

        elif command == "criterion":
            cid = get_arg(rest, "--id")
            desc = get_arg(rest, "--desc")
            ctype = get_arg(rest, "--type")
            status = get_arg(rest, "--status")
            evidence = get_arg(rest, "--evidence")

            if not cid:
                print("--id required", file=sys.stderr)
                sys.exit(1)

            criteria = state.setdefault("criteria", [])
            existing = next((c for c in criteria if c.get("id") == cid), None)

            if existing:
                if desc:
                    existing["description"] = desc
                if ctype:
                    existing["type"] = ctype
                if status:
                    existing["status"] = status
                if evidence:
                    existing["evidence"] = evidence
            else:
                criteria.append({
                    "id": cid,
                    "description": desc or "",
                    "type": ctype or "criterion",
                    "status": status or "pending",
                    "evidence": evidence,
                    "createdInPhase": state.get("currentPhase", "IDLE"),
                })

        elif command == "agent":
            name = get_arg(rest, "--name")
            agent_type = get_arg(rest, "--type")
            status = get_arg(rest, "--status")
            task = get_arg(rest, "--task")

            if not name:
                print("--name required", file=sys.stderr)
                sys.exit(1)

            agents = state.setdefault("agents", [])
            existing = next((a for a in agents if a.get("name") == name), None)

            if existing:
                if agent_type:
                    existing["agentType"] = agent_type
                if status:
                    existing["status"] = status
                if task:
                    existing["task"] = task
                existing["phase"] = state.get("currentPhase", "IDLE")
            else:
                agents.append({
                    "name": name,
                    "agentType": agent_type or "general-purpose",
                    "status": status or "active",
                    "task": task,
                    "phase": state.get("currentPhase", "IDLE"),
                })

        elif command == "capabilities":
            cap_list = get_arg(rest, "--list")
            if cap_list:
                state["capabilities"] = [s.strip() for s in cap_list.split(",")]

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

        write_state(state)
    except Exception:
        pass


if __name__ == "__main__":
    main()
