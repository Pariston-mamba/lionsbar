import discord
from discord.ext import commands
from game import GameSession, GameState
from formatter import (
    fmt_hp_board, fmt_reveal, fmt_play_announce,
    fmt_eliminated, fmt_winner, fmt_lobby,
)
from views import JoinView, AllHandsView, TurnActionView, DoubtView


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

        await interaction.response.send_message(
            "🦁 **Lion's Bar 房間已建立！**\n"
            "點下方按鈕加入，集齊 2～6 人後開始遊戲。\n"
            "**提示：按鈕 30 分鐘後會失效；如果卡住，請用 `/reset` 後重新 `/create`。**\n\n"
            + fmt_lobby(self.sessions[guild_id]),
            view=JoinView(self),
        )

    @discord.app_commands.command(name="stop", description="強制結束目前遊戲")
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild_id not in self.sessions:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return

        del self.sessions[interaction.guild_id]
        await interaction.response.send_message("遊戲已強制結束。現在可以重新使用 `/create`。")

    @discord.app_commands.command(name="reset", description="重置卡住的 Lion's Bar 遊戲")
    async def reset(self, interaction: discord.Interaction):
        self.sessions.pop(interaction.guild_id, None)
        await interaction.response.send_message("Lion's Bar 已重置。現在可以重新使用 `/create`。")

    @discord.app_commands.command(name="status", description="查看目前血量狀態")
    async def status(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)

        if not session or session.state != GameState.PLAYING:
            await interaction.response.send_message("目前沒有進行中的遊戲。", ephemeral=True)
            return

        await interaction.response.send_message(
            f"本輪桌面牌：**{session.table_rank}**\n\n{fmt_hp_board(session)}"
        )

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
            f"🎮 **Lion's Bar 開始！**\n"
            f"本輪桌面牌：**{session.table_rank}**\n\n"
            f"{fmt_hp_board(session)}\n"
            "所有玩家可以點下方按鈕查看自己的手牌。",
            view=AllHandsView(self, session.guild_id),
        )

        await self._prompt_turn(interaction.channel, session)

    async def handle_play(self, interaction: discord.Interaction, indices: list[int]):
        session = self.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立。", ephemeral=True)
            return

        ok, msg = session.play_cards(interaction.user.id, indices)

        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        claim = session.last_claim

        await interaction.response.edit_message(content="出牌完成！", view=None)
        await interaction.channel.send(
            fmt_play_announce(interaction.user.display_name, claim.claimed_rank, claim.claimed_count)
        )

        contenders = session.other_players_with_cards(claim.player_id)

        if not contenders:
            await interaction.channel.send("所有其他玩家都已出光手牌，本輪結束並重新發牌。")
            session.reset_round()
            await self._announce_new_round(interaction.channel, session)
            await self._prompt_turn(interaction.channel, session)
            return

        if len(contenders) == 1:
            forced = contenders[0]
            session.set_current_player(forced.discord_id)
            await interaction.channel.send(
                f"<@{forced.discord_id}> 只剩你還能處理這次出牌，你必須質疑！",
                view=DoubtView(self, forced.discord_id, allow_pass=False),
            )
            return

        session.advance_turn(skip_empty=True)
        doubter = session.get_current_player()

        await interaction.channel.send(
            f"<@{doubter.discord_id}> 你要質疑，還是繼續出牌？",
            view=DoubtView(self, doubter.discord_id, allow_pass=True),
        )

    async def handle_doubt(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立。", ephemeral=True)
            return

        claim = session.last_claim

        if not claim:
            await interaction.response.send_message("目前沒有可質疑的出牌。", ephemeral=True)
            return

        is_lying = session.check_lie()
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

        if loser.is_alive:
            session.set_current_player(loser.discord_id)
        else:
            session.advance_turn(skip_empty=False)

        session.reset_round()

        await interaction.channel.send(fmt_hp_board(session))
        await self._announce_new_round(interaction.channel, session)
        await self._prompt_turn(interaction.channel, session)

    async def handle_pass(self, interaction: discord.Interaction):
        session = self.get_session(interaction.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。請用 `/create` 重新建立。", ephemeral=True)
            return

        current = session.get_current_player()

        if interaction.user.id != current.discord_id:
            await interaction.response.send_message("還沒輪到你。", ephemeral=True)
            return

        await interaction.response.edit_message(content="✅ 選擇不質疑，繼續出牌。", view=None)
        await self._prompt_turn(interaction.channel, session)

    async def _announce_new_round(self, channel: discord.TextChannel, session: GameSession):
        await channel.send(
            f"新一輪開始！本輪桌面牌：**{session.table_rank}**\n"
            "所有玩家可以點下方按鈕查看自己的新手牌。",
            view=AllHandsView(self, session.guild_id),
        )

    async def _prompt_turn(self, channel: discord.TextChannel, session: GameSession):
        current = session.get_current_player()

        if len(current.hand) == 0:
            session.advance_turn(skip_empty=True)
            current = session.get_current_player()

        await channel.send(
            f"<@{current.discord_id}> 輪到你出牌！本輪你只能宣稱自己出的是 **{session.table_rank}**。",
            view=TurnActionView(self, session.guild_id, current.discord_id),
        )
