import discord
from formatter import fmt_hand
from game import MAX_PLAY_CARDS


VIEW_TIMEOUT = 1800


class JoinView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog

    @discord.ui.button(label="加入遊戲", style=discord.ButtonStyle.primary, emoji="🦁")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_join(interaction)

    @discord.ui.button(label="開始遊戲", style=discord.ButtonStyle.success, emoji="▶")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_start(interaction)

    @discord.ui.button(label="查看規則", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**🦁 Lion's Bar 規則**\n"
            "🎯 每輪會指定一種桌面牌，例如 A，所有人都只能宣稱自己出的牌是桌面牌。\n"
            "🎴 輪到你時，可以出 1～3 張牌；Joker 可當作任意桌面牌。\n"
            "👀 玩家出牌後，下一位玩家要先決定：質疑，或不質疑並輪到自己出牌。\n"
            "🔍 如果質疑成功，出牌者扣 1 血；如果質疑錯誤，質疑者扣 1 血。\n"
            "🔁 只要有人質疑並翻牌，該輪立刻結束，重新發牌並指定新的桌面牌。\n"
            "👑 下一輪由扣血的玩家先出牌；若該玩家被淘汰，則由下一位存活玩家開始。\n"
            "🃏 手牌出光的玩家本輪跳過；只剩一位玩家有手牌時，該玩家必須質疑。\n"
            "🏆 活到最後的人獲勝。",
            ephemeral=True,
        )
class AllHandsView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="查看我的手牌", style=discord.ButtonStyle.primary, emoji="🃏")
    async def show_my_hand(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.get_session(self.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。", ephemeral=True)
            return

        player = session.get_player(interaction.user.id)

        if not player:
            await interaction.response.send_message("你不是本局玩家。", ephemeral=True)
            return

        await interaction.response.send_message(
            f"本輪桌面牌：**{session.table_rank}**\n{fmt_hand(player.hand)}",
            ephemeral=True,
        )


class TurnActionView(discord.ui.View):
    def __init__(self, cog, guild_id: int, current_player_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.guild_id = guild_id
        self.current_player_id = current_player_id

    @discord.ui.button(label="出牌", style=discord.ButtonStyle.success, emoji="🎴")
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("還沒輪到你！", ephemeral=True)
            return

        session = self.cog.get_session(self.guild_id)

        if not session:
            await interaction.response.send_message("找不到遊戲。", ephemeral=True)
            return

        player = session.get_player(interaction.user.id)

        if not player:
            await interaction.response.send_message("你不是本局玩家。", ephemeral=True)
            return

        if len(player.hand) == 0:
            await interaction.response.send_message("你本輪已經沒有手牌。", ephemeral=True)
            return

        await interaction.response.send_message(
            f"本輪桌面牌：**{session.table_rank}**\n"
            f"{fmt_hand(player.hand)}\n"
            f"請選擇 1～{MAX_PLAY_CARDS} 張牌。你將宣稱它們都是 **{session.table_rank}**。",
            view=HandView(self.cog, self.current_player_id, player.hand),
            ephemeral=True,
        )


class HandView(discord.ui.View):
    def __init__(self, cog, current_player_id: int, hand: list[str]):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.current_player_id = current_player_id
        self.selected_indices: list[int] = []

        for i, card in enumerate(hand):
            button = discord.ui.Button(
                label=card,
                style=discord.ButtonStyle.secondary,
                custom_id=f"card_{i}",
                row=0,
            )
            button.callback = self._make_card_callback(i)
            self.add_item(button)

        confirm_button = discord.ui.Button(
            label="確認出牌",
            style=discord.ButtonStyle.success,
            emoji="✔",
            row=1,
        )
        confirm_button.callback = self.confirm_play
        self.add_item(confirm_button)

    def _make_card_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.current_player_id:
                await interaction.response.send_message("這不是你的手牌！", ephemeral=True)
                return

            if index in self.selected_indices:
                self.selected_indices.remove(index)
            else:
                if len(self.selected_indices) >= MAX_PLAY_CARDS:
                    await interaction.response.send_message(
                        f"一次最多只能選 {MAX_PLAY_CARDS} 張牌。",
                        ephemeral=True,
                    )
                    return
                self.selected_indices.append(index)

            self._refresh_buttons()
            await interaction.response.edit_message(view=self)

        return callback

    async def confirm_play(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("還沒輪到你！", ephemeral=True)
            return

        if not self.selected_indices:
            await interaction.response.send_message("請先選擇要打出的牌！", ephemeral=True)
            return

        await self.cog.handle_play(interaction, self.selected_indices)

    def _refresh_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("card_"):
                index = int(item.custom_id.split("_")[1])
                item.style = (
                    discord.ButtonStyle.primary
                    if index in self.selected_indices
                    else discord.ButtonStyle.secondary
                )


class DoubtView(discord.ui.View):
    def __init__(self, cog, doubter_id: int, allow_pass: bool):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.doubter_id = doubter_id

        doubt_button = discord.ui.Button(
            label="質疑！",
            style=discord.ButtonStyle.danger,
            emoji="🔍",
            row=0,
        )
        doubt_button.callback = self.doubt
        self.add_item(doubt_button)

        if allow_pass:
            pass_button = discord.ui.Button(
                label="不質疑，繼續出牌",
                style=discord.ButtonStyle.secondary,
                emoji="✅",
                row=0,
            )
            pass_button.callback = self.pass_turn
            self.add_item(pass_button)

    async def doubt(self, interaction: discord.Interaction):
        if interaction.user.id != self.doubter_id:
            await interaction.response.send_message("還沒輪到你質疑！", ephemeral=True)
            return

        self.stop()
        await self.cog.handle_doubt(interaction)

    async def pass_turn(self, interaction: discord.Interaction):
        if interaction.user.id != self.doubter_id:
            await interaction.response.send_message("還沒輪到你！", ephemeral=True)
            return

        self.stop()
        await self.cog.handle_pass(interaction)
