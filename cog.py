import discord
from discord.ext import commands
from game import GameSession, GameState
from formatter import (
    fmt_hp_board, fmt_hand, fmt_reveal, fmt_play_announce,
    fmt_eliminated, fmt_winner, fmt_lobby,
)
from views import JoinView, AllHandsView, TurnActionView, ClaimView


VIEW_TIMEOUT = 1800


class LionsBarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, GameSession] = {}

    def get_session(self, guild_id: int) -> GameSession | None:
        return self.sessions.get(guild_id)

    def get_or_create_session(self, guild_id: int, channel_id: int) -> GameSession:
        if guild_id not in self.sessions:
            self.sessions[guild_id] = GameSession(guild_id, channel_id)
        return self.sessions[guild_id]

    @discord.app_commands.command(name="create", description="建立一個新的 Lion's Bar 房間")
    async def create(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if guild_id in self.sessions and self.sessions[guild_id].state == GameState.PLAYING:
            await interaction.response.send_message(
                "已經有遊戲在進行中！如果按鈕失效或遊戲卡住，請先用 `/reset`，再用 `/create`。",
                ephemeral=True,
            )
            return

        self.sessions[guild_id] = GameSession(guild_id, interaction.channel_id)
        view = JoinView(self)

        await interaction.response.send_message(
            "🦁 **Lion's Bar 房間已建立！**\n"
            "點下方按鈕加入，集齊 2～6 人後開始遊戲。\n"
            "**提示：按鈕 30 分鐘後會失效；如果卡住，請用 `/reset` 後重新 `/create`。**\n\n"
            + fmt_lobby(self.sessions[guild_id]),
            view=view,
        )

    @discord.app_commands.command(name="stop", description="強制結束目前遊戲")
    async def stop(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if guild_id not in self.sessions:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return

        del self.sessions[guild_id]
        await interaction.response.send_message("遊戲已強制結束。現在可以重新使用 `/create`。")

    @discord.app_commands.command(name="reset", description="重置卡住的 Lion's Bar 遊戲")
    async def reset(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id

        if guild_id in self.sessions:
            del self.sessions[guild_id]

        await interaction.response.send_message(
            "Lion's Bar 已重置。現在可以重新使用 `/create` 建立房間。"
        )

    @discord.app_commands.command(name="status", description="查看目前血量狀態")
    async def status(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)

        if not session or session.state != GameState.PLAYING:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return

        await interaction.response.send_message(fmt_hp_board(session))

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
            f"🎮 **Lion's Bar 開始！**\n\n{fmt_hp_board(session)}\n"
            "所有玩家可以點下方按鈕查看自己的手牌。",
            view=AllHandsView(self, session),
        )

        await self._prompt_turn(interaction.channel, session)

    async def handle_play(self, interaction: discord.Interaction, indices: list[int], claimed_rank: str):
        session = self.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立房間。", ephemeral=True)
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
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立房間。", ephemeral=True)
            return

        is_lying = session.check_lie()
        claim = session.last_claim

        if not claim:
            await interaction.response.send_message("目前沒有可質疑的出牌。", ephemeral=True)
            return

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

        await interaction.channel.send(
            "新一輪開始，所有玩家可以點下方按鈕查看自己的新手牌。",
            view=AllHandsView(self, session),
        )

        await self._prompt_turn(interaction.channel, session)

    async def handle_pass(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立房間。", ephemeral=True)
            return

        await interaction.response.edit_message(content="✅ 放行", view=None)
        session.advance_turn()
        await self._prompt_turn(interaction.channel, session)

    async def _prompt_turn(self, channel: discord.TextChannel, session: GameSession):
        current = session.get_current_player()

        await channel.send(
            f"<@{current.discord_id}> 輪到你出牌！請點下方按鈕出牌。",
            view=TurnActionView(self, session.guild_id, current.discord_id),
        )


class DoubtView(discord.ui.View):
    def __init__(self, cog, doubter_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.doubter_id = doubter_id

    @discord.ui.button(label="質疑！", style=discord.ButtonStyle.danger, emoji="🔍")
    async def doubt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.doubter_id:
            await interaction.response.send_message("還沒輪到你質疑！", ephemeral=True)
            return

        self.stop()
        await self.cog.handle_doubt(interaction)

    @discord.ui.button(label="放行", style=discord.ButtonStyle.secondary, emoji="✅")
    async def pass_turn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.doubter_id:
            await interaction.response.send_message("還沒輪到你！", ephemeral=True)
            return

        self.stop()
        await self.cog.handle_pass(interaction)
