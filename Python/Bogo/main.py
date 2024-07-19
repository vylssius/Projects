import os
import re
import discord
import logging
import colorlog
import asyncio
import yt_dlp as youtube_dl

from discord.ext import commands
from discord import FFmpegPCMAudio
from openai import OpenAI
from eleven_labs import ElevenLabsManager


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


clear_console()

# Get Discord bot token and OpenAI API key from environment variable
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOGO_CHANNEL_ID = 1262153225671282779
GPT_MODEL = "gpt-3.5-turbo"
MAX_REQUESTS = 10
MINUTE = 60
BOT_PERSONALITY = "Bogo"
ELEVENLABS_VOICE = "Bogo"
PERSONALITY_PATH = "Personalities/" + BOT_PERSONALITY + ".txt"
VOLUME_LEVEL = 0.35 / 2
MAX_VIDEO_DURATION_SECONDS = 30 * 60

is_speech_worker_active = False
is_text_worker_active = False
is_youtube_worker_active = False

bogospeak_queue = asyncio.Queue()
bogotext_queue = asyncio.Queue()
bogoyoutube_queue = asyncio.Queue()

if DISCORD_BOT_TOKEN is None:
    raise ValueError(
        "No token found. Please set the DISCORD_BOT_TOKEN environment variable."
    )

if OPENAI_API_KEY is None:
    raise ValueError(
        "No API key found. Please set the OPENAI_API_KEY environment variable."
    )

# Set OpenAI api key
client = OpenAI(api_key=OPENAI_API_KEY)

# Eleven Labs Manager
elevenlabs_manager = ElevenLabsManager()

# Ensures the bot has a "Brain" and remembers previous chat history
chat_history = []

# Sets up console logging for conversations
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.DEBUG)

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(message)s",
        log_colors={
            "DEBUG": "purple",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
)

logger.addHandler(handler)


# Rate limiter to prevent exceeding the OpenAI API rate limit
class RateLimiter:
    def __init__(self):
        self.request_count = 0
        self.rate_limit_message_sent = False

    async def make_request(self, ctx):
        if self.request_count < MAX_REQUESTS:
            logger.warning("Making request to OpenAI")
            self.request_count += 1
            self.rate_limit_message_sent = False
        else:
            if not self.rate_limit_message_sent:
                await ctx.send(
                    "Woah, that's a lot of questions! Give me a minute to catch up."
                )
                self.rate_limit_message_sent = True
            logger.warning("Rate limit reached. Waiting 1 minute.")
            await asyncio.sleep(MINUTE)
            self.request_count = 0
            logger.warning("Rate limit reset. Resuming requests.")


limiter = RateLimiter()

############################################################################################################
#                                               FUNCTIONS                                                  #
############################################################################################################


# Save chat_history list to a file every 5 minutes as a backup
async def backup_chat_history():
    while True:
        with open("chat_history.txt", "w") as file:
            file.write(str(chat_history))
        await asyncio.sleep(1)


# Load chat_history.txt file if it exists and append it to chat_history list
async def load_chat_history():
    if os.path.exists("chat_history.txt"):
        with open("chat_history.txt", "r") as file:
            chat_history.extend(eval(file.read()))
            chat_history.pop(0)
            logger.info("Loaded chat history from file.")
    else:
        logger.warning("No chat history backup found. Starting fresh..")


def is_url(string):
    return re.match(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        string,
    )


async def search_youtube(search_query):
    ydl_opt = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "auto",
    }
    with youtube_dl.YoutubeDL(ydl_opt) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{search_query}", download=False)
            if "entries" in info:
                video_info = info["entries"][0]
                return video_info["webpage_url"], video_info["title"]
        except Exception as e:
            logger.critical(f"Error searching Youtube: {e}")
            return None, None


with open(PERSONALITY_PATH, "r") as file:
    PERSONALITY = file.read()

# Sets the personality for the bot each time it is booted up
FIRST_SYSTEM_MESSAGE = {
    "role": "system",
    "content": PERSONALITY,
}
chat_history.append(FIRST_SYSTEM_MESSAGE)

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.dm_messages = True
intents.members = True
intents.voice_states = True

# Set up the bot with the appropriate command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)


############################################################################################################
#                                               BOT COMMANDS                                               #
############################################################################################################


@bot.event
async def on_ready():
    logger.info("Bogo logged in")
    await load_chat_history()
    logger.debug("\n" + PERSONALITY + "\n")
    await backup_chat_history()


@bot.command()
async def bogotext(ctx, *, question):
    # Add request to the queue
    await bogotext_queue.put((ctx, question))
    logger.warning(f"Added to queue: {question}")

    global is_text_worker_active
    # Start processing the queue if the worker is not active
    if not is_text_worker_active:
        is_text_worker_active = True
        await process_bogotext_queue()


async def process_bogotext_queue():
    global is_text_worker_active
    while not bogotext_queue.empty():
        ctx, question = await bogotext_queue.get()
        logger.warning(f"Processing from queue: {question}")
        try:
            # Check rate limit before making request
            await limiter.make_request(ctx)

            # logs question to terminal
            logger.debug(f"{ctx.author}: {question}")

            # Process the question
            chat_history.append(
                {"role": "user", "content": f"{ctx.author.name}: {question}"}
            )
            response = client.chat.completions.create(
                model=GPT_MODEL, messages=chat_history
            )
            chat_history.append(
                {
                    "role": response.choices[0].message.role,
                    "content": response.choices[0].message.content,
                }
            )
            answer = response.choices[0].message.content
            logger.debug(f"Bogo: {answer}")
            await ctx.send(f"{ctx.author.mention} {answer}")
        except Exception as e:
            logger.critical(f"Error in queue processing: {e}")
            await ctx.send(f"An error occurred: {e}")
        finally:
            bogotext_queue.task_done()
            logger.warning(
                "Finished processing and marked the queue task as done.")
    is_text_worker_active = False
    logger.warning("Queue is empty, marking text worker as inactive.")


@bot.command()
async def bogoyoutube(ctx, *, query: str):
    url, title = None, None
    if is_url(query):
        url = query
    else:
        url, title = await search_youtube(query)

    if not url:
        await ctx.send("Could not find a video matching your query.")
        return

    # Add request to the queue
    await bogoyoutube_queue.put((ctx, url))
    logger.warning(f"Added to queue: {url}")

    while is_speech_worker_active:
        await asyncio.sleep(1)

    global is_youtube_worker_active
    # Start processing the queue if the worker is not active
    if not is_youtube_worker_active:
        is_youtube_worker_active = True
        await process_bogoyoutube_queue()


async def process_bogoyoutube_queue():
    global is_youtube_worker_active
    while not bogoyoutube_queue.empty():
        ctx, url = await bogoyoutube_queue.get()
        logger.warning(f"Processing from queue: {url}")
        try:
            if ctx.author.voice and ctx.author.voice.channel:
                logger.warning(
                    f"{ctx.author} is in a voice channel, proceeding...")
                channel = ctx.author.voice.channel
                voice_client = ctx.guild.voice_client

                if voice_client:
                    # already in voice channel
                    if voice_client.channel != channel:
                        await voice_client.disconnect()
                        voice_client = await channel.connect()
                else:
                    try:
                        ydl_opts = {
                            "format": "bestaudio/best",
                            "postprocessors": [
                                {
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3",
                                    "preferredquality": "192",
                                }
                            ],
                            "outtmpl": "%(title)s.%(ext)s",
                        }

                        def transform(volume):
                            def volume_transformer(data, volume=volume):
                                return

                            return volume_transformer

                        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                            info_dict = ydl.extract_info(url, download=False)
                            video_title = info_dict.get("title", None)
                            filename = f"{video_title}.mp3"
                            await ctx.send(f"Now loading: {video_title}")

                            # Check if Embedding is disabled
                            if not info_dict.get("url", None):
                                raise Exception(
                                    "Embedding is disabled for this video.")

                            # ydl.download([url])
                            await asyncio.to_thread(ydl.download, [url])

                        if not voice_client.is_connected():
                            voice_client = await channel.connect()

                        logger.warning("Joining voice channel...")
                        voice_client = await channel.connect()

                        voice_client.play(discord.FFmpegPCMAudio(filename))

                        if voice_client.is_playing():
                            # Adjust volume in real time
                            voice_client.source = discord.PCMVolumeTransformer(
                                voice_client.source, volume=VOLUME_LEVEL
                            )

                        while voice_client.is_playing():
                            await asyncio.sleep(1)

                        # Remove the file asynchronously
                        await asyncio.to_thread(os.remove, filename)

                        await voice_client.disconnect()

                    except youtube_dl.utils.ExtractorError as e:
                        logger.critical(f"Extractor Error: {e}")
                        await ctx.send(
                            "Embedding is disabled for that video. "
                            "Please try another video."
                        )

                    except youtube_dl.utils.DownloadError as e:
                        logger.critical(f"Download Error: {e}")
                        await ctx.send(
                            f"An error occurred with the requested video: {e}"
                        )

                    except Exception as e:
                        logger.critical(f"Error in processing: {e}")
                        await ctx.send(f"An error occurred: {e}")

            else:
                await ctx.send("You need to be in a voice chat to do that!")
        except Exception as e:
            logger.critical(f"Error in queue processing: {e}")
            await ctx.send(f"An error occurred: {e}")
        finally:
            bogoyoutube_queue.task_done()
            logger.warning(
                "Finished processing and marked the queue task as done.")
    is_youtube_worker_active = False
    logger.warning("Queue is empty, marking youtube worker as inactive.")


@bot.command()
async def bogoskip(ctx):
    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_playing() and not is_speech_worker_active:
        voice_client.stop()
        await ctx.send("Skipping current video.")
    else:
        await ctx.send("No song is currently playing.")


@bot.command()
async def bogospeak(ctx, *, speechquestion):
    # Add request to the queue
    await bogospeak_queue.put((ctx, speechquestion))
    logger.warning(f"Added to queue: {speechquestion}")

    while is_youtube_worker_active:
        await asyncio.sleep(1)

    global is_speech_worker_active
    # Start processing the queue if the worker is not active
    if not is_speech_worker_active:
        is_speech_worker_active = True
        await process_bogospeak_queue()


async def process_bogospeak_queue():
    global is_speech_worker_active
    while not bogospeak_queue.empty():
        ctx, speechquestion = await bogospeak_queue.get()
        logger.warning(f"Processing from queue: {speechquestion}")
        try:
            if ctx.author.voice and ctx.author.voice.channel:
                logger.warning(
                    f"{ctx.author} is in a voice channel, proceeding...")
                channel = ctx.author.voice.channel
                voice_client = ctx.guild.voice_client

                # Check rate limit before making request
                logger.warning("Checking rate limit...")
                await limiter.make_request(ctx)

                if voice_client:
                    # already in voice channel
                    if voice_client.channel != channel:
                        await voice_client.disconnect()
                else:
                    # logs question to terminal
                    logger.debug(f"{ctx.author}: {speechquestion}")

                    try:
                        # Appends question to chat history
                        chat_history.append(
                            {
                                "role": "user",
                                "content": ctx.author.name + ": " + speechquestion,
                            },
                        )
                        speechresponse = client.chat.completions.create(
                            model=GPT_MODEL,
                            messages=chat_history,
                        )
                        chat_history.append(
                            {
                                "role": speechresponse.choices[0].message.role,
                                "content": speechresponse.choices[0].message.content,
                            }
                        )

                        speechanswer = speechresponse.choices[0].message.content
                        logger.debug(f"Bogo: {speechanswer}")

                        elevenlabs_output = elevenlabs_manager.text_to_audio(
                            speechanswer, ELEVENLABS_VOICE, False
                        )
                        audio_source = discord.FFmpegPCMAudio(
                            elevenlabs_output)
                        logger.warning("Joining voice channel...")
                        voice_client_bot = await channel.connect()
                        voice_client_bot.play(audio_source)

                        while voice_client_bot.is_playing():
                            await asyncio.sleep(1)

                        await voice_client_bot.disconnect()

                        os.remove(elevenlabs_output)

                    except Exception as e:
                        logger.critical(f"Error: {e}")
                        await ctx.send(f"An error occurred: {e}")
            else:
                await ctx.send("You need to be in a voice chat to speak to me!")
        except Exception as e:
            logger.critical(f"Error in queue processing: {e}")
            await ctx.send(f"An error occurred: {e}")
        finally:
            bogospeak_queue.task_done()
            logger.warning(
                "Finished processing and marked the queue task as done.")
    is_speech_worker_active = False
    logger.warning("Queue is empty, marking speech worker as inactive.")


@bot.event
async def on_message(message):
    if message.channel.id != BOGO_CHANNEL_ID:
        return
    await bot.process_commands(message)


# Run the bot with the token
bot.run(DISCORD_BOT_TOKEN)
