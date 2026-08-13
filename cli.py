#!/usr/bin/env python3
import sys
import os
import argparse
import json
import time
import requests

DEFAULT_SERVER_URL = os.getenv("AGENTMESH_URL", "http://localhost:8000")


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
  █████╗  ██████╗ ███████╗███╗   ██╗████████╗███╗   ███╗███████╗███████╗██╗  ██╗
 ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝████╗ ████║██╔════╝██╔════╝██║  ██║
 ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██╔████╔██║█████╗  ███████╗███████║
 ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║
 ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║ ╚═╝ ██║███████╗███████║██║  ██║
 ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
{Colors.ENDC}{Colors.HEADER}    Zuctro AgentMesh Enterprise Control Plane & Governance Gateway CLI (AM-CP-v2.5){Colors.ENDC}\n"""
    print(banner)


def get_base_url(args):
    return getattr(args, 'url', DEFAULT_SERVER_URL).rstrip('/')


def cmd_status(args):
    url = get_base_url(args)
    try:
        res = requests.get(f"{url}/api/info", timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            summary = data.get("summary", {})
            print(f"{Colors.BOLD}🌐 Control Plane URL:{Colors.ENDC} {url}")
            print(f"{Colors.BOLD}📋 Specification:{Colors.ENDC} {data.get('specification')} ({data.get('version')})")
            print(f"{Colors.BOLD}💚 System Status:{Colors.ENDC} {Colors.GREEN}{data.get('status')}{Colors.ENDC}\n")

            print(f"{Colors.BOLD}📊 System Summary:{Colors.ENDC}")
            print(f"  • Total Tasks Submitted : {Colors.CYAN}{summary.get('total_tasks')}{Colors.ENDC}")
            print(f"  • Tasks Queued          : {Colors.WARNING}{summary.get('queued_tasks')}{Colors.ENDC}")
            print(f"  • Tasks Completed       : {Colors.GREEN}{summary.get('completed_tasks')}{Colors.ENDC}")
            print(f"  • Tasks Failed          : {Colors.FAIL}{summary.get('failed_tasks')}{Colors.ENDC}")
            print(f"  • Active Worker Nodes   : {Colors.BLUE}{summary.get('active_workers')} / {summary.get('total_workers')}{Colors.ENDC}")
            print(f"  • Tokens Burned         : {summary.get('total_tokens_burned'):,}")
            print(f"  • Total USD Cost        : {Colors.WARNING}${summary.get('total_cost_usd'):.4f}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Error fetching status: HTTP {res.status_code}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Cannot connect to AgentMesh server at {url}: {e}{Colors.ENDC}")


def cmd_task_submit(args):
    url = get_base_url(args)
    hitl_tools = [t.strip() for t in args.hitl_tools.split(',')] if args.hitl_tools else []

    payload = {
        "tenant_id": args.tenant,
        "cost_center": args.cost_center,
        "agent_type": args.agent_type,
        "priority": args.priority,
        "governance": {
            "max_token_budget": args.max_tokens,
            "max_cost_usd": args.max_cost,
            "pii_redaction": not args.no_pii,
            "require_hitl_for_tools": hitl_tools
        },
        "payload": {
            "instruction": args.instruction
        }
    }

    try:
        res = requests.post(f"{url}/v1/tasks", json=payload, timeout=5.0)
        data = res.json()

        if res.status_code == 201:
            state = data.get("state")
            state_color = Colors.GREEN if state == "QUEUED" else Colors.WARNING
            print(f"\n{Colors.GREEN}✅ Task Submitted Successfully!{Colors.ENDC}")
            print(f"  • Task ID          : {Colors.BOLD}{data.get('task_id')}{Colors.ENDC}")
            print(f"  • Initial State    : {state_color}{state}{Colors.ENDC}")
            if data.get("hitl_trigger_tool"):
                print(f"  • HITL Trigger     : {Colors.WARNING}{data.get('hitl_trigger_tool')}{Colors.ENDC}")
            print(f"  • Message          : {data.get('message')}\n")

            if args.follow:
                cmd_task_stream_internal(url, data.get('task_id'))
        else:
            print(f"\n{Colors.FAIL}❌ Task Submission Rejected by Governance Gate!{Colors.ENDC}")
            print(f"  • Error Detail : {data.get('detail')}\n")
    except Exception as e:
        print(f"{Colors.FAIL}Error submitting task: {e}{Colors.ENDC}")


def cmd_task_list(args):
    url = get_base_url(args)
    params = {}
    if args.status:
        params["status"] = args.status

    try:
        res = requests.get(f"{url}/v1/tasks", params=params, timeout=5.0)
        tasks = res.json()

        print(f"\n{Colors.BOLD}📋 AgentMesh Tasks List ({len(tasks)} items):{Colors.ENDC}\n")
        header = f"{'TASK ID':<16} {'TENANT':<16} {'AGENT TYPE':<16} {'STATUS':<15} {'PRIORITY':<8}"
        print(Colors.UNDERLINE + header + Colors.ENDC)

        for t in tasks:
            st = t.get("status")
            st_color = Colors.GREEN if st == "COMPLETED" else Colors.WARNING if st in ("QUEUED", "WAITING_HITL") else Colors.FAIL
            print(f"{t.get('task_id'):<16} {t.get('tenant_id'):<16} {t.get('agent_type'):<16} {st_color}{st:<15}{Colors.ENDC} {t.get('priority'):<8}")
        print()
    except Exception as e:
        print(f"{Colors.FAIL}Error listing tasks: {e}{Colors.ENDC}")


def cmd_task_inspect(args):
    url = get_base_url(args)
    try:
        res = requests.get(f"{url}/v1/tasks/{args.task_id}", timeout=5.0)
        if res.status_code == 200:
            task = res.json()
            print(f"\n{Colors.BOLD}🔍 Task Inspection: {task.get('task_id')}{Colors.ENDC}")
            print(f"  • Tenant ID     : {task.get('tenant_id')} (Cost Center: {task.get('cost_center')})")
            print(f"  • Agent Type    : {task.get('agent_type')}")
            print(f"  • Status        : {Colors.BOLD}{task.get('status')}{Colors.ENDC}")
            print(f"  • Priority      : {task.get('priority')} | Retries: {task.get('retries')}/{task.get('max_retries')}")
            print(f"  • Instruction   : {task.get('payload', {}).get('instruction')}")
            if task.get("hitl_trigger_tool"):
                print(f"  • HITL Tool     : {Colors.WARNING}{task.get('hitl_trigger_tool')}{Colors.ENDC}")
            if task.get("result"):
                print(f"  • Output Result : {Colors.GREEN}{json.dumps(task.get('result'))}{Colors.ENDC}")
            if task.get("error_message"):
                print(f"  • Error Msg     : {Colors.FAIL}{task.get('error_message')}{Colors.ENDC}")

            telem = task.get("telemetry", {})
            print(f"  • Telemetry     : Tokens: {telem.get('total_tokens')} | Cost: ${telem.get('total_cost_usd', 0):.4f}\n")
        else:
            print(f"{Colors.FAIL}Task {args.task_id} not found{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Error inspecting task: {e}{Colors.ENDC}")


def cmd_task_stream(args):
    url = get_base_url(args)
    cmd_task_stream_internal(url, args.task_id)


def cmd_task_stream_internal(url, task_id):
    print(f"\n{Colors.CYAN}📡 Connecting live SSE event stream for task '{task_id}'...{Colors.ENDC}\n")
    try:
        res = requests.get(f"{url}/v1/tasks/{task_id}/stream", stream=True, timeout=30.0)
        for line in res.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data:"):
                    raw_json = decoded[5:].strip()
                    try:
                        evt = json.loads(raw_json)
                        st = evt.get("status")
                        st_color = Colors.GREEN if st == "COMPLETED" else Colors.WARNING if st in ("QUEUED", "WAITING_HITL") else Colors.FAIL
                        print(f"[{time.strftime('%H:%M:%S')}] {Colors.BOLD}Task {evt.get('task_id')}{Colors.ENDC} Status ➔ {st_color}{st}{Colors.ENDC} | Cost: ${evt.get('cost_usd', 0):.4f}")
                        if st in ("COMPLETED", "FAILED", "DEAD_LETTER_QUEUE", "CANCELLED"):
                            print(f"\n{Colors.GREEN}✨ Stream closed (terminal state reached).{Colors.ENDC}\n")
                            break
                    except Exception:
                        pass
    except Exception as e:
        print(f"{Colors.FAIL}Stream connection ended: {e}{Colors.ENDC}")


def cmd_hitl_list(args):
    url = get_base_url(args)
    try:
        res = requests.get(f"{url}/v1/tasks?status=WAITING_HITL", timeout=5.0)
        tasks = res.json()
        print(f"\n{Colors.WARNING}🛡️ HITL Approval Gate Queue ({len(tasks)} blocked tasks):{Colors.ENDC}\n")
        for t in tasks:
            print(f"  • Task ID: {Colors.BOLD}{t.get('task_id')}{Colors.ENDC} | Tenant: {t.get('tenant_id')}")
            print(f"    Trigger Tool : {Colors.WARNING}{t.get('hitl_trigger_tool')}{Colors.ENDC}")
            print(f"    Instruction  : {t.get('payload', {}).get('instruction')}\n")
    except Exception as e:
        print(f"{Colors.FAIL}Error fetching HITL queue: {e}{Colors.ENDC}")


def cmd_hitl_decision(args, decision):
    url = get_base_url(args)
    payload = {
        "decision": decision,
        "operator_id": args.operator,
        "reason": args.reason or f"CLI operator decision {decision}"
    }
    try:
        res = requests.post(f"{url}/v1/hitl/{args.task_id}/decision", json=payload, timeout=5.0)
        data = res.json()
        if res.status_code == 200:
            print(f"\n{Colors.GREEN}✅ HITL Decision '{decision}' Recorded for Task {args.task_id}{Colors.ENDC}")
            print(f"  • New State : {Colors.BOLD}{data.get('new_state')}{Colors.ENDC}\n")
        else:
            print(f"{Colors.FAIL}Error recording HITL decision: {data.get('detail')}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Network error: {e}{Colors.ENDC}")


def cmd_mcp_list(args):
    url = get_base_url(args)
    try:
        res = requests.get(f"{url}/v1/mcp/tools", timeout=5.0)
        tools = res.json()
        print(f"\n{Colors.BOLD}🔌 Registered MCP Tools ({len(tools)} items):{Colors.ENDC}\n")
        header = f"{'TOOL NAME':<30} {'REQUIRED ROLE':<20} {'DESCRIPTION'}"
        print(Colors.UNDERLINE + header + Colors.ENDC)
        for t in tools:
            role = t.get("required_rbac_role") or "PUBLIC"
            print(f"{t.get('name'):<30} {Colors.WARNING}{role:<20}{Colors.ENDC} {t.get('description')}")
        print()
    except Exception as e:
        print(f"{Colors.FAIL}Error listing MCP tools: {e}{Colors.ENDC}")


def main():
    parser = argparse.ArgumentParser(description="Zuctro AgentMesh Control Plane CLI")
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help="AgentMesh server URL (default: http://localhost:8000)")

    subparsers = parser.add_subparsers(dest="subcommand")

    # Status / Info
    subparsers.add_parser("status", help="Display AgentMesh control plane health and metrics summary")
    subparsers.add_parser("info", help="Display AgentMesh control plane health and metrics summary")

    # Task Management
    task_parser = subparsers.add_parser("task", help="Task operations")
    task_sub = task_parser.add_subparsers(dest="task_cmd")

    submit_p = task_sub.add_parser("submit", help="Submit a new task instruction to AgentMesh")
    submit_p.add_argument("--instruction", "-i", required=True, help="Task instruction string")
    submit_p.add_argument("--agent-type", "-a", default="general_worker", help="Target agent type (default: general_worker)")
    submit_p.add_argument("--tenant", "-t", default="default_tenant", help="Tenant ID")
    submit_p.add_argument("--cost-center", default="default", help="Cost Center ID")
    submit_p.add_argument("--priority", type=int, default=5, help="Priority (1-10)")
    submit_p.add_argument("--max-tokens", type=int, default=50000, help="Max token budget")
    submit_p.add_argument("--max-cost", type=float, default=0.50, help="Max cost USD cap")
    submit_p.add_argument("--no-pii", action="store_true", help="Disable PII redaction")
    submit_p.add_argument("--hitl-tools", help="Comma-separated list of tools requiring HITL approval")
    submit_p.add_argument("--follow", "-f", action="store_true", help="Stream real-time SSE events after submission")

    list_p = task_sub.add_parser("list", help="List tasks")
    list_p.add_argument("--status", help="Filter by status (QUEUED, RUNNING, WAITING_HITL, COMPLETED, FAILED)")

    inspect_p = task_sub.add_parser("inspect", help="Inspect a specific task")
    inspect_p.add_argument("task_id", help="Task ID")

    stream_p = task_sub.add_parser("stream", help="Stream SSE events for a task")
    stream_p.add_argument("task_id", help="Task ID")

    # HITL Operations
    hitl_parser = subparsers.add_parser("hitl", help="HITL Gate operations")
    hitl_sub = hitl_parser.add_subparsers(dest="hitl_cmd")
    hitl_sub.add_parser("list", help="List tasks waiting for HITL approval")

    app_p = hitl_sub.add_parser("approve", help="Approve a blocked HITL task")
    app_p.add_argument("task_id", help="Task ID")
    app_p.add_argument("--operator", default="cli_operator", help="Operator ID")
    app_p.add_argument("--reason", help="Approval reason")

    rej_p = hitl_sub.add_parser("reject", help="Reject a blocked HITL task")
    rej_p.add_argument("task_id", help="Task ID")
    rej_p.add_argument("--operator", default="cli_operator", help="Operator ID")
    rej_p.add_argument("--reason", help="Rejection reason")

    # MCP Operations
    mcp_parser = subparsers.add_parser("mcp", help="MCP tool operations")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_cmd")
    mcp_sub.add_parser("list", help="List registered MCP tools")

    args = parser.parse_args()

    if not args.subcommand:
        print_banner()
        parser.print_help()
        sys.exit(0)

    if args.subcommand in ("status", "info"):
        print_banner()
        cmd_status(args)
    elif args.subcommand == "task":
        if args.task_cmd == "submit":
            cmd_task_submit(args)
        elif args.task_cmd == "list":
            cmd_task_list(args)
        elif args.task_cmd == "inspect":
            cmd_task_inspect(args)
        elif args.task_cmd == "stream":
            cmd_task_stream(args)
        else:
            task_parser.print_help()
    elif args.subcommand == "hitl":
        if args.hitl_cmd == "list":
            cmd_hitl_list(args)
        elif args.hitl_cmd == "approve":
            cmd_hitl_decision(args, "APPROVED")
        elif args.hitl_cmd == "reject":
            cmd_hitl_decision(args, "REJECTED")
        else:
            hitl_parser.print_help()
    elif args.subcommand == "mcp":
        if args.mcp_cmd == "list":
            cmd_mcp_list(args)
        else:
            mcp_parser.print_help()


if __name__ == "__main__":
    main()
