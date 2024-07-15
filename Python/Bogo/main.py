import os
import discord
import logging
import colorlog
import asyncio
from discord.ext import commands, tasks
from openai import OpenAI
from rich import print

# Get Discord bot token and OpenAI API key from environment variable
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOGO_CHANNEL_ID = 1262153225671282779
GPT_MODEL = "gpt-3.5-turbo"
MAX_REQUESTS = 5
MINUTE = 60
PEOPLE_IN_VOICE = []

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
            print("Making request to OpenAI")
            self.request_count += 1
        else:
            print("Rate limit reached. Waiting 1 minute.")
            await asyncio.sleep(MINUTE)
            self.request_count = 0
            print("Rate limit reset. Resuming requests.")


limiter = RateLimiter()

############################################################################################################
#                                               FUNCTIONS                                                  #
############################################################################################################


# Save chat_history list to a file every 5 minutes as a backup
async def backup_chat_history():
    while True:
        await asyncio.sleep(5 * MINUTE)
        with open("chat_history.txt", "w") as file:
            file.write(str(chat_history))
            logger.warning("Chat history backed up to file.")


# Load chat_history.txt file if it exists and append it to chat_history list
async def load_chat_history():
    if os.path.exists("chat_history.txt"):
        with open("chat_history.txt", "r") as file:
            chat_history.extend(eval(file.read()))
            chat_history.pop(0)
            logger.info("Loaded chat history from file.")
    else:
        logger.warning("No chat history backup found. Starting fresh..")


# Sets the personality for the bot each time it is booted up, ensuring maximum Bogo
FIRST_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
You are Bogo, a fun lovable goofy alien who helps out the users of my discord server

While responding as Bogo, you must obey the following rules:
1) Provide short responses, about 1-2 paragraphs.
2) Always stay in character, no matter what.
3) Occasionally mention that the government is after your organs.
4) Keep your answers limited to just a few sentences.
5) Occasionally include random fun facts in your responses that are never true but do not mention that they are not true.
6) You have 3 toes on each foot, and 16 fingers on each hand.
7) You refer to everyone by a completely random human name.
8) You are overly concerned about other peoples health and hygine, but you only occasionally mention it in a disgusted way.
9) You will sometimes mention how penguins are the best animals to have ever existed.
10) If anyone ever asks if you got your photos printed you MUST respond with 'Bogos Binted' and absolutely nothing else.
11) If anyone responds to your message saying 'Bogos Binted' with the message 'huh' you MUST respond with an alien emoji and absolutely nothing else. Only do this if your previous message was 'Bogos Binted'.
12) You frequently swear but they are all made up swear words

Okay, let the conversation begin!
""",
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
    await backup_chat_history()


@bot.command()
async def bogo(ctx, *, question):
    # Check rate limit before making request
    logger.warning("Checking rate limit...")
    await limiter.make_request()
    # logs question to terminal
    logger.debug(f"{ctx.author}: {question}")
    # Appends question to chat history
    chat_history.append({"role": "user", "content": question})

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
