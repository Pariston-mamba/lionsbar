import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
from dotenv import load_dotenv
from cog import LiarsBarCog

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Flask keep-alive（防止 Render 休眠）──────────────────────
app = Flask("")

@app.route("/")
def home():
    return "Liar's Bar Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

Thread(target=run_web, daemon=True).start()

# ── Discord Bot ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ 機器人已上線：{bot.user}")
    await bot.add_cog(LiarsBarCog(bot))
    await bot.tree.sync()
    print("✅ Slash Commands 同步完成")

bot.run(TOKEN)
