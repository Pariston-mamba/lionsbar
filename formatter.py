from game import Player, GameSession, MAX_HP, JOKER

R = "\u001b[31m"
G = "\u001b[32m"
Y = "\u001b[33m"
B = "\u001b[34m"
M = "\u001b[35m"
C = "\u001b[36m"
W = "\u001b[37m"
GRAY = "\u001b[30m"
BOLD = "\u001b[1m"
RESET = "\u001b[0m"


def ansi(text: str) -> str:
    return f"```ansi\n{text}\n```"


def fmt_hp_board(session: GameSession) -> str:
    lines = [f"{BOLD}{W}── 血量狀態 ──{RESET}"]

    for player in session.players:
        is_current = (
            session.state.value == "playing"
            and session.players[session.current_turn].discord_id == player.discord_id
            and player.is_alive
        )

        if not player.is_alive:
            lines.append(f"{GRAY}  {player.display_name:<14} ✕ 淘汰{RESET}")
            continue

        if player.hp >= 4:
            hp_color = G
        elif player.hp >= 2:
            hp_color = Y
        else:
            hp_color = R

        hearts = f"{hp_color}{'♥ ' * player.hp}{RESET}{GRAY}{'♡ ' * (MAX_HP - player.hp)}{RESET}"
        arrow = f"{Y}▶ {RESET}" if is_current else "  "
        hand_count = f"{GRAY}({len(player.hand)} 張){RESET}"

        lines.append(f"{arrow}{BOLD}{player.display_name:<14}{RESET} {hearts} {hand_count}")

    return ansi("\n".join(lines))


def fmt_hand(hand: list[str]) -> str:
    if not hand:
        return ansi(f"{GRAY}你本輪已經沒有手牌。{RESET}")

    cards = "  ".join(f"{BOLD}{C}[ {card} ]{RESET}" for card in hand)
    return ansi(f"{W}你的手牌：{RESET}\n{cards}")


def fmt_reveal(claim, is_lying: bool, loser_name: str) -> str:
    colored = []

    for card in claim.actual_cards:
        if card == claim.claimed_rank or card == JOKER:
            colored.append(f"{G}{card}{RESET}")
        else:
            colored.append(f"{R}{card}{RESET}")

    cards_str = "  ".join(colored)
    verdict = f"{BOLD}{R}說謊！{RESET}" if is_lying else f"{BOLD}{G}誠實！{RESET}"
    loser_line = f"{BOLD}{R}{loser_name} 扣一滴血！{RESET}"

    lines = [
        f"{Y}聲稱：{claim.claimed_rank} × {claim.claimed_count}{RESET}",
        f"{W}實際：{RESET}{cards_str}",
        "",
        f"{verdict}  →  {loser_line}",
    ]

    return ansi("\n".join(lines))


def fmt_play_announce(player_name: str, claimed_rank: str, claimed_count: int) -> str:
    return ansi(
        f"{BOLD}{W}{player_name}{RESET} 打出了 "
        f"{BOLD}{Y}{claimed_count} 張牌{RESET}，"
        f"聲稱是 {BOLD}{M}{claimed_rank}{RESET}"
    )


def fmt_eliminated(player_name: str, hp_left: int) -> str:
    if hp_left <= 0:
        return ansi(f"{BOLD}{R}💀 {player_name} 已被淘汰！{RESET}")

    return ansi(f"{R}{player_name} 剩餘 {hp_left} 滴血{RESET}")


def fmt_winner(player_name: str) -> str:
    return ansi(
        f"{BOLD}{Y}🏆 遊戲結束！{RESET}\n"
        f"{BOLD}{G}勝者是 {player_name}！{RESET}"
    )


def fmt_lobby(session: GameSession) -> str:
    if not session.players:
        return ansi(f"{GRAY}還沒有玩家加入{RESET}")

    lines = [f"{BOLD}{W}── 房間玩家 ──{RESET}"]

    for i, player in enumerate(session.players):
        lines.append(f"  {C}{i + 1}.{RESET} {player.display_name}")

    lines.append(f"\n{GRAY}人數：{len(session.players)} / 6{RESET}")

    return ansi("\n".join(lines))
