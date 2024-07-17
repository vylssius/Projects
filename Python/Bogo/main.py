import os
import discord
import logging
import colorlog
import asyncio

from discord.ext import commands
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
MAX_REQUESTS = 5
MINUTE = 60
RATE_LIMITED = False
is_speech_worker_active = False
is_text_worker_active = False

BOT_PERSONALITY = "BogoSmart"
ELEVENLABS_VOICE = "Bogo"
PERSONALITY_PATH = "Personalities/" + BOT_PERSONALITY + ".txt"

bogospeak_queue = asyncio.Queue()
bogotext_queue = asyncio.Queue()

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
async def bogospeak(ctx, *, speechquestion):
    # Add request to the queue
    await bogospeak_queue.put((ctx, speechquestion))
    logger.warning(f"Added to queue: {speechquestion}")

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
                    # not in voice channel
                    logger.warning("Joining voice channel...")

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
