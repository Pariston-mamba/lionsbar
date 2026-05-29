import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

MAX_HP = 5
HAND_SIZE = 5
RANKS = ["A", "K", "Q", "J"]


class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    ENDED = "ended"


@dataclass
class Claim:
    player_id: int
    actual_cards: list[str]
    claimed_rank: str
    claimed_count: int


@dataclass
class Player:
    discord_id: int
    display_name: str
    hp: int = MAX_HP
    hand: list[str] = field(default_factory=list)
    is_alive: bool = True


class GameSession:
    def __init__(self, guild_id: int, channel_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.players: list[Player] = []
        self.state: GameState = GameState.WAITING
        self.current_turn: int = 0
        self.last_claim: Optional[Claim] = None
        self.table_cards: list[str] = []
        self.deck: list[str] = []

    # ── 玩家管理 ──────────────────────────────

    def add_player(self, discord_id: int, display_name: str) -> tuple[bool, str]:
        if self.state != GameState.WAITING:
            return False, "遊戲已經開始，無法加入"
        if len(self.players) >= 6:
            return False, "房間已滿（最多 6 人）"
        if any(p.discord_id == discord_id for p in self.players):
            return False, "你已經在房間裡了"
        self.players.append(Player(discord_id=discord_id, display_name=display_name))
        return True, "加入成功"

    def get_player(self, discord_id: int) -> Optional[Player]:
        return next((p for p in self.players if p.discord_id == discord_id), None)

    def get_current_player(self) -> Player:
        return self.players[self.current_turn]

    def get_next_alive_player_after(self, discord_id: int) -> Optional[Player]:
        idx = next(i for i, p in enumerate(self.players) if p.discord_id == discord_id)
        for offset in range(1, len(self.players) + 1):
            candidate = self.players[(idx + offset) % len(self.players)]
            if candidate.is_alive:
                return candidate
        return None

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    # ── 牌組管理 ──────────────────────────────

    def build_deck(self) -> list[str]:
        deck = RANKS * 8
        random.shuffle(deck)
        return deck

    def deal_cards(self):
        self.deck = self.build_deck()
        for p in self.alive_players():
            p.hand = [self.deck.pop() for _ in range(HAND_SIZE)]

    # ── 遊戲流程 ──────────────────────────────

    def start_game(self) -> tuple[bool, str]:
        if len(self.players) < 2:
            return False, "至少需要 2 人才能開始"
        if self.state != GameState.WAITING:
            return False, "遊戲已經在進行中"
        self.state = GameState.PLAYING
        random.shuffle(self.players)
        self.current_turn = 0
        self.deal_cards()
        return True, "遊戲開始"

    def play_cards(self, player_id: int, card_indices: list[int], claimed_rank: str) -> tuple[bool, str]:
        player = self.get_player(player_id)
        if not player:
            return False, "你不在這場遊戲中"
        if self.get_current_player().discord_id != player_id:
            return False, "還沒輪到你"
        if not card_indices:
            return False, "請選擇至少一張牌"
        if any(i >= len(player.hand) for i in card_indices):
            return False, "無效的牌索引"
        if claimed_rank not in RANKS:
            return False, f"聲稱的牌面必須是 {', '.join(RANKS)} 之一"

        actual_cards = [player.hand[i] for i in sorted(card_indices, reverse=True)]
        for i in sorted(card_indices, reverse=True):
            player.hand.pop(i)

        self.table_cards.extend(actual_cards)
        self.last_claim = Claim(
            player_id=player_id,
            actual_cards=actual_cards,
            claimed_rank=claimed_rank,
            claimed_count=len(actual_cards),
        )
        return True, "出牌成功"

    def check_lie(self) -> bool:
        if not self.last_claim:
            return False
        return (
            any(c != self.last_claim.claimed_rank for c in self.last_claim.actual_cards)
            or len(self.last_claim.actual_cards) != self.last_claim.claimed_count
        )

    def apply_damage(self, discord_id: int) -> tuple[Player, bool]:
        player = self.get_player(discord_id)
        player.hp -= 1
        eliminated = player.hp <= 0
        if eliminated:
            player.is_alive = False
        return player, eliminated

    def check_winner(self) -> Optional[Player]:
        alive = self.alive_players()
        if len(alive) == 1:
            self.state = GameState.ENDED
            return alive[0]
        return None

    def advance_turn(self):
        total = len(self.players)
        for _ in range(total):
            self.current_turn = (self.current_turn + 1) % total
            if self.players[self.current_turn].is_alive:
                return

    def reset_round(self):
        self.last_claim = None
        self.table_cards = []
        self.deal_cards()

    def reset_game(self):
        self.__init__(self.guild_id, self.channel_id)
