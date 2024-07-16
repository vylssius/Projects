import os
import discord
import logging
import colorlog
import asyncio
from discord.ext import commands, tasks
from openai import OpenAI
from rich import print


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
PEOPLE_IN_VOICE = []

BOT_PERSONALITY = "BogoSmart"
PERSONALITY_PATH = "Personalities/" + BOT_PERSONALITY + ".txt"


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

    async def make_request(self):
        if self.request_count < MAX_REQUESTS:
            logger.warning("Making request to OpenAI")
            self.request_count += 1
        else:
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
        await asyncio.sleep(MINUTE)


# Load chat_history.txt file if it exists and append it to chat_history list
async def load_chat_history():
    if os.path.exists("chat_history.txt"):
        with open("chat_history.txt", "r") as file:
            chat_history.extend(eval(file.read()))
            logger.info("Loaded chat history from file.")
    else:
        logger.warning("No chat history backup found. Starting fresh..")


with open(PERSONALITY_PATH, "r") as file:
    PERSONALITY = file.read()

# Sets the personality for the bot each time it is booted up, ensuring maximum Bogo
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

# Set up the bot with the appropriate command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)


############################################################################################################
#                                               BOT COMMANDS                                               #
############################################################################################################


@tasks.loop(seconds=1)
async def check_voice_channels():
    for guild in bot.guilds:
        for member in guild.members:
            if member.voice and member.voice.channel:
                if member.name not in PEOPLE_IN_VOICE:
                    PEOPLE_IN_VOICE.append(member.name)
                # Check to see if a member that has been logged in the list has left the voice channel, if so remove them from the list
                for person in PEOPLE_IN_VOICE:
                    if person not in [
                        member.name
                        for member in member.voice.channel.members  # type: ignore
                    ]:
                        PEOPLE_IN_VOICE.remove(person)


@bot.event
async def on_ready():
    logger.info("Bogo logged in")
    check_voice_channels.start()
    await load_chat_history()
    logger.debug("\n" + PERSONALITY + "\n")
    await backup_chat_history()


@bot.command()
async def bogo(ctx, *, question):
    # Check rate limit before making request
    logger.warning("Checking rate limit...")
    await limiter.make_request()
    # logs question to terminal
    logger.debug(f"{ctx.author}: {question}")
    # Appends question to chat history
    chat_history.append({"role": "user", "content": ctx.author.name + ": " + question})

    try:
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=chat_history,
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
        logger.critical(f"Error: {e}")
        await ctx.send(f"An error occurred: {e}")


@bot.event
async def on_message(message):
    if message.channel.id != BOGO_CHANNEL_ID:
        return
    await bot.process_commands(message)


# Run the bot with the token
bot.run(DISCORD_BOT_TOKEN)
