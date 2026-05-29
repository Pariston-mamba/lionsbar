import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

MAX_HP = 5
HAND_SIZE = 5
MAX_PLAY_CARDS = 3

TABLE_RANKS = ["A", "K", "Q"]
JOKER = "Joker"
RANKS = TABLE_RANKS + [JOKER]


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
        self.table_rank: str = random.choice(TABLE_RANKS)

    def add_player(self, discord_id: int, display_name: str) -> tuple[bool, str]:
        if self.state != GameState.WAITING:
            return False, "遊戲已經開始，不能加入。"
        if len(self.players) >= 6:
            return False, "房間已滿，最多 6 人。"
        if any(p.discord_id == discord_id for p in self.players):
            return False, "你已經在房間裡了。"

        self.players.append(Player(discord_id=discord_id, display_name=display_name))
        return True, "加入成功。"

    def get_player(self, discord_id: int) -> Optional[Player]:
        return next((p for p in self.players if p.discord_id == discord_id), None)

    def get_current_player(self) -> Player:
        return self.players[self.current_turn]

    def set_current_player(self, discord_id: int):
        for i, player in enumerate(self.players):
            if player.discord_id == discord_id:
                self.current_turn = i
                return

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.is_alive]

    def alive_players_with_cards(self) -> list[Player]:
        return [p for p in self.players if p.is_alive and len(p.hand) > 0]

    def build_deck(self) -> list[str]:
        deck = TABLE_RANKS * 10 + [JOKER, JOKER]
        random.shuffle(deck)
        return deck

    def deal_cards(self):
        self.deck = self.build_deck()
        for player in self.alive_players():
            player.hand = [self.deck.pop() for _ in range(HAND_SIZE)]

    def start_game(self) -> tuple[bool, str]:
        if len(self.players) < 2:
            return False, "至少需要 2 位玩家才能開始。"
        if self.state != GameState.WAITING:
            return False, "遊戲已經開始。"

        self.state = GameState.PLAYING
        random.shuffle(self.players)
        self.current_turn = 0
        self.reset_round()
        return True, "遊戲開始。"

    def play_cards(self, player_id: int, card_indices: list[int]) -> tuple[bool, str]:
        player = self.get_player(player_id)

        if not player:
            return False, "你不是本局玩家。"
        if self.get_current_player().discord_id != player_id:
            return False, "還沒輪到你。"
        if not player.is_alive:
            return False, "你已經被淘汰。"
        if not card_indices:
            return False, "請至少選擇 1 張牌。"
        if len(card_indices) > MAX_PLAY_CARDS:
            return False, f"一次最多只能出 {MAX_PLAY_CARDS} 張牌。"
        if len(set(card_indices)) != len(card_indices):
            return False, "不能重複選同一張牌。"
        if any(i < 0 or i >= len(player.hand) for i in card_indices):
            return False, "手牌索引錯誤。"

        actual_cards = [player.hand[i] for i in sorted(card_indices)]
        for i in sorted(card_indices, reverse=True):
            player.hand.pop(i)

        self.table_cards.extend(actual_cards)
        self.last_claim = Claim(
            player_id=player_id,
            actual_cards=actual_cards,
            claimed_rank=self.table_rank,
            claimed_count=len(actual_cards),
        )
        return True, "出牌成功。"

    def check_lie(self) -> bool:
        if not self.last_claim:
            return False

        return any(
            card != self.table_rank and card != JOKER
            for card in self.last_claim.actual_cards
        )

    def apply_damage(self, discord_id: int) -> tuple[Player, bool]:
        player = self.get_player(discord_id)
        player.hp -= 1
        eliminated = player.hp <= 0

        if eliminated:
            player.is_alive = False
            player.hand = []

        return player, eliminated

    def check_winner(self) -> Optional[Player]:
        alive = self.alive_players()
        if len(alive) == 1:
            self.state = GameState.ENDED
            return alive[0]
        return None

    def advance_turn(self, skip_empty: bool = True):
        total = len(self.players)

        for _ in range(total):
            self.current_turn = (self.current_turn + 1) % total
            player = self.players[self.current_turn]

            if not player.is_alive:
                continue
            if skip_empty and len(player.hand) == 0:
                continue

            return

    def other_players_with_cards(self, exclude_player_id: int) -> list[Player]:
        return [
            p for p in self.alive_players_with_cards()
            if p.discord_id != exclude_player_id
        ]

    def reset_round(self):
        self.last_claim = None
        self.table_cards = []
        self.table_rank = random.choice(TABLE_RANKS)
        self.deal_cards()

    def reset_game(self):
        self.__init__(self.guild_id, self.channel_id)
