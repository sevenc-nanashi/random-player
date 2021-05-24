import asyncio
import datetime
import json
import os
import random

import discord
import motor.motor_asyncio
import youtube_dl
from discord.ext import commands
from discord_slash import SlashContext
from discord_slash.utils import manage_commands
from discord_slash.cog_ext import cog_slash
from sembed import SAuthor, SEmbed, SFooter  # , SField
motor_client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("connectstr"))
musics_collection = motor_client.vocaloidcafe.musics
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn -af volume=-15dB',
    "executable": r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -loglevel quiet"
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

guild_ids = [int(os.getenv("main_guild_id"))]
users = []
musics = {}
log_musics = {}
shuffled_musics = []
event_name = ""
index = 0
running_channel = None

MAIN_VC_ID = int(os.getenv("main_vc_id"))
MAIN_GUILD = None


class MainCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        global MAIN_GUILD
        MAIN_GUILD = self.bot.get_guild(int(os.getenv("main_guild_id")))
        self.log_vc.stop()
        self.log_vc.start()

    @cog_slash(name="help", guild_ids=guild_ids, description="ヘルプを表示します。")
    async def _help(self, ctx: SlashContext):
        global channel, musics, index, force_skip, users
        try:
            await ctx.send("""
このBotはランダムに音楽を流すBotです。
**再生モード**
1. `/start` で開始する。
2. 選ばれたら`/register`で曲を登録する。
- `/register https://youtu.be/nNhDezUbvSc` のように使います。
3. 待つ

**ログモード**
最後に送信されたIDから曲を表示します。
`/log ログID`

Source code: [sevenc-nanashi/randomplayer](https://github.com/sevenc-nanashi/randomplayer)
Created by [名無し。（@sevenc-nanashi）](https://github.com/sevenc-nanashi)
            """, hidden=True)
        except discord.errors.NotFound:
            pass

    @cog_slash(name="start", guild_ids=guild_ids, description="布教会を開始します。", options=[manage_commands.create_option(
        name="Number",
        description="曲をリクエストできる人の数。",
        option_type=4,
        required=True
    ), manage_commands.create_option(
        name="Channel",
        description="再生するチャンネル。",
        option_type=3,
        required=False
    ), manage_commands.create_option(
        name="Name",
        description="イベント名。省略で「音楽布教会」になります。",
        option_type=3,
        required=False
    )])
    async def _start(self, ctx: SlashContext, number: int, channel: discord.VoiceChannel, name: str = "音楽布教会"):
        global running_channel, musics, log_musics, event_name
        running_channel = channel
        vc_members = [m for m in running_channel.members if not m.bot]
        running_channel = ctx.channel.id
        rm = random.sample(vc_members, number)
        event_name = name
        await ctx.send(content=f"**{name}！**\n今回は…")
        musics = {}
        log_musics = {}
        for e in rm:
            await asyncio.sleep(1)
            users.append(e.id)
            await ctx.send(e.mention + "さん")
        await ctx.send("が選ばれました！\n`/register`で曲の登録をお願いします！")
        await ctx.send(content="全員登録した後、`/next`で開始します。")

    @cog_slash(name="register", guild_ids=guild_ids, description="曲を登録します。", options=[manage_commands.create_option(
        name="URL",
        description="曲のURL。",
        option_type=3,
        required=True
    )])
    async def _register(self, ctx: SlashContext, url: str):
        global running_channel, shuffled_musics, index
        if running_channel is None:
            await ctx.defer(hidden=True)
            return await ctx.send(content="布教会は始まっていません。", hidden=True)
        elif ctx.author.id not in users:
            await ctx.defer(hidden=True)
            return await ctx.send(content="あなたは選ばれていません。", hidden=True)
        elif ctx.author.id in musics.keys():
            await ctx.defer(hidden=True)
            return await ctx.send(content="既にリクエスト済みです。", hidden=True)
        if not ("youtu.be" in url or "youtube.com" in url):
            await ctx.defer(hidden=True)
            return await ctx.send(content="無効なURLです。", hidden=True)
        musics[ctx.author.id] = url
        await ctx.channel.send(f"{ctx.author.mention}さんの登録が完了しました！")
        if len(musics.keys()) == len(users):
            ch = self.bot.get_channel(812511695665627158)
            await ch.send("全員の登録が完了しました！")
            index = -1
            shuffled_musics = list(musics.items())
            random.shuffle(shuffled_musics)

    @cog_slash(name="next", guild_ids=guild_ids, description="再生を開始します。")
    async def _next(self, ctx: SlashContext):
        global running_channel, musics, index, force_skip, users, log_musics
        if running_channel is None:
            await ctx.defer(hidden=True)
            return await ctx.send(content="布教会は始まっていません。", hidden=True)
        try:
            if len(musics.keys()) != len(users):
                await ctx.defer(hidden=True)
                return await ctx.send(content="まだ全員登録していません。", hidden=True)
            elif len(musics.keys()) == 0:
                await ctx.defer(hidden=True)
                return await ctx.send(content="最初に`/start`をしてください。", hidden=True)
            await ctx.defer(hidden=True)
        except discord.errors.NotFound:
            return
        index += 1
        if ctx.guild.voice_client:
            vc = ctx.guild.voice_client
            if vc.channel.name != ctx.channel.name:
                return await ctx.send(content="別チャンネルで使用中です。", hidden=True)
        else:
            await running_channel.connect()
        if vc.is_playing():
            vc.stop()
            return await ctx.send(content="強制終了しました。", hidden=True)
        if index == 0:
            await ctx.send(f"{event_name}の始まりです！")
            log_musics = {}
        async with running_channel.typing():
            loop = asyncio.get_event_loop()
            user = self.bot.get_user(shuffled_musics[index][0])
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(shuffled_musics[index][1], download=False))
            e = SEmbed(data["title"], "\n".join(data["description"].splitlines()[:8]),
                       author=SAuthor(name=str(user), icon_url=str(user.avatar_url_as(static_format="png"))),
                       thumbnail_url=data["thumbnails"][0]["url"],
                       footer=SFooter(text=f"{len(musics.keys())}曲中{index+1}曲目"),
                       url=f"https://youtu.be/{data['id']}",
                       color=0xff0000)
            log_musics[user.id] = f'[{data["title"]}](https://youtu.be/{data["id"]})'
            await running_channel.send(embed=e)
        vc.play(discord.FFmpegOpusAudio(data["formats"][0]["url"], bitrate=512, **ffmpeg_options))
        while vc.is_playing():
            await asyncio.sleep(1)

        await running_channel.send(content="再生が終了しました。")
        if index + 1 == len(musics.keys()):
            await running_channel.send(content="全ての曲が再生されました！\nご静聴、ありがとうございました！")
            dtn = datetime.datetime.now()
            tmpid = dtn.strftime("%y%m%d%H%M%S")
            async with running_channel.typing():
                await musics_collection.insert_one({
                    "id": tmpid,
                    "name": event_name,
                    "musics": json.loads(json.dumps(log_musics))
                })
                await running_channel.send(f"`{tmpid}`というIDで保存しました。`/log {tmpid}`で呼び出せます。")
            musics = {}
            index = -1
            users = []
            log_musics = {}

    @cog_slash(name="finish", guild_ids=guild_ids, description="終了します。")
    async def _finish(self, ctx: SlashContext):
        global users, musics, index
        await ctx.defer(hidden=False)
        if ctx.guild.voice_client is None:
            await ctx.send(content="VCに接続していません。スキップされました。", hidden=True)
        else:
            await ctx.guild.voice_client.disconnect()
        musics = {}
        index = -1
        users = []
        await ctx.send(f"{event_name}を終了しました。", hidden=True)

    @cog_slash(name="reselect", guild_ids=guild_ids, description="対象の代わりを抽選します。", options=[manage_commands.create_option(
        name="Target",
        description="再抽選の対象。",
        option_type=6,
        required=True
    )])
    async def _reselect(self, ctx: SlashContext, user: discord.Member):
        global running_channel, musics, index, force_skip, users
        try:
            if user.id not in users:
                await ctx.defer(hidden=True)
                return await ctx.send(content="選択された人を指定してください。", hidden=True)
            await ctx.defer(hidden=False)
            vc_members = [m for m in self.bot.get_channel(MAIN_VC_ID).members if (not m.bot) and m.id not in users]
            rm = random.choice(vc_members)
            users.remove(user.id)
            users.append(rm.id)
            await ctx.send(f"{user.mention}さんの代わりに、{rm.mention}さんが選ばれました！")
        except discord.errors.NotFound:
            pass

    @cog_slash(name="log", guild_ids=guild_ids, description="過去ログを参照します。", options=[manage_commands.create_option(
        name="ID",
        description="ログID。最後に送信されたものです。",
        option_type=3,
        required=True
    )])
    async def _log(self, ctx: SlashContext, logid: str):
        global musics, index, force_skip, users
        try:
            await ctx.defer(hidden=True)
            r = await musics_collection.find_one({"id": logid})
            if r is None:
                return await ctx.send("ログが見付かりませんでした。", hidden=True)
            t = datetime.datetime.strptime(logid, "%y%m%d%H%M%S")
            res = t.strftime(f"**%Y/%m/%d %H:%M:%Sの{r['name']}のログ**")
            for mk, mv in r["musics"].items():
                tres = f"\n<@!{mk}>さん： {mv}"

                if len(res + tres) > 2000:
                    await ctx.send(res, allowed_mentions=discord.AllowedMentions.none())
                    res = ""
                res += tres

            await ctx.send(res, allowed_mentions=discord.AllowedMentions.none())

        except discord.errors.NotFound:
            pass

    @commands.command("reload")
    @commands.is_owner()
    async def _reload(self, ctx):
        self.bot.reload_extension("cog")
        await ctx.reply("Done")


def setup(bot):
    bot.add_cog(MainCog(bot))
