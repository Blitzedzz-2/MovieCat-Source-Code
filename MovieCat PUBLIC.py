import discord
from discord.ext import commands
import aiohttp
import logging
import asyncio
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

categories = {
    "hollywood": "http://103.87.212.46/Data/movies1/hollywood/", #These are links for movies yay
    "bollywood": "http://103.87.212.46/Data/movies1/bollywood/",
    "animated": "http://103.87.212.46/Data/movies1/animation/",
}

async def download_and_stream(ctx, url, voice_client): # Download and stream stuff lmao
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    voice_client.play(discord.FFmpegPCMAudio(url), after=lambda e: logger.info(f"Stream finished: {e}"))
                    await ctx.send("Streaming in progress...")
                    while voice_client.is_playing():
                        await asyncio.sleep(1)
                    logger.info(f"Streaming complete!")
                else:
                    logger.error(f"Failed to fetch the file. Status code: {response.status}")
                    await ctx.send("Failed to fetch the file.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await ctx.send("An error occurred while streaming the movie.")

async def stream_movie(ctx, file_url):
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send("You need to join a voice channel first!")
        return

    voice_client = await voice_channel.connect()
    await download_and_stream(ctx, file_url, voice_client)
    await voice_client.disconnect()

@bot.command()
async def start(ctx):
    await ctx.send("Welcome! Please select a category: Hollywood, Bollywood, Animated")

    def check(message):
        return message.author == ctx.author and message.content.lower() in categories

    category_message = await bot.wait_for('message', check=check)
    category = category_message.content.lower()
    category_url = categories[category]

    if category == "IPTV":
        await iptv(ctx)
        return

    await ctx.send(f"Please select a timeframe: 2000-2010, 2011-2020, 2021, 2022, 2023, or 2024.")
    def check_timeframe(message):
        return message.author == ctx.author and message.content.lower() in ['2000-2010', '2011-2020', '2021', '2022', '2023', '2024']

    timeframe_message = await bot.wait_for('message', check=check_timeframe)
    timeframe = timeframe_message.content.lower()

    await ctx.send("Please enter the name of the movie:")
    def check_movie(message):
        return message.author == ctx.author and message.channel == ctx.channel

    movie_message = await bot.wait_for('message', check=check_movie)
    movie_name = movie_message.content

    parent_url = f"{category_url}{timeframe}/"
    async with aiohttp.ClientSession() as session:
        async with session.get(parent_url) as response:
            if response.status == 200:
                html_content = await response.text()
                movie_folder = [
                    line.split('"')[1]
                    for line in html_content.splitlines()
                    if movie_name.lower() in line.lower() and 'href="' in line
                ]

                if movie_folder:
                    movie_folder_url = urljoin(parent_url, movie_folder[0])
                    async with session.get(movie_folder_url) as folder_response:
                        if folder_response.status == 200:
                            folder_html = await folder_response.text()
                            video_files = [
                                line.split('"')[1]
                                for line in folder_html.splitlines()
                                if any(ext in line.lower() for ext in ['.mkv', '.mp4', '.avi'])
                                and 'href="' in line
                            ]
                            if video_files:
                                file_url = urljoin(movie_folder_url, video_files[0])
                                await ctx.send("Streaming the movie. Please wait!")
                                await stream_movie(ctx, file_url)
                            else:
                                await ctx.send("No video file found in the movie folder.")
                        else:
                            await ctx.send("Failed to access the movie folder.")
                else:
                    await ctx.send("Movie folder not found.")
            else:
                await ctx.send("Failed to access the parent URL.")

@bot.command()
async def iptv(ctx, *, channel_name=None):
    await ctx.send("Welcome to IPTV! Fetching available American channels, please wait...")

    m3u_url = "https://iptv-org.github.io/iptv/countries/us.m3u"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(m3u_url) as response:
                if response.status == 200:
                    playlist_content = await response.text()
                    playlist_lines = playlist_content.splitlines()
                    channels = []

                    for i in range(len(playlist_lines)):
                        if playlist_lines[i].startswith("#EXTINF"):
                            name = playlist_lines[i].split(",")[-1]
                            url = playlist_lines[i + 1]
                            channels.append((name, url))

                    if not channels:
                        await ctx.send("No channels found in the playlist.")
                        return

                    if channel_name:
                        matched_channels = [ch for ch in channels if channel_name.lower() in ch[0].lower()]
                        if not matched_channels:
                            await ctx.send(f"No channels found matching '{channel_name}'.")
                            return

                        if len(matched_channels) > 1:
                            options = "\n".join([f"{i + 1}. {name}" for i, (name, _) in enumerate(matched_channels)])
                            await ctx.send(f"Multiple matches found for '{channel_name}':\n{options}\nEnter the number of the channel to watch:")

                            def check_selection(message):
                                return (
                                    message.author == ctx.author
                                    and message.content.isdigit()
                                    and 1 <= int(message.content) <= len(matched_channels)
                                )

                            selection_msg = await bot.wait_for("message", check=check_selection)
                            selected_index = int(selection_msg.content) - 1
                        else:
                            selected_index = 0

                        selected_channel = matched_channels[selected_index]
                        channel_name, channel_url = selected_channel
                        await ctx.send(f"Tuning in to {channel_name}. Please wait...")

                        await stream_channel(ctx, channel_url)
                        return

                    items_per_page = 10
                    total_pages = (len(channels) + items_per_page - 1) // items_per_page
                    current_page = 0

                    def get_page_content(page):
                        start_idx = page * items_per_page
                        end_idx = start_idx + items_per_page
                        page_channels = channels[start_idx:end_idx]
                        return "\n".join([f"{idx + 1}. {name}" for idx, (name, _) in enumerate(page_channels, start=start_idx)])

                    msg = await ctx.send(f"Available American Channels (Page {current_page + 1}/{total_pages}):\n{get_page_content(current_page)}")
                    await msg.add_reaction("\u25c0")
                    await msg.add_reaction("\u25b6")

                    def check_reaction(reaction, user):
                        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["\u25c0", "\u25b6"]

                    while True:
                        try:
                            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)
                            if str(reaction.emoji) == "\u25b6" and current_page < total_pages - 1:
                                current_page += 1
                            elif str(reaction.emoji) == "\u25c0" and current_page > 0:
                                current_page -= 1
                            else:
                                await msg.remove_reaction(reaction.emoji, user)
                                continue

                            await msg.edit(content=f"Available American Channels (Page {current_page + 1}/{total_pages}):\n{get_page_content(current_page)}")
                            await msg.remove_reaction(reaction.emoji, user)

                        except asyncio.TimeoutError:
                            await msg.clear_reactions()
                            break
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await ctx.send("An error occurred while fetching or streaming the channels.")

async def stream_channel(ctx, channel_url): # IPTV stuff yay
    try:
        voice_channel = ctx.author.voice.channel
        if not voice_channel:
            await ctx.send("You need to join a voice channel first!")
            return

        voice_client = await voice_channel.connect()
        voice_client.play(discord.FFmpegPCMAudio(channel_url), after=lambda e: logger.info(f"Stream finished: {e}"))

        while voice_client.is_playing():
            await asyncio.sleep(1)

        await voice_client.disconnect()

    except Exception as e:
        logger.error(f"Error streaming channel: {e}")
        await ctx.send("An error occurred while streaming the channel.")

bot.run('TOKEN HERE')
