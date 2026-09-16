"""
Authenticated Streamable HTTP MCP transport, bridged into Flask.

Uses the official MCP SDK ``StreamableHTTPSessionManager`` (JSON responses)
and mounts it under Flask at ``/api/mcp`` so local Flask (:5001) works for
Grok Bot / Cursor without Cloudflare. A tunnel is optional and not required
for tests.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, Request, Response, current_app
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import Scope

from app.mcp.auth import MCPAuthContext, bind_request_auth, reset_request_auth
from app.mcp.server import create_mcp_server

logger = logging.getLogger(__name__)

# Extension key on the Flask app
MCP_HTTP_EXTENSION = "gymbro_mcp_http"

# Default: JSON Streamable HTTP (easier for phone clients / tunnels).
# Set GYMBRO_MCP_STATELESS=true for multi-worker / no session stickiness.
_DEFAULT_JSON_RESPONSE = True


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _transport_security() -> TransportSecuritySettings:
    """
    DNS-rebinding protection is off by default so localhost and optional
    tunnels work. Auth is enforced separately on every request.

    Set GYMBRO_MCP_DNS_REBINDING_PROTECTION=true and GYMBRO_MCP_ALLOWED_HOSTS
    (comma-separated) to lock Host headers down.
    """
    if not _env_flag("GYMBRO_MCP_DNS_REBINDING_PROTECTION", default=False):
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    hosts_raw = os.getenv("GYMBRO_MCP_ALLOWED_HOSTS", "")
    origins_raw = os.getenv("GYMBRO_MCP_ALLOWED_ORIGINS", "")
    hosts = [h.strip() for h in hosts_raw.split(",") if h.strip()]
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


class MCPHttpRuntime:
    """Owns the StreamableHTTP session manager on a dedicated asyncio loop."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._manager: Optional[StreamableHTTPSessionManager] = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._start_error: Optional[BaseException] = None

    @property
    def manager(self) -> StreamableHTTPSessionManager:
        if self._manager is None:
            raise RuntimeError("MCP HTTP runtime is not started.")
        return self._manager

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="gymbro-mcp-http",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=15):
            raise RuntimeError("Timed out starting MCP HTTP runtime.")
        if self._start_error is not None:
            raise RuntimeError(
                f"MCP HTTP runtime failed to start: {self._start_error}"
            ) from self._start_error

    def stop(self) -> None:
        self._stop.set()
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(lambda: None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._loop = None
        self._manager = None
        self._ready.clear()

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._async_main())
        except BaseException as exc:  # pragma: no cover - startup failures
            self._start_error = exc
            logger.exception("MCP HTTP runtime crashed")
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # pragma: no cover
                pass
            loop.close()
            self._ready.set()

    async def _async_main(self) -> None:
        server = create_mcp_server()
        stateless = _env_flag("GYMBRO_MCP_STATELESS", default=False)
        self._manager = StreamableHTTPSessionManager(
            app=server,
            json_response=_DEFAULT_JSON_RESPONSE,
            stateless=stateless,
            security_settings=_transport_security(),
        )
        logger.info(
            "MCP Streamable HTTP manager ready (stateless=%s, json_response=%s)",
            stateless,
            _DEFAULT_JSON_RESPONSE,
        )
        async with self._manager.run():
            self._ready.set()
            while not self._stop.is_set():
                await asyncio.sleep(0.2)

    def dispatch(
        self,
        flask_request: Request,
        auth: MCPAuthContext,
        *,
        timeout: float = 60.0,
    ) -> Response:
        """Bridge a Flask request into the StreamableHTTP ASGI app."""
        if self._loop is None or self._manager is None:
            raise RuntimeError("MCP HTTP runtime is not started.")

        body = flask_request.get_data(cache=False, as_text=False) or b""
        scope = _flask_request_to_asgi_scope(flask_request, body)

        status_box: List[int] = [500]
        header_box: List[List[Tuple[bytes, bytes]]] = [[]]
        chunk_q: queue.Queue[Optional[bytes]] = queue.Queue()
        headers_ready = threading.Event()
        error_box: List[BaseException] = []

        async def _run() -> None:
            token = bind_request_auth(auth)
            try:
                body_sent = False

                async def receive() -> Dict[str, Any]:
                    nonlocal body_sent
                    if not body_sent:
                        body_sent = True
                        return {
                            "type": "http.request",
                            "body": body,
                            "more_body": False,
                        }
                    # Block until cancelled / connection end
                    await asyncio.sleep(3600)
                    return {"type": "http.disconnect"}

                async def send(message: Dict[str, Any]) -> None:
                    msg_type = message.get("type")
                    if msg_type == "http.response.start":
                        status_box[0] = int(message["status"])
                        header_box[0] = list(message.get("headers") or [])
                        headers_ready.set()
                    elif msg_type == "http.response.body":
                        chunk = message.get("body") or b""
                        if chunk:
                            chunk_q.put(bytes(chunk))
                        if not message.get("more_body", False):
                            chunk_q.put(None)

                await self.manager.handle_request(scope, receive, send)
            except BaseException as exc:
                error_box.append(exc)
                logger.exception("MCP HTTP dispatch failed")
                if not headers_ready.is_set():
                    status_box[0] = 500
                    header_box[0] = [
                        (b"content-type", b"application/json"),
                    ]
                    chunk_q.put(
                        b'{"error":"mcp_http_dispatch_failed"}'
                    )
                    chunk_q.put(None)
                    headers_ready.set()
                else:
                    chunk_q.put(None)
                raise
            finally:
                reset_request_auth(token)
                if not headers_ready.is_set():
                    headers_ready.set()
                # Ensure consumer unblocks even if send never finished
                chunk_q.put(None)

        future = asyncio.run_coroutine_threadsafe(_run(), self._loop)
        if not headers_ready.wait(timeout=timeout):
            future.cancel()
            return Response(
                '{"error":"mcp_http_timeout"}',
                status=504,
                content_type="application/json",
            )

        def generate() -> Iterable[bytes]:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    item = chunk_q.get(timeout=min(remaining, 1.0))
                except queue.Empty:
                    if future.done():
                        break
                    continue
                if item is None:
                    break
                yield item
            try:
                future.result(timeout=1.0)
            except Exception:  # pragma: no cover - already logged
                pass
            if error_box and status_box[0] == 500:
                return

        flask_headers = _asgi_headers_to_wsgi(header_box[0])
        return Response(
            generate(),
            status=status_box[0],
            headers=flask_headers,
            direct_passthrough=False,
        )


def _flask_request_to_asgi_scope(flask_request: Request, body: bytes) -> Scope:
    """Build a minimal ASGI HTTP scope for the session manager (path=/)."""
    headers: List[Tuple[bytes, bytes]] = []
    for key, value in flask_request.headers:
        k = key.encode("latin-1").lower()
        # Avoid duplicate host/content-length surprises; Starlette rebuilds as needed.
        if k in {b"content-length"}:
            continue
        headers.append((k, value.encode("latin-1")))
    headers.append((b"content-length", str(len(body)).encode("ascii")))

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": flask_request.method,
        "scheme": flask_request.scheme,
        # Manager is mounted at blueprint root; strip the /api/mcp prefix.
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "query_string": flask_request.query_string or b"",
        "headers": headers,
        "client": (
            (flask_request.remote_addr, 0) if flask_request.remote_addr else None
        ),
        "server": (
            flask_request.host.split(":")[0],
            flask_request.environ.get("SERVER_PORT"),
        ),
    }


def _asgi_headers_to_wsgi(
    headers: List[Tuple[bytes, bytes]],
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    hop_by_hop = {
        b"transfer-encoding",
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"te",
        b"trailers",
        b"upgrade",
        b"content-length",
    }
    for key, value in headers:
        if key.lower() in hop_by_hop:
            continue
        out[key.decode("latin-1")] = value.decode("latin-1")
    return out


def init_mcp_http(app: Flask) -> MCPHttpRuntime:
    """Start (or reuse) the MCP HTTP runtime and attach it to the Flask app."""
    existing = app.extensions.get(MCP_HTTP_EXTENSION)
    if isinstance(existing, MCPHttpRuntime):
        existing.start()
        return existing

    runtime = MCPHttpRuntime()
    runtime.start()
    app.extensions[MCP_HTTP_EXTENSION] = runtime

    @app.teardown_appcontext
    def _noop_teardown(_exc: Optional[BaseException] = None) -> None:
        # Keep the runtime alive for the process; tests call stop explicitly.
        return None

    return runtime


def get_mcp_http_runtime(app: Optional[Flask] = None) -> MCPHttpRuntime:
    flask_app = app or current_app
    runtime = flask_app.extensions.get(MCP_HTTP_EXTENSION)
    if not isinstance(runtime, MCPHttpRuntime):
        raise RuntimeError("MCP HTTP runtime is not initialized on this app.")
    return runtime
