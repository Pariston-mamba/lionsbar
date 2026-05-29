import os
from threading import Thread

import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask

from cog import LionsBarCog


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("找不到 DISCORD_TOKEN，請在 Render 的 Environment Variables 設定它。")


app = Flask("")


@app.route("/")
def home():
    return "Lion's Bar Bot is alive!"


def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))


class LionsBarBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(LionsBarCog(self))
        await self.tree.sync()
        print("✅ Slash Commands 同步完成")


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = LionsBarBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Lion's Bar 機器人已上線：{bot.user}")


Thread(target=run_web, daemon=True).start()
bot.run(TOKEN)
