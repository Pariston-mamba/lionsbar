import discord
from game import RANKS


class JoinView(discord.ui.View):
    """開始前的加入房間按鈕"""

    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.button(label="加入遊戲", style=discord.ButtonStyle.primary, emoji="🃏")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_join(interaction)

    @discord.ui.button(label="開始遊戲", style=discord.ButtonStyle.success, emoji="▶")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_start(interaction)


class HandView(discord.ui.View):
    """查看手牌 + 選牌按鈕（Ephemeral，只有當前玩家看得到）"""

    def __init__(self, cog, current_player_id: int, hand: list[str]):
        super().__init__(timeout=60)
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

    def _make_card_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.current_player_id:
                await interaction.response.send_message("這不是你的手牌！", ephemeral=True)
                return

            if index in self.selected_indices:
                self.selected_indices.remove(index)
            else:
                self.selected_indices.append(index)

            self._refresh_buttons(interaction)
            await interaction.response.edit_message(view=self)

        return callback

    def _refresh_buttons(self, interaction):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("card_"):
                idx = int(item.custom_id.split("_")[1])
                item.style = (
                    discord.ButtonStyle.primary
                    if idx in self.selected_indices
                    else discord.ButtonStyle.secondary
                )


class ClaimView(discord.ui.View):
    """選擇聲稱牌面的按鈕"""

    def __init__(self, cog, current_player_id: int, selected_indices: list[int]):
        super().__init__(timeout=60)
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


class DoubtView(discord.ui.View):
    """質疑或放行按鈕"""

    def __init__(self, cog, doubter_id: int):
        super().__init__(timeout=60)
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
