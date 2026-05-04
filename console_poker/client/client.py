"""gRPC client wrapper — manages the bidirectional stream."""

from __future__ import annotations

import threading
import queue
import logging
from typing import Callable, Optional

import grpc

import sys, os
_PROTO_DIR = os.path.join(os.path.dirname(__file__), "..", "proto")
if _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)

import poker_pb2 as pb
import poker_pb2_grpc as pb_grpc

logger = logging.getLogger(__name__)


class PokerClient:
    """Wraps the gRPC bidirectional stream.

    Events from the server are dispatched to registered handlers.
    Client actions are queued and sent on the stream.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 50051) -> None:
        self.host = host
        self.port = port
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None

        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[pb_grpc.PokerServiceStub] = None
        self._send_queue: queue.Queue[pb.ClientMessage] = queue.Queue()
        self._handlers: dict[str, list[Callable]] = {}
        self._connected = False
        self._stream_thread: Optional[threading.Thread] = None

    # ── Event subscription ────────────────────────────────────────────────

    def on(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def _dispatch(self, event: str, *args, **kwargs) -> None:
        for fn in self._handlers.get(event, []):
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"Handler error [{event}]: {e}")

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self, name: str, player_id: str = "") -> bool:
        self._channel = grpc.insecure_channel(f"{self.host}:{self.port}")
        self._stub = pb_grpc.PokerServiceStub(self._channel)
        self.player_name = name

        try:
            resp = self._stub.Join(pb.JoinRequest(name=name, player_id=player_id))
        except grpc.RpcError as e:
            logger.error(f"Join failed: {e}")
            return False

        if not resp.success:
            logger.warning(f"Join rejected: {resp.message}")
            self._dispatch("error", resp.message)
            return False

        self.player_id = resp.player_id
        self._connected = True
        self._start_stream()
        return True

    def disconnect(self) -> None:
        self._connected = False
        if self._channel:
            self._channel.close()

    # ── Streaming ─────────────────────────────────────────────────────────

    def _outgoing_generator(self):
        """Yield outgoing ClientMessage objects from the send queue."""
        # First message identifies the player
        yield pb.ClientMessage(player_id=self.player_id, action=pb.PlayerAction.ACTION_NONE)
        while self._connected:
            try:
                msg = self._send_queue.get(timeout=1.0)
                yield msg
            except queue.Empty:
                continue

    def _start_stream(self) -> None:
        def run():
            try:
                for event in self._stub.Play(self._outgoing_generator()):
                    self._handle_server_event(event)
            except grpc.RpcError as e:
                if self._connected:
                    logger.warning(f"Stream error: {e}")
                    self._dispatch("disconnected")
            self._connected = False

        self._stream_thread = threading.Thread(target=run, daemon=True)
        self._stream_thread.start()

    def _handle_server_event(self, event: pb.ServerEvent) -> None:
        which = event.WhichOneof("event")
        if which == "lobby":
            self._dispatch("lobby", event.lobby)
        elif which == "class_select":
            self._dispatch("class_select", event.class_select)
        elif which == "combat":
            self._dispatch("combat", event.combat)
        elif which == "shop":
            self._dispatch("shop", event.shop)
        elif which == "reward":
            self._dispatch("reward", event.reward)
        elif which == "result":
            self._dispatch("result", event.result)
        elif which == "game_over":
            self._dispatch("game_over", event.game_over)
        elif which == "log":
            self._dispatch("log", event.log)
        elif which == "error":
            self._dispatch("error", event.error.message)

    # ── Actions ───────────────────────────────────────────────────────────

    def _send(self, msg: pb.ClientMessage) -> None:
        if self._connected:
            self._send_queue.put(msg)

    def send_ready(self) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_READY,
        ))

    def send_select_class(self, class_id: str) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_SELECT_CLASS,
            class_id=class_id,
        ))

    def send_play(self, card_ids: list[str]) -> None:
        cards = [pb.CardProto(card_id=cid) for cid in card_ids]
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_PLAY_HAND,
            play_hand=pb.HandProto(cards=cards),
        ))

    def send_pass(self) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_PASS,
        ))

    def send_use_skill(self, skill_id: str) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_USE_SKILL,
            skill_id=skill_id,
        ))

    def send_buy(self, item_id: str) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_BUY,
            buy_item_id=item_id,
        ))

    def send_sell(self, item_id: str) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_SELL,
            sell_item_id=item_id,
        ))

    def send_refresh(self) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_REFRESH,
            refresh_shop=True,
        ))

    def send_confirm_result(self) -> None:
        self._send(pb.ClientMessage(
            player_id=self.player_id,
            action=pb.PlayerAction.ACTION_CONFIRM_RESULT,
            confirm="ok",
        ))
