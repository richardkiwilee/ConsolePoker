"""gRPC service implementation."""

from __future__ import annotations

import threading
import queue
import uuid
import logging
from typing import Iterator

import grpc

# Add parent to path for proto imports
import sys, os
_PROTO_DIR = os.path.join(os.path.dirname(__file__), "..", "proto")
if _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)

import poker_pb2 as pb
import poker_pb2_grpc as pb_grpc

from .entities.player import Player, Room
from .entities.game import GameSession, GameStatus
from .core.phase import PhaseEngine
from .core.combat import CombatState
from .core.hand import recognize, Hand
from .core.card import Card
from .registry.class_registry import CLASS_REGISTRY
from .ai.agent import AIAgent

logger = logging.getLogger(__name__)


def _player_to_proto(player: Player) -> pb.PlayerStateProto:
    skills = []
    for s in player.all_skills:
        skills.append(pb.SkillProto(
            skill_id=s.skill_id, name=s.name, description=s.description,
            mana_cost=s.mana_cost, level=s.level, is_class_skill=s.is_class_skill,
        ))
    chips = []
    for c in player.chips:
        chips.append(pb.ChipProto(
            chip_id=c.chip_id, name=c.name, description=c.description,
            rarity=c.rarity, buy_price=c.buy_price,
        ))
    return pb.PlayerStateProto(
        player_id=player.player_id,
        name=player.name,
        score=player.score,
        coins=player.coins,
        mana=player.mana,
        mana_max=player.mana_max,
        hand_count=len(player.hand),
        class_id=player.class_id or "",
        skills=skills,
        chips=chips,
        is_ready=player.is_ready,
        is_ai=player.is_ai,
        is_connected=player.is_connected,
    )


def _card_to_proto(card: Card) -> pb.CardProto:
    return pb.CardProto(
        rank=pb.Rank.Value(card.rank.name) if card.rank.name in pb.Rank.keys() else pb.Rank.RANK_NONE,
        suit=pb.Suit.Value(card.suit.name) if card.suit.name in pb.Suit.keys() else pb.Suit.SUIT_NONE,
        card_id=card.card_id,
        enchantments=[e.enchant_id for e in card.enchantments],
    )


def _proto_to_card_ids(card_protos) -> list[str]:
    return [cp.card_id for cp in card_protos]


class PokerServiceServicer(pb_grpc.PokerServiceServicer):
    """Server-side gRPC service."""

    def __init__(self, room: Room, session: GameSession) -> None:
        self._room = room
        self._session = session
        # player_id → event queue
        self._queues: dict[str, queue.Queue] = {}
        self._ai_agents: dict[str, AIAgent] = {}
        self._lock = threading.RLock()  # RLock allows re-entry from same thread

        # Wire up game session events
        session.on("combat_started", self._on_combat_started)
        session.on("combat_round_over", self._on_combat_round_over)
        session.on("shop_started", self._on_shop_started)
        session.on("reward_started", self._on_reward_started)
        session.on("game_over", self._on_game_over)
        session.on("class_select_started", self._on_class_select_started)
        session.on("class_confirmed", self._on_class_confirmed)

    # ── gRPC handlers ─────────────────────────────────────────────────────

    def Join(self, request: pb.JoinRequest, context) -> pb.JoinResponse:
        with self._lock:
            # Reconnect
            if request.player_id:
                player = self._room.get_player(request.player_id)
                if player and player.name == request.name:
                    player.is_connected = True
                    if player.is_ai:
                        self._ai_agents.pop(request.player_id, None)
                    self._queues[request.player_id] = queue.Queue()
                    self._broadcast_lobby()
                    return pb.JoinResponse(success=True, player_id=request.player_id,
                                          message="重连成功")
                return pb.JoinResponse(success=False, message="重连失败：昵称不匹配")

            # New join
            if len(self._room.players) >= self._room.max_players:
                return pb.JoinResponse(success=False, message="房间已满")
            player_id = str(uuid.uuid4())
            player = Player(player_id=player_id, name=request.name)
            self._room.add_player(player)
            self._queues[player_id] = queue.Queue()
            self._broadcast_lobby()
            return pb.JoinResponse(success=True, player_id=player_id, message="加入成功")

    def Play(
        self,
        request_iterator: Iterator[pb.ClientMessage],
        context,
    ) -> Iterator[pb.ServerEvent]:
        """Bidirectional streaming — one stream per player."""
        player_id: str | None = None
        logger.info("Play stream opened")

        def send_initial_state():
            # Send current lobby/game state to the newly connected player
            evt = pb.ServerEvent(lobby=pb.LobbyEvent(
                players=[_player_to_proto(p) for p in self._room.player_list],
                room_config="",
            ))
            if player_id and player_id in self._queues:
                logger.debug("Sending initial state player_id=%s", player_id)
                self._queues[player_id].put(evt)

        # Start a thread to handle incoming messages
        def handle_incoming():
            nonlocal player_id
            try:
                for msg in request_iterator:
                    logger.debug("Received client msg action=%s player_id=%s", msg.action, msg.player_id)
                    if not player_id:
                        # First message must identify the player
                        player_id = msg.player_id
                        logger.info("Play stream identified player_id=%s", player_id)
                        send_initial_state()
                    self._handle_client_message(msg)
            except Exception as e:
                logger.exception("Client stream error for player_id=%s", player_id)
            finally:
                logger.info("Play incoming loop closing player_id=%s", player_id)
                if player_id:
                    player = self._room.get_player(player_id)
                    if player:
                        player.is_connected = False
                        # Hand off to AI
                        self._ai_agents[player_id] = AIAgent(player_id)
                    self._broadcast_lobby()

        t = threading.Thread(target=handle_incoming, daemon=True)
        t.start()

        # Yield events from the player's queue
        while context.is_active():
            if player_id is None:
                import time; time.sleep(0.05)
                continue
            q = self._queues.get(player_id)
            if q is None:
                logger.warning("Event queue missing for player_id=%s", player_id)
                break
            try:
                evt = q.get(timeout=1.0)
                logger.debug("Yielding server event=%s player_id=%s", evt.WhichOneof("event"), player_id)
                yield evt
            except queue.Empty:
                continue
        logger.info("Play stream closed player_id=%s active=%s", player_id, context.is_active())

    # ── Message routing ───────────────────────────────────────────────────

    def _handle_client_message(self, msg: pb.ClientMessage) -> None:
        action = msg.action
        pid = msg.player_id
        player = self._room.get_player(pid)
        if player is None:
            return

        if action == pb.PlayerAction.ACTION_READY:
            player.is_ready = True
            self._session.player_ready(pid)
            self._broadcast_lobby()

        elif action == pb.PlayerAction.ACTION_SELECT_CLASS:
            class_id = msg.class_id
            if class_id in CLASS_REGISTRY:
                self._session.player_select_class(pid, class_id)

        elif action == pb.PlayerAction.ACTION_PLAY_HAND:
            cs = self._session.current_combat
            if cs is None:
                return
            card_ids = _proto_to_card_ids(msg.play_hand.cards)
            hand_cards = [c for c in player.hand if c.card_id in card_ids]
            result = cs.play(pid, hand_cards)
            if result.valid:
                player.hand = cs.hands.get(pid, [])
                self._broadcast_combat(cs)
                if result.round_over and result.winner_id:
                    self._session.resolve_combat_round(result.winner_id)
            else:
                self._send_error(pid, result.message)

        elif action == pb.PlayerAction.ACTION_PASS:
            cs = self._session.current_combat
            if cs is None:
                return
            result = cs.do_pass(pid)
            if result.valid:
                self._broadcast_combat(cs)
                if result.round_over and result.winner_id:
                    self._session.resolve_combat_round(result.winner_id)
            else:
                self._send_error(pid, result.message)

        elif action == pb.PlayerAction.ACTION_USE_SKILL:
            skill_id = msg.skill_id
            skill = player.find_skill(skill_id)
            if skill and player.spend_mana(skill.mana_cost):
                if callable(skill.on_use):
                    skill.on_use(player, self._session)
                self._broadcast_log(f"{player.name} 使用了技能 [{skill.name}]", important=True)

        elif action == pb.PlayerAction.ACTION_BUY:
            self._handle_buy(pid, msg.buy_item_id)

        elif action == pb.PlayerAction.ACTION_SELL:
            self._handle_sell(pid, msg.sell_item_id)

        elif action == pb.PlayerAction.ACTION_REFRESH:
            self._handle_refresh(pid)

        elif action == pb.PlayerAction.ACTION_CONFIRM_RESULT:
            # Track confirmations; when all confirmed, advance phase
            player._result_confirmed = True
            if all(getattr(p, "_result_confirmed", False) for p in self._room.player_list):
                for p in self._room.player_list:
                    p._result_confirmed = False
                self._session.advance_phase()

    # ── Shop ─────────────────────────────────────────────────────────────

    def _handle_buy(self, player_id: str, item_id: str) -> None:
        from .registry.shop import PlayerShop
        # Each player has a shop; stored on player for simplicity
        player = self._room.get_player(player_id)
        if player is None:
            return
        shop = getattr(player, "_shop", None)
        if shop is None:
            return
        item = shop.get_item(item_id)
        if item is None:
            self._send_error(player_id, "商品不存在")
            return
        if not player.spend_coins(item.price):
            self._send_error(player_id, "金币不足")
            return
        shop.buy(item_id)

        if item.item_type == "chip" and item._def:
            chip = item._def.instantiate()
            if not player.add_chip(chip):
                player.add_coins(item.price)  # refund
                self._send_error(player_id, "筹码槽已满")
                return

        elif item.item_type == "skill" and item._def:
            skill = item._def.instantiate()
            outcome = player.upgrade_or_equip_skill(skill)
            if outcome == "no_slot":
                player.add_coins(item.price)  # refund
                self._send_error(player_id, "技能槽已满")
                return

        self._send_shop_state(player_id)

    def _handle_sell(self, player_id: str, item_id: str) -> None:
        player = self._room.get_player(player_id)
        if player is None:
            return
        # Try selling a chip
        chip = player.remove_chip(item_id)
        if chip:
            player.add_coins(chip.sell_price())
            self._send_shop_state(player_id)
            return
        self._send_error(player_id, "未找到可出售的物品")

    def _handle_refresh(self, player_id: str) -> None:
        from .registry.shop import PlayerShop
        player = self._room.get_player(player_id)
        if player is None:
            return
        shop = getattr(player, "_shop", None)
        if shop is None:
            return
        ok, cost = shop.refresh(player.coins)
        if ok:
            player.spend_coins(cost)
            self._send_shop_state(player_id)
        else:
            self._send_error(player_id, f"金币不足以刷新（需要 {shop.refresh_cost} 金币）")

    # ── Broadcast helpers ─────────────────────────────────────────────────

    def _broadcast_lobby(self) -> None:
        evt = pb.ServerEvent(lobby=pb.LobbyEvent(
            players=[_player_to_proto(p) for p in self._room.player_list],
        ))
        self._broadcast(evt)

    def _broadcast_combat(self, cs: CombatState) -> None:
        players_proto = [_player_to_proto(p) for p in self._room.player_list]
        last_hand = None
        if cs.last_hand:
            last_hand = pb.HandProto(
                type=pb.HandType.Value(f"HAND_{cs.last_hand.type.name}"),
                cards=[_card_to_proto(c) for c in cs.last_hand.cards],
                key_rank=pb.Rank.Value(cs.last_hand.key_rank.name)
                    if cs.last_hand.key_rank.name in pb.Rank.keys() else pb.Rank.RANK_NONE,
            )
        state = pb.CombatStateProto(
            players=players_proto,
            current_player_id=cs.current_player_id,
            last_hand=last_hand,
            last_hand_player_id=cs.last_hand_player or "",
            fatigue_counter=cs.fatigue,
            round_number=cs.round_number,
        )
        evt = pb.ServerEvent(combat=pb.CombatEvent(state=state, event_type="turn_update"))
        self._broadcast(evt)

    def _send_shop_state(self, player_id: str) -> None:
        player = self._room.get_player(player_id)
        if player is None:
            return
        shop = getattr(player, "_shop", None)
        if shop is None:
            return
        items = [pb.ShopItem(
            item_id=i.item_id, item_type=i.item_type, name=i.name,
            description=i.description, price=i.price, rarity=i.rarity,
            reserved=i.reserved,
        ) for i in shop.items]
        state = pb.ShopStateProto(
            items=items,
            refresh_cost=shop.refresh_cost,
            player_coins=player.coins,
        )
        evt = pb.ServerEvent(shop=pb.ShopEvent(state=state))
        self._send_to(player_id, evt)

    def _broadcast_log(self, message: str, important: bool = False) -> None:
        evt = pb.ServerEvent(log=pb.LogEvent(message=message, important=important))
        self._broadcast(evt)

    def _send_error(self, player_id: str, message: str) -> None:
        evt = pb.ServerEvent(error=pb.ErrorEvent(message=message))
        self._send_to(player_id, evt)

    def _broadcast(self, evt: pb.ServerEvent) -> None:
        with self._lock:
            for q in self._queues.values():
                q.put(evt)

    def _send_to(self, player_id: str, evt: pb.ServerEvent) -> None:
        q = self._queues.get(player_id)
        if q:
            q.put(evt)

    # ── Game event handlers ───────────────────────────────────────────────

    def _on_combat_started(self, cs: CombatState) -> None:
        self._broadcast_combat(cs)
        self._broadcast_log("对战开始！", important=True)

    def _on_combat_round_over(self, winner_id, results, coin_deltas) -> None:
        winner = self._room.get_player(winner_id)
        name = winner.name if winner else winner_id
        self._broadcast_log(f"本轮结束！{name} 获胜。", important=True)
        # Build result proto
        player_ids = [r.player_id for r in results]
        result = pb.RoundResult(
            winner_id=winner_id,
            player_ids=player_ids,
            remaining_cards=[0] * len(results),
            score_delta=[r.score_delta for r in results],
            coin_delta=[coin_deltas.get(r.player_id, 0) for r in results],
            total_scores=[self._room.get_player(r.player_id).score for r in results
                          if self._room.get_player(r.player_id)],
        )
        self._broadcast(pb.ServerEvent(result=pb.ResultEvent(result=result)))

    def _on_shop_started(self, config: dict) -> None:
        from .registry.shop import PlayerShop
        for player in self._room.player_list:
            shop = PlayerShop(player.player_id, class_id=player.class_id or "")
            shop.reset_refresh_cost()
            player._shop = shop
            self._send_shop_state(player.player_id)
        self._broadcast_log("进入商店。")

    def _on_reward_started(self, config: dict) -> None:
        self._broadcast_log("进入奖励阶段。")
        # Generate rewards for each player
        for player in self._room.player_list:
            from .registry.shop import PlayerShop
            shop = PlayerShop(player.player_id, class_id=player.class_id or "")
            items = [pb.RewardItem(
                item_id=i.item_id, item_type=i.item_type,
                name=i.name, description=i.description,
            ) for i in shop.items[:3]]
            picks = config.get("picks", 1)
            evt = pb.ServerEvent(reward=pb.RewardEvent(
                state=pb.RewardStateProto(items=items, picks_allowed=picks)
            ))
            self._send_to(player.player_id, evt)

    def _on_class_select_started(self) -> None:
        available = list(CLASS_REGISTRY.keys())
        evt = pb.ServerEvent(class_select=pb.ClassSelectEvent(
            available_classes=available,
            all_confirmed=False,
        ))
        self._broadcast(evt)
        # AI players auto-select
        for player in self._room.player_list:
            if player.is_ai:
                agent = self._ai_agents.get(player.player_id, AIAgent(player.player_id))
                chosen = agent.choose_class(available)
                self._session.player_select_class(player.player_id, chosen)

    def _on_class_confirmed(self, player_id: str) -> None:
        confirmed = [p.player_id for p in self._room.player_list if p.class_confirmed]
        evt = pb.ServerEvent(class_select=pb.ClassSelectEvent(
            available_classes=list(CLASS_REGISTRY.keys()),
            all_confirmed=self._room.all_class_confirmed(),
            confirmed_ids=confirmed,
        ))
        self._broadcast(evt)

    def _on_game_over(self, players_sorted: list) -> None:
        result = pb.GameResult(
            player_ids=[p.player_id for p in players_sorted],
            total_scores=[p.score for p in players_sorted],
            player_names=[p.name for p in players_sorted],
        )
        self._broadcast(pb.ServerEvent(game_over=pb.GameOverEvent(result=result)))


def serve(host: str = "0.0.0.0", port: int = 50051, template: dict | None = None,
          max_players: int = 8) -> None:
    """Start the gRPC server."""
    import json, pathlib
    if template is None:
        default_tmpl = pathlib.Path(__file__).parent.parent / "data" / "classic.json"
        if default_tmpl.exists():
            template = json.loads(default_tmpl.read_text(encoding="utf-8"))
        else:
            template = {"name": "classic", "nodes": [
                {"type": "combat"}, {"type": "shop"}, {"type": "combat"},
                {"type": "reward", "picks": 1}, {"type": "combat"},
            ]}

    room = Room(max_players=max_players)
    engine = PhaseEngine.from_template(template)
    session = GameSession(room, engine)

    server = grpc.server(
        __import__("concurrent.futures", fromlist=["ThreadPoolExecutor"]).ThreadPoolExecutor(max_workers=20)
    )
    servicer = PokerServiceServicer(room, session)
    pb_grpc.add_PokerServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    logger.info(f"Server started on {host}:{port}")
    print(f"[Server] 监听 {host}:{port}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
