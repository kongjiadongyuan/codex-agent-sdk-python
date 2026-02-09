"""Subprocess transport implementation using Codex CLI."""

import json
import logging
import os
import shutil
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from pathlib import Path
from subprocess import PIPE
from typing import Any

import anyio
import anyio.abc
from anyio.abc import Process
from anyio.streams.text import TextReceiveStream, TextSendStream

from ..._errors import CLIConnectionError, CLINotFoundError, ProcessError
from ..._errors import CLIJSONDecodeError as SDKJSONDecodeError
from ..._version import __version__
from ...types import CodexAgentOptions
from . import Transport

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer limit


class SubprocessCLITransport(Transport):
    """Subprocess transport using Codex CLI."""

    def __init__(
        self,
        prompt: str | AsyncIterable[str] | AsyncIterable[dict[str, Any]] | None,
        options: CodexAgentOptions,
    ):
        self._prompt = prompt
        self._is_streaming_input = not isinstance(prompt, str) and prompt is not None
        self._options = options
        self._cli_path = (
            str(options.cli_path) if options.cli_path is not None else self._find_cli()
        )
        self._cwd = str(options.cwd) if options.cwd else None
        self._process: Process | None = None
        self._stdout_stream: TextReceiveStream | None = None
        self._stdin_stream: TextSendStream | None = None
        self._stderr_stream: TextReceiveStream | None = None
        self._stderr_task_group: anyio.abc.TaskGroup | None = None
        self._ready = False
        self._exit_error: Exception | None = None
        self._max_buffer_size = (
            options.max_buffer_size
            if options.max_buffer_size is not None
            else _DEFAULT_MAX_BUFFER_SIZE
        )
        self._write_lock: anyio.Lock = anyio.Lock()

    def _find_cli(self) -> str:
        """Find Codex CLI binary."""
        if cli := shutil.which("codex"):
            return cli

        locations = [
            Path.home() / ".local/bin/codex",
            Path("/usr/local/bin/codex"),
            Path.home() / "node_modules/.bin/codex",
        ]

        for path in locations:
            if path.exists() and path.is_file():
                return str(path)

        raise CLINotFoundError(
            "Codex CLI not found. Install Codex and ensure `codex` is on PATH, "
            "or pass CodexAgentOptions(cli_path=\"/path/to/codex\")."
        )

    def _build_command(self) -> list[str]:
        """Build CLI command with arguments."""
        # Base command: codex exec (or codex exec resume)
        cmd = [self._cli_path, "exec"]

        resume_mode = (
            self._options.resume_session is not None
            or self._options.resume_last
            or self._options.resume_all
        )
        if resume_mode:
            cmd.append("resume")
            if self._options.resume_session:
                cmd.append(self._options.resume_session)

        # Global flags (must come after subcommand per docs)
        if self._options.include_json_events:
            cmd.append("--json")

        for image in self._options.images:
            cmd.extend(["--image", str(image)])

        if self._options.model:
            cmd.extend(["--model", self._options.model])

        if self._options.oss:
            cmd.append("--oss")

        if self._options.sandbox:
            cmd.extend(["--sandbox", self._options.sandbox])

        if self._options.ask_for_approval:
            approval_policy = json.dumps(self._options.ask_for_approval)
            cmd.extend(["--config", f"approval_policy={approval_policy}"])

        if self._options.full_auto:
            cmd.append("--full-auto")

        if self._options.yolo:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")

        if self._options.profile:
            cmd.extend(["--profile", self._options.profile])

        if self._options.cwd:
            cmd.extend(["--cd", str(self._options.cwd)])

        if self._options.search:
            cmd.extend(["--config", "features.web_search=true"])

        if self._options.skip_git_repo_check:
            cmd.append("--skip-git-repo-check")

        for directory in self._options.add_dirs:
            cmd.extend(["--add-dir", str(directory)])

        if self._options.output_schema:
            cmd.extend(["--output-schema", str(self._options.output_schema)])

        if self._options.color:
            cmd.extend(["--color", self._options.color])

        if self._options.output_last_message:
            cmd.extend(
                ["--output-last-message", str(self._options.output_last_message)]
            )

        # Config overrides
        for kv in self._options.config_kv:
            cmd.extend(["--config", kv])

        for key, value in self._options.config_overrides.items():
            if isinstance(value, str):
                encoded_value = value
            else:
                encoded_value = json.dumps(value)
            cmd.extend(["--config", f"{key}={encoded_value}"])

        # Extra args passthrough
        for flag, value in self._options.extra_args.items():
            if value is None:
                cmd.append(f"--{flag}")
            else:
                cmd.extend([f"--{flag}", str(value)])

        # Prompt handling
        if self._prompt is not None:
            prompt_value = "-" if self._is_streaming_input else str(self._prompt)
            cmd.append(prompt_value)

        return cmd

    def _build_process_env(self) -> dict[str, str]:
        inherited_env = dict(os.environ) if self._options.inherit_env else {}

        if self._options.env_allowlist:
            allowlist = set(self._options.env_allowlist)
            if self._options.inherit_env:
                inherited_env = {
                    key: value
                    for key, value in inherited_env.items()
                    if key in allowlist
                }
            else:
                inherited_env = {
                    key: value
                    for key, value in os.environ.items()
                    if key in allowlist
                }

        for key in self._options.env_denylist:
            inherited_env.pop(key, None)

        return {
            **inherited_env,
            **self._options.env,
            "CODEX_SDK_ENTRYPOINT": "sdk-py",
            "CODEX_SDK_VERSION": __version__,
        }

    async def connect(self) -> None:
        """Start subprocess."""
        if self._process:
            return

        cmd = self._build_command()
        try:
            process_env = self._build_process_env()

            should_pipe_stderr = self._options.stderr is not None
            stderr_dest = PIPE if should_pipe_stderr else None

            self._process = await anyio.open_process(
                cmd,
                stdin=PIPE,
                stdout=PIPE,
                stderr=stderr_dest,
                cwd=self._cwd,
                env=process_env,
            )

            if self._process.stdout:
                self._stdout_stream = TextReceiveStream(self._process.stdout)

            if should_pipe_stderr and self._process.stderr:
                self._stderr_stream = TextReceiveStream(self._process.stderr)
                self._stderr_task_group = anyio.create_task_group()
                await self._stderr_task_group.__aenter__()
                self._stderr_task_group.start_soon(self._handle_stderr)

            if self._process.stdin:
                if self._is_streaming_input:
                    self._stdin_stream = TextSendStream(self._process.stdin)
                else:
                    await self._process.stdin.aclose()

            self._ready = True

        except FileNotFoundError as e:
            if self._cwd and not Path(self._cwd).exists():
                error = CLIConnectionError(
                    f"Working directory does not exist: {self._cwd}"
                )
                self._exit_error = error
                raise error from e
            error = CLINotFoundError(f"Codex CLI not found at: {self._cli_path}")
            self._exit_error = error
            raise error from e
        except Exception as e:
            error = CLIConnectionError(f"Failed to start Codex CLI: {e}")
            self._exit_error = error
            raise error from e

    async def _handle_stderr(self) -> None:
        """Handle stderr stream - read and invoke callbacks."""
        if not self._stderr_stream:
            return

        try:
            async for line in self._stderr_stream:
                line_str = line.rstrip()
                if not line_str:
                    continue
                if self._options.stderr:
                    self._options.stderr(line_str)
        except anyio.ClosedResourceError:
            pass
        except Exception:
            pass

    async def close(self) -> None:
        """Close the transport and clean up resources."""
        if not self._process:
            self._ready = False
            return

        if self._stderr_task_group:
            with suppress(Exception):
                self._stderr_task_group.cancel_scope.cancel()
                await self._stderr_task_group.__aexit__(None, None, None)
            self._stderr_task_group = None

        async with self._write_lock:
            self._ready = False
            if self._stdin_stream:
                with suppress(Exception):
                    await self._stdin_stream.aclose()
                self._stdin_stream = None

        if self._stderr_stream:
            with suppress(Exception):
                await self._stderr_stream.aclose()
            self._stderr_stream = None

        if self._process.returncode is None:
            with suppress(ProcessLookupError):
                self._process.terminate()
                with suppress(Exception):
                    await self._process.wait()

        self._process = None
        self._stdout_stream = None
        self._stdin_stream = None
        self._stderr_stream = None
        self._exit_error = None

    async def write(self, data: str) -> None:
        """Write raw data to the transport."""
        async with self._write_lock:
            if not self._ready or not self._stdin_stream:
                raise CLIConnectionError("Transport is not ready for writing")

            if self._process and self._process.returncode is not None:
                raise CLIConnectionError(
                    "Cannot write to terminated process "
                    f"(exit code: {self._process.returncode})"
                )

            if self._exit_error:
                raise CLIConnectionError(
                    "Cannot write to process that exited with error: "
                    f"{self._exit_error}"
                ) from self._exit_error

            try:
                await self._stdin_stream.send(data)
            except Exception as e:
                self._ready = False
                self._exit_error = CLIConnectionError(
                    f"Failed to write to process stdin: {e}"
                )
                raise self._exit_error from e

    async def end_input(self) -> None:
        """End the input stream (close stdin)."""
        async with self._write_lock:
            if self._stdin_stream:
                with suppress(Exception):
                    await self._stdin_stream.aclose()
                self._stdin_stream = None

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read and parse messages from the transport."""
        return self._read_messages_impl()

    async def _read_messages_impl(self) -> AsyncIterator[dict[str, Any]]:
        """Internal implementation of read_messages."""
        if not self._process or not self._stdout_stream:
            raise CLIConnectionError("Not connected")

        json_buffer = ""

        try:
            async for line in self._stdout_stream:
                line_str = line.strip()
                if not line_str:
                    continue

                json_lines = line_str.split("\n")
                for json_line in json_lines:
                    json_line = json_line.strip()
                    if not json_line:
                        continue
                    # Skip non-JSON lines (Codex can emit logs on stdout in --json mode)
                    if not json_line.startswith("{") and not json_buffer:
                        continue
                    if not json_line.startswith("{") and json_buffer:
                        # Drop any partial buffer if a log line interleaves.
                        json_buffer = ""
                        continue

                    json_buffer += json_line

                    if len(json_buffer) > self._max_buffer_size:
                        buffer_length = len(json_buffer)
                        json_buffer = ""
                        raise SDKJSONDecodeError(
                            "JSON message exceeded maximum buffer size of "
                            f"{self._max_buffer_size} bytes",
                            ValueError(
                                "Buffer size "
                                f"{buffer_length} exceeds limit "
                                f"{self._max_buffer_size}"
                            ),
                        )

                    try:
                        data = json.loads(json_buffer)
                        json_buffer = ""
                        yield data
                    except json.JSONDecodeError:
                        continue

        except anyio.ClosedResourceError:
            pass
        except GeneratorExit:
            pass

        try:
            returncode = await self._process.wait()
        except Exception:
            returncode = -1

        if returncode is not None and returncode != 0:
            self._exit_error = ProcessError(
                f"Command failed with exit code {returncode}",
                exit_code=returncode,
                stderr="Check stderr output for details",
            )
            raise self._exit_error

    def is_ready(self) -> bool:
        """Check if transport is ready for communication."""
        return self._ready
