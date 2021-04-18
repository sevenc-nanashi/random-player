import asyncio
import datetime
import json
import os
import random

import discord
import motor.motor_asyncio
import youtube_dl
from discord.ext import commands, tasks
from discord_slash import SlashContext
from discord_slash.utils import manage_commands
from discord_slash.cog_ext import cog_slash, cog_subcommand
from sembed import SAuthor, SEmbed, SFooter  # , SField
motor_client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("connectstr"))
musics_collection = motor_client.vocaloidcafe.musics
profile_collection = motor_client.vocaloidcafe.profile
vc_count_collection = motor_client.vocaloidcafe.vc_count
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

guild_ids = [732924162951086080, 808283612105408533]
users = []
musics = {}
log_musics = {}
shuffled_musics = []
event_name = ""
index = 0

MAIN_VC_ID = 808302657445036044
MAIN_GUILD_ID = 808283612105408533
MAIN_GUILD = None


def can_play(user):
    if user.id in [521166149904236554, 686547120534454315]:
        return True
    elif [r for r in user.roles if r.name == "布教会DJ"]:
        return True
    else:
        return False


async def check_exists(user):
    r = await profile_collection.find_one({"uid": user.id})
    if r is None:
        await profile_collection.insert_one({
            "uid": user.id,
            "text": "（自己紹介未設定）",
            "music": "（イチオシ曲未設定）"
        })


class MainCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        global MAIN_GUILD
        MAIN_GUILD = self.bot.get_guild(MAIN_GUILD)
        self.log_vc.stop()
        self.log_vc.start()

    @cog_slash(name="help", guild_ids=guild_ids, description="ヘルプを表示します。")
    async def _help(self, ctx: SlashContext):
        global channel, musics, index, force_skip, users
        try:
            await ctx.send("""
このBotはこのサーバー専属のBotです。
**布教会モード**
1. `/start` で開始する。
2. 選ばれたら`/register`で曲を登録する。
- `/register https://youtu.be/nNhDezUbvSc` のように使います。
3. 待つ

**ログ閲覧モード**
布教会の最後のIDを持ってきます。
`/log ログID`

**イベント送信モード**
`/event イベント名`とすると<#808306538401759252>に送信されます。

**プロフィール**
プロフィールを使うことで
・自己紹介
・イチオシ曲
を設定出来ます。
`/profile show ユーザー`でユーザーのプロフィールが閲覧できます。
`/profile text`で自己紹介を設定出来ます。（設定した後にDMに送信）
`/profile music URL`でイチオシ曲を設定出来ます。

Source code: [sevenc-nanashi/vocaloidcafe](https://github.com/sevenc-nanashi/vocaloidcafe)
Created by 名無し。（No Name.#1225）
Icon by ともろう#2374
            """, hidden=True)
        except discord.errors.NotFound:
            pass

    @cog_slash(name="start", guild_ids=guild_ids, description="布教会を開始します。", options=[manage_commands.create_option(
        name="Number",
        description="曲をリクエストできる人の数。",
        option_type=4,
        required=True
    ), manage_commands.create_option(
        name="Name",
        description="イベント名。省略で「ボカロ布教会」になります。",
        option_type=3,
        required=False
    )])
    async def _start(self, ctx: SlashContext, number: int, name: str = "ボカロ布教会"):
        global channel, musics, log_musics, event_name
        # if not can_play(ctx.author):
        #     await ctx.defer(hidden=True)
        #     return await ctx.send(content="このコマンドは`Amachi#7900`、`No Name.#1225`、または「布教会DJ」ロールを持っている人にしか使用できません。", hidden=True)
        vc_members = [m for m in self.bot.get_channel(MAIN_VC_ID).members if not m.bot]
        channel = ctx.channel.id
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
        await ctx.send(content="全員登録した後、`/next`で開始します。", hidden=True)

    @cog_slash(name="info", guild_ids=guild_ids, description="いろいろな情報を表示します。")
    async def _info(self, ctx):
        profile_count = 0
        async for p in profile_collection.find():
            if p["text"] != "（自己紹介未設定）" or p["music"] != "（イチオシ曲未設定）":
                profile_count += 1

        vc_count = 0
        for vc in ctx.guild.voice_channels:
            vc_count += len(vc.members)

        await ctx.send(f"""
**{ctx.guild.name}の情報**
メンバー数：{len([m for m in ctx.guild.members if m.status is not discord.Status.offline])}人 / {len(ctx.guild.members)}人
VC中：{vc_count}人
プロフィール登録済み：{profile_count}人
        """, hidden=True)

    @cog_slash(name="register", guild_ids=guild_ids, description="曲を登録します。", options=[manage_commands.create_option(
        name="URL",
        description="曲のURL。",
        option_type=3,
        required=True
    )])
    async def _register(self, ctx: SlashContext, url: str):
        global channel, shuffled_musics, index
        if ctx.author.id not in users:
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
        global channel, musics, index, force_skip, users, log_musics
        try:
            # if not can_play(ctx.author):
            #     await ctx.defer(hidden=True)
            #     return await ctx.send(content="このコマンドは`Amachi#7900`、`No Name.#1225`、または「布教会DJ」ロールを持っている人にしか使用できません。", hidden=True)
            # el
            if len(musics.keys()) != len(users):
                await ctx.defer(hidden=True)
                return await ctx.send(content="まだ全員登録していません。", hidden=True)
            elif len(musics.keys()) == 0:
                await ctx.defer(hidden=True)
                return await ctx.send(content="最初に`/start`をしてください。", hidden=True)
            await ctx.defer(hidden=True)
        except discord.errors.NotFound:
            return
        # ch = self.bot.get_channel(812511695665627158)
        index += 1
        if ctx.guild.voice_client:
            vc = ctx.guild.voice_client
            if vc.channel.name != ctx.channel.name:
                return await ctx.send(content="別チャンネルで使用中です。", hidden=True)
        else:
            ch = discord.utils.get(ctx.guild.voice_channels, name=ctx.channel.name)
            if not ch:
                return await ctx.send(content="タイムラインでは使用できません。", hidden=True)
            await ch.connect()
        if vc.is_playing():
            vc.stop()
            return await ctx.send(content="強制終了しました。", hidden=True)
        if index == 0:
            await ctx.send(f"{event_name}の始まりです！")
            log_musics = {}
        async with ch.typing():
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
            await ch.send(embed=e)
        vc.play(discord.FFmpegOpusAudio(data["formats"][0]["url"], bitrate=512, **ffmpeg_options))
        while vc.is_playing():
            await asyncio.sleep(1)

        await ch.send(content="再生が終了しました。")
        if index + 1 == len(musics.keys()):
            await ch.send(content="全ての曲が再生されました！\nご静聴、ありがとうございました！")
            dtn = datetime.datetime.now()
            tmpid = dtn.strftime("%y%m%d%H%M%S")
            async with ch.typing():
                await musics_collection.insert_one({
                    "id": tmpid,
                    "name": event_name,
                    "musics": json.loads(json.dumps(log_musics))
                })
                await ch.send(f"`{tmpid}`というIDで保存しました。`/log {tmpid}`で呼び出せます。")
            musics = {}
            index = -1
            users = []
            log_musics = {}

    @cog_slash(name="finish", guild_ids=guild_ids, description="終了します。")
    async def _finish(self, ctx: SlashContext):
        global users, musics, index
        # if not can_play(ctx.author):
        #     await ctx.defer(hidden=True)
        #     return await ctx.send(content="このコマンドは`Amachi#7900`、`No Name.#1225`、または「布教会DJ」ロールを持っている人にしか使用できません。", hidden=True)
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
        global channel, musics, index, force_skip, users
        try:
            # if not can_play(ctx.author):
            #     await ctx.defer(hidden=True)
            #     return await ctx.send(content="このコマンドは`Amachi#7900`、`No Name.#1225`、または「布教会DJ」ロールを持っている人にしか使用できません。", hidden=True)
            # el
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
        global channel, musics, index, force_skip, users
        try:
            await ctx.defer(hidden=True)
            r = await musics_collection.find_one({"id": logid})
            if r is None:
                return await ctx.send("ログが見付かりませんでした。", hidden=True)
            t = datetime.datetime.strptime(logid, "%y%m%d%H%M%S")
            # ut = t - datetime.timedelta(hours=9)
            res = t.strftime(f"**%Y/%m/%d %H:%M:%Sの{r['name']}のログ**")
            for mk, mv in r["musics"].items():
                tres = f"\n<@!{mk}>さん： {mv}"

                if len(res + tres) > 2000:
                    await ctx.send(res, hidden=True, allowed_mentions=discord.AllowedMentions.none())
                    res = ""
                res += tres

            await ctx.send(res, hidden=True, allowed_mentions=discord.AllowedMentions.none())

        except discord.errors.NotFound:
            pass

    @cog_slash(name="event", guild_ids=guild_ids, description="イベント開始・開催中通知を流します。", options=[manage_commands.create_option(
        name="Name",
        description="イベント名。",
        option_type=3,
        required=True
    ), manage_commands.create_option(
        name="Current",
        description="現在進行しているかどうか。省略でFalseになります。",
        option_type=5,
        required=False
    ), manage_commands.create_option(
        name="From",
        description="開催者。省略で実行者になります。",
        option_type=6,
        required=False
    ), manage_commands.create_option(
        name="Type",
        description="イベントの種類。`Sing`で歌、`Talk`で雑談になります。省略するとその他になります。",
        option_type=3,
        required=False,
        choices=["Sing", "Talk"]
    ), ])
    async def _event(self, ctx: SlashContext, event_name: str, current: bool = False, event_by: discord.Member = None, event_type: str = None):
        global channel, musics, index, force_skip, users
        try:
            await ctx.defer(hidden=False)
            ch = self.bot.get_channel(808306538401759252)
            if event_type == "Sing":
                mention = "<@&821537813413363742>\n"
            else:
                mention = "<@&821537562937262151>\n"

            await ch.send(f"{mention}\n{(event_by or ctx.author).mention}さんが{ctx.channel.mention}で\n> {event_name}\nを開催し{'てい' if current else ''}ます！", allowed_mentions=discord.AllowedMentions(users=False, everyone=False))
        except discord.errors.NotFound:
            pass

    @cog_subcommand(base="profile", name="show", guild_ids=guild_ids, description="プロフィールを表示します。", options=[manage_commands.create_option(
        name="Target",
        description="表示するユーザー。",
        option_type=6,
        required=True
    )])
    async def _profile_show(self, ctx: SlashContext, user: discord.Member):
        await ctx.defer()
        await check_exists(user)
        m = await profile_collection.find_one({"uid": user.id})
        await ctx.send(f"**{user.mention}さんの情報**\n"
                       + f"アカウント作成日時：{(user.created_at + datetime.timedelta(hours=9)).strftime('%Y/%m/%d %H:%M:%S')}\n"
                       + f"サーバー参加日時：{(user.joined_at + datetime.timedelta(hours=9)).strftime('%Y/%m/%d %H:%M:%S')}\n"
                       + "自己紹介：\n"
                       + "> " + "\n> ".join(m["text"].splitlines()) + "\n" + "イチオシ曲：\n"
                       + (m["music"] if isinstance(m["music"], str) else f'[{m["music"]["title"]}]({m["music"]["url"]}) - [{m["music"]["uploader"]["name"]}]({m["music"]["uploader"]["url"]})'), hidden=True)

    @cog_subcommand(base="profile", name="text", guild_ids=guild_ids, description="プロフィールの自己紹介を登録します。",)
    async def _profile_text(self, ctx: SlashContext):
        global channel, shuffled_musics, index
        await ctx.defer(hidden=True)
        await ctx.send("自己紹介をDMに送信して下さい。\n1分後に時間切れになります。", hidden=True)
        try:
            msg = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id, timeout=60)
            await check_exists(ctx.author)
            await profile_collection.update_one({"uid": ctx.author.id}, {"$set": {"text": msg.content}})
            await ctx.send("設定が完了しました。", hidden=True)
        except asyncio.TimeoutError:
            await ctx.send("タイムアウトしました。", hidden=True)

    @cog_subcommand(base="profile", name="music", guild_ids=guild_ids, description="プロフィールのイチオシ曲を登録します。", options=[manage_commands.create_option(
        name="URL",
        description="曲のURL。",
        option_type=3,
        required=True
    ), manage_commands.create_option(
        name="Name",
        description="曲の名前。省略するとYouTubeのタイトルになります。",
        option_type=3,
        required=False
    ), manage_commands.create_option(
        name="Author",
        description="作者の名前。省略するとYouTubeの投稿者名になります。",
        option_type=3,
        required=False
    )])
    async def _profile_music(self, ctx: SlashContext, url: str, name: str = None, author: str = None):
        if not ("youtu.be" in url or "youtube.com" in url):
            await ctx.defer(hidden=True)
            return await ctx.send(content="無効なURLです。", hidden=True)
        loop = asyncio.get_event_loop()
        await ctx.send("情報を抽出中です。", hidden=True)
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        await profile_collection.update_one({"uid": ctx.author.id}, {"$set": {"music": {"url": f"https://youtu.be/{data['id']}", "title": (name or data["title"]), "uploader": {"name": (author or data["uploader"]), "url": data["uploader_url"]}}}})
        await ctx.send("登録が完了しました。", hidden=True)

    @tasks.loop(hours=1)
    async def log_vc(self):
        vc_count = 0
        for vc in MAIN_GUILD.voice_channels:
            vc_count += len(vc.members)
        await vc_count_collection.insert_one({"datetime": datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S"), "count": vc_count})
        cursor = vc_count_collection.find()
        async for d in cursor:
            if (datetime.datetime.now() - datetime.datetime.strptime(d["datetime"], "%y/%m/%d %H:%M:%S")).seconds / 3600 >= 12:
                await vc_count_collection.delete_one(d)

        if (datetime.datetime.now().hour) % 6 == 0:
            text = "> **定期的なお知らせ**\n" + random.choice(["""
`/profile text` で自己紹介を、
`/profile music` でイチオシ曲を設定でき、
`/profile show` でプロフィールを見ることが出来ます！
    """,
                                                       """
`/event` で<#808306538401759252>に何をやっているか投稿できます！
    """])
            await self.bot.get_channel(808306538401759252).send(text)

    @log_vc.before_loop
    async def log_vc_before(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep((60 - datetime.datetime.now().minute) * 60)

    @cog_slash(name="vclog", guild_ids=guild_ids, description="VC接続人数のログを表示します。")
    async def vclog(self, ctx):
        res = "> **VC接続人数ログ**\n"
        l = []
        async for d in vc_count_collection.find():
            l.append(d)
        l.sort(key=lambda d: datetime.datetime.strptime(d["datetime"], "%y/%m/%d %H:%M:%S"))
        for d in l[:11]:
            m = datetime.datetime.strptime(d["datetime"], "%y/%m/%d %H:%M:%S")  # - datetime.timedelta(hours=9)
            res += f'{m.strftime("%Y/%m/%d %H:%M:%S")}: {d["count"]}人\n'
        await ctx.send(res, hidden=True)

    @commands.command("reload")
    @commands.is_owner()
    async def _reload(self, ctx):
        self.bot.reload_extension("cog")
        await ctx.reply("Done")
    # @bot.listen("on_voice_state_update")
    # async def move_notify(member, before, after):
    #     if after.channel == before.channel:
    #         return
    #     if after.channel is None:
    #         channel = discord.utils.get(member.guild.text_channels, name=before.channel.name)
    #         await channel.send(f"{member.mention}さんが{before.channel.name}を退出しました。", allowed_mentions=discord.AllowedMentions.none())
    #     elif before.channel is None:
    #         channel = discord.utils.get(member.guild.text_channels, name=after.channel.name)
    #         await channel.send(f"{member.mention}さんが{after.channel.name}に入室しました。", allowed_mentions=discord.AllowedMentions.none())
    #     else:
    #         channel = discord.utils.get(member.guild.text_channels, name=after.channel.name)
    #         await channel.send(f"{member.mention}さんが{before.channel.name}から{after.channel.name}へ移動しました。", allowed_mentions=discord.AllowedMentions.none())
    #         channel = discord.utils.get(member.guild.text_channels, name=before.channel.name)
    #         await channel.send(f"{member.mention}さんが{before.channel.name}から{after.channel.name}へ移動しました。", allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_voice_channel_update(self, member, before, after):
        channel = before or after
        if len(channel.members) == 1 and channel.id not in [823140380388098049]:
            chname = channel.mention
            if channel.category and channel.category.id != 833117282016297000:
                chname = channel.category.name + "の" + channel.mention
            if member.id == 521166149904236554:
                await self.bot.get_channel(808306538401759252).send(embed=SEmbed("あまぼっちアラート！！！", f"Amachiさんが{chname}であまぼっち中です。**暖かく**見守ってあげましょう。", color=0xe91e63))
            else:
                await self.bot.get_channel(808306538401759252).send(embed=SEmbed(None, f"{member.mention}さんが{chname}で寂しそうにしています...", color=0xf1c40f))


def setup(bot):
    bot.add_cog(MainCog(bot))
