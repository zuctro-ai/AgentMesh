import pytest
from cli import cmd_status, cmd_task_submit
from unittest.mock import MagicMock


class DummyArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_cli_args_parsing():
    args = DummyArgs(
        url="http://localhost:8000",
        tenant="test_tenant",
        cost_center="default",
        agent_type="general_worker",
        priority=5,
        max_tokens=1000,
        max_cost=0.1,
        no_pii=False,
        hitl_tools=None,
        instruction="CLI test task",
        follow=False
    )
    assert args.url == "http://localhost:8000"
    assert args.instruction == "CLI test task"
