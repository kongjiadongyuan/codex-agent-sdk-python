"""Tests for Codex subprocess transport command building."""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from codex_agent_sdk._internal.transport.app_server import AppServerTransport
from codex_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
from codex_agent_sdk.types import CodexAgentOptions


def make_options(**overrides):
    base = CodexAgentOptions(cli_path="/usr/bin/codex")
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_build_command_basic_flags():
    options = make_options(
        model="gpt-5-codex",
        oss=True,
        profile="default",
        sandbox="workspace-write",
        ask_for_approval="on-request",
        full_auto=True,
        yolo=True,
        cwd="/tmp",
        search=True,
        skip_git_repo_check=True,
        add_dirs=["/extra"],
        images=["a.png", "b.png"],
        output_schema="schema.json",
        output_last_message="out.txt",
        color="never",
        config_overrides={"web_search": "live", "features.shell_tool": True},
        config_kv=["foo=bar"],
        include_json_events=True,
        extra_args={"extra-flag": None, "other": "value"},
    )

    transport = SubprocessCLITransport(prompt="Hello", options=options)
    cmd = transport._build_command()

    assert cmd[:2] == ["/usr/bin/codex", "exec"]
    assert "--json" in cmd
    assert "--model" in cmd and "gpt-5-codex" in cmd
    assert "--oss" in cmd
    assert "--profile" in cmd and "default" in cmd
    assert "--sandbox" in cmd and "workspace-write" in cmd
    assert 'approval_policy="on-request"' in cmd
    assert "--full-auto" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--cd" in cmd and "/tmp" in cmd
    assert "features.web_search=true" in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--add-dir" in cmd and "/extra" in cmd
    assert "--image" in cmd and "a.png" in cmd and "b.png" in cmd
    assert "--output-schema" in cmd and "schema.json" in cmd
    assert "--output-last-message" in cmd and "out.txt" in cmd
    assert "--color" in cmd and "never" in cmd
    assert "--config" in cmd
    assert "foo=bar" in cmd
    assert "--extra-flag" in cmd
    assert "--other" in cmd and "value" in cmd
    assert cmd[-1] == "Hello"


def test_build_command_resume_session():
    options = make_options(resume_session="abc123")
    transport = SubprocessCLITransport(prompt="Follow up", options=options)
    cmd = transport._build_command()

    assert cmd[:3] == ["/usr/bin/codex", "exec", "resume"]
    assert "abc123" in cmd


@pytest.mark.asyncio
async def test_build_command_streaming_prompt_uses_stdin():
    async def prompt_stream() -> AsyncIterator[str]:
        yield "Hello"

    options = make_options()
    transport = SubprocessCLITransport(prompt=prompt_stream(), options=options)
    cmd = transport._build_command()
    assert cmd[-1] == "-"


def test_build_process_env_inherit_disabled_only_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SHOULD_NOT_LEAK", "x")
    options = make_options(
        inherit_env=False,
        env={"EXPLICIT_VAR": "1"},
    )
    transport = SubprocessCLITransport(prompt="Hello", options=options)

    process_env = transport._build_process_env()
    assert "SHOULD_NOT_LEAK" not in process_env
    assert process_env["EXPLICIT_VAR"] == "1"
    assert process_env["CODEX_SDK_ENTRYPOINT"] == "sdk-py"


def test_build_process_env_allowlist_and_denylist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEEP_ME", "yes")
    monkeypatch.setenv("DROP_ME", "no")
    monkeypatch.setenv("OVERRIDE_ME", "old")

    options = make_options(
        inherit_env=True,
        env_allowlist=["KEEP_ME", "DROP_ME", "OVERRIDE_ME"],
        env_denylist=["DROP_ME", "OVERRIDE_ME"],
        env={"OVERRIDE_ME": "new", "EXPLICIT_VAR": "1"},
    )
    transport = SubprocessCLITransport(prompt="Hello", options=options)

    process_env = transport._build_process_env()
    assert process_env["KEEP_ME"] == "yes"
    assert "DROP_ME" not in process_env
    assert process_env["OVERRIDE_ME"] == "new"
    assert process_env["EXPLICIT_VAR"] == "1"


def test_app_server_transport_process_env_respects_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FILTERED", "no")
    monkeypatch.setenv("ALLOWED", "yes")
    options = make_options(
        inherit_env=False,
        env_allowlist=["ALLOWED"],
        env={"EXPLICIT_VAR": "2"},
    )
    transport = AppServerTransport(options=options)

    process_env = transport._build_process_env()
    assert process_env["ALLOWED"] == "yes"
    assert "FILTERED" not in process_env
    assert process_env["EXPLICIT_VAR"] == "2"
