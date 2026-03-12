"""Live-updating visualization server with WebSocket push."""

from __future__ import annotations

import asyncio
import hashlib
import http.server
import json
import logging
import threading

import websockets

from graphmem.core import GraphMem

logger = logging.getLogger(__name__)


class VizServer:
    """HTTP + WebSocket server for live graph visualization."""

    def __init__(
        self,
        html: str,
        port: int,
        gm: GraphMem,
        poll_interval: float = 3.0,
        group_id: str | None = None,
    ):
        self.html = html
        self.http_port = port
        self.ws_port = port + 1
        self.gm = gm
        self.poll_interval = poll_interval
        self.group_id = group_id
        self.clients: set = set()
        self._last_hash: str = ""

    async def _ws_handler(self, websocket):
        """Handle a WebSocket connection."""
        self.clients.add(websocket)
        try:
            data = await self.gm.viz_data(group_id=self.group_id)
            await websocket.send(json.dumps(data))
            async for _ in websocket:
                pass
        finally:
            self.clients.discard(websocket)

    async def _poll_and_broadcast(self):
        """Poll graph DB for changes and broadcast to connected clients."""
        while True:
            await asyncio.sleep(self.poll_interval)
            try:
                data = await self.gm.viz_data(group_id=self.group_id)
                data_json = json.dumps(data, sort_keys=True)
                data_hash = hashlib.md5(data_json.encode()).hexdigest()
                if data_hash != self._last_hash:
                    self._last_hash = data_hash
                    if self.clients:
                        websockets.broadcast(self.clients, data_json)
            except Exception:
                logger.debug("Poll failed", exc_info=True)

    def _start_http_server(self):
        """Start HTTP server in a daemon thread."""
        html_bytes = self.html.encode("utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self_inner):
                self_inner.send_response(200)
                self_inner.send_header("Content-Type", "text/html; charset=utf-8")
                self_inner.send_header("Content-Length", str(len(html_bytes)))
                self_inner.end_headers()
                self_inner.wfile.write(html_bytes)

            def log_message(self_inner, format, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", self.http_port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    async def run(self):
        """Start HTTP server, WS server, and poller. Block until cancelled."""
        http_server = self._start_http_server()

        async with websockets.serve(
            self._ws_handler, "127.0.0.1", self.ws_port
        ):
            poller = asyncio.create_task(self._poll_and_broadcast())
            try:
                await asyncio.Future()  # block forever
            finally:
                poller.cancel()
                http_server.shutdown()
