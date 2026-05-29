import discord
from game import RANKS
from formatter import fmt_hand


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


class AllHandsView(discord.ui.View):
    def __init__(self, cog, session):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.guild_id = session.guild_id

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
            f"你的手牌：\n{fmt_hand(player.hand)}",
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

        hand_view = HandView(self.cog, self.current_player_id, player.hand)

        await interaction.response.send_message(
            f"你的手牌：\n{fmt_hand(player.hand)}\n請選擇要打出的牌。",
            view=hand_view,
            ephemeral=True,
        )


class HandView(discord.ui.View):
    def __init__(self, cog, current_player_id: int, hand: list[str]):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.current_player_id = current_player_id
        self.selected_indices: list[int] = []

        for i, card in enumerate(hand):
            btn = discord.ui.Button(
                label=f"{card}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"card_{i}",
                row=0,
            )
            btn.callback = self._make_card_callback(i)
            self.add_item(btn)

        confirm_btn = discord.ui.Button(
            label="確認出牌",
            style=discord.ButtonStyle.success,
            emoji="✔",
            row=1,
        )
        confirm_btn.callback = self.confirm_play
        self.add_item(confirm_btn)

    def _make_card_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.current_player_id:
                await interaction.response.send_message("這不是你的手牌！", ephemeral=True)
                return

            if index in self.selected_indices:
                self.selected_indices.remove(index)
            else:
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

        claim_view = ClaimView(self.cog, self.current_player_id, self.selected_indices)

        await interaction.response.send_message(
            f"選了 {len(self.selected_indices)} 張牌，聲稱是？",
            view=claim_view,
            ephemeral=True,
        )

    def _refresh_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("card_"):
                idx = int(item.custom_id.split("_")[1])
                item.style = (
                    discord.ButtonStyle.primary
                    if idx in self.selected_indices
                    else discord.ButtonStyle.secondary
                )


class ClaimView(discord.ui.View):
    def __init__(self, cog, current_player_id: int, selected_indices: list[int]):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.cog = cog
        self.current_player_id = current_player_id
        self.selected_indices = selected_indices

        for rank in RANKS:
            btn = discord.ui.Button(
                label=f"聲稱是 {rank}",
                style=discord.ButtonStyle.primary,
                custom_id=f"claim_{rank}",
                row=0,
            )
            btn.callback = self._make_claim_callback(rank)
            self.add_item(btn)

    def _make_claim_callback(self, rank: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.current_player_id:
                await interaction.response.send_message("還沒輪到你！", ephemeral=True)
                return

            await self.cog.handle_play(interaction, self.selected_indices, rank)

        return callback
