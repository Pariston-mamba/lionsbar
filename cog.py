import discord
from discord.ext import commands
from game import GameSession, GameState
from formatter import (
    fmt_hp_board, fmt_hand, fmt_reveal, fmt_play_announce,
    fmt_eliminated, fmt_winner, fmt_lobby,
)
from views import JoinView, HandView, ClaimView, DoubtView


class LiarsBarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, GameSession] = {}

    def get_session(self, guild_id: int) -> GameSession | None:
        return self.sessions.get(guild_id)

    def get_or_create_session(self, guild_id: int, channel_id: int) -> GameSession:
        if guild_id not in self.sessions:
            self.sessions[guild_id] = GameSession(guild_id, channel_id)
        return self.sessions[guild_id]

    # ── Slash Commands ────────────────────────────────────────

    @discord.app_commands.command(name="create", description="建立一個新的 Liar's Bar 房間")
    async def create(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in self.sessions and self.sessions[guild_id].state == GameState.PLAYING:
            await interaction.response.send_message("已經有遊戲在進行中！用 `/stop` 結束後再建立。", ephemeral=True)
            return

        self.sessions[guild_id] = GameSession(guild_id, interaction.channel_id)
        view = JoinView(self)
        await interaction.response.send_message(
            "🃏 **Liar's Bar 房間已建立！**\n點下方按鈕加入，集齊 2～6 人後開始遊戲。\n\n" + fmt_lobby(self.sessions[guild_id]),
            view=view,
        )

    @discord.app_commands.command(name="stop", description="強制結束目前遊戲")
    async def stop(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id not in self.sessions:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return
        del self.sessions[guild_id]
        await interaction.response.send_message("遊戲已強制結束。")

    @discord.app_commands.command(name="status", description="查看目前血量狀態")
    async def status(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)
        if not session or session.state != GameState.PLAYING:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return
        await interaction.response.send_message(fmt_hp_board(session))

    # ── 按鈕 Handlers ─────────────────────────────────────────

    async def handle_join(self, interaction: discord.Interaction):
        session = self.get_or_create_session(interaction.guild_id, interaction.channel_id)
        ok, msg = session.add_player(interaction.user.id, interaction.user.display_name)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** 加入了房間！\n\n{fmt_lobby(session)}"
        )

    async def handle_start(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("請先用 `/create` 建立房間。", ephemeral=True)
            return

        ok, msg = session.start_game()
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        await interaction.response.send_message(
            f"🎮 **遊戲開始！**\n\n{fmt_hp_board(session)}"
        )
        await self._prompt_play(interaction.channel, session)

    async def handle_play(self, interaction: discord.Interaction, indices: list[int], claimed_rank: str):
        session = self.get_session(interaction.guild_id)
        if not session:
            await interaction.response.send_message("找不到遊戲。", ephemeral=True)
            return

        ok, msg = session.play_cards(interaction.user.id, indices, claimed_rank)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        claim = session.last_claim
        announce = fmt_play_announce(interaction.user.display_name, claimed_rank, claim.claimed_count)

        await interaction.response.edit_message(content="出牌完成！", view=None)
        await interaction.channel.send(announce)

        session.advance_turn()
        doubter = session.get_current_player()
        doubt_view = DoubtView(self, doubter.discord_id)
        await interaction.channel.send(
            f"<@{doubter.discord_id}> 你要質疑嗎？",
            view=doubt_view,
        )

    async def handle_doubt(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)
        if not session:
            return

        is_lying = session.check_lie()
        claim = session.last_claim
        loser_id = claim.player_id if is_lying else interaction.user.id
        loser = session.get_player(loser_id)

        await interaction.response.edit_message(content="翻牌！", view=None)
        await interaction.channel.send(fmt_reveal(claim, is_lying, loser.display_name))

        loser, eliminated = session.apply_damage(loser_id)
        if eliminated:
            await interaction.channel.send(fmt_eliminated(loser.display_name, loser.hp))

        winner = session.check_winner()
        if winner:
            await interaction.channel.send(fmt_hp_board(session))
            await interaction.channel.send(fmt_winner(winner.display_name))
            del self.sessions[interaction.guild_id]
            return

        await interaction.channel.send(fmt_hp_board(session))

        if not loser.is_alive:
            session.advance_turn()

        session.reset_round()
        await self._prompt_play(interaction.channel, session)

    async def handle_pass(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)
        if not session:
            return

        await interaction.response.edit_message(content="✅ 放行", view=None)
        session.advance_turn()
        await self._prompt_play(interaction.channel, session)

    # ── 內部工具 ──────────────────────────────────────────────

    async def _prompt_play(self, channel: discord.TextChannel, session: GameSession):
        current = session.get_current_player()

        hand_view = HandView(self, current.discord_id, current.hand)
        hand_msg = fmt_hand(current.hand)

        await channel.send(
            f"<@{current.discord_id}> 輪到你出牌！\n{hand_msg}\n選好牌後點「確認出牌」",
            view=hand_view,
        )

        confirm_btn = ConfirmPlayView(self, current.discord_id, hand_view)
        await channel.send(view=confirm_btn)


class ConfirmPlayView(discord.ui.View):
    """確認出牌按鈕，會帶出 ClaimView"""

    def __init__(self, cog, current_player_id: int, hand_view: "HandView"):
        super().__init__(timeout=60)
        self.cog = cog
        self.current_player_id = current_player_id
        self.hand_view = hand_view

    @discord.ui.button(label="確認出牌", style=discord.ButtonStyle.success, emoji="✔")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("還沒輪到你！", ephemeral=True)
            return
        if not self.hand_view.selected_indices:
            await interaction.response.send_message("請先選擇要打出的牌！", ephemeral=True)
            return

        claim_view = ClaimView(self.cog, self.current_player_id, self.hand_view.selected_indices)
        await interaction.response.send_message(
            f"選了 {len(self.hand_view.selected_indices)} 張牌，聲稱是？",
            view=claim_view,
            ephemeral=True,
        )
