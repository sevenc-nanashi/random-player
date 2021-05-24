import os

import discord
import motor.motor_asyncio
# import pymongo
from discord.ext import commands
from discord_slash import SlashCommand
from dotenv import load_dotenv

load_dotenv()
motor_client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("connectstr"))
musics_collection = motor_client.vocaloidcafe.musics
profile_collection = motor_client.vocaloidcafe.profile
vc_count_collection = motor_client.vocaloidcafe.vc_count


bot = commands.Bot(command_prefix=commands.when_mentioned, intents=discord.Intents.all(), allowed_mentions=discord.AllowedMentions.none())
slash = SlashCommand(bot, sync_commands=True)
bot.load_extension("jishaku")


@bot.event
async def on_ready():
    print("I'm ready!")
    await bot.change_presence(activity=discord.Game(
        name="/help"
    ))


bot.load_extension("cog")
bot.run(os.environ.get("token"))
