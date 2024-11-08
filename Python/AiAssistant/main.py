import os
from rich import print
from openai import OpenAI

os.system("cls" if os.name == "nt" else "clear")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CHAT_HISTORY = []
GPT_MODEL = "gpt-3.5-turbo"

# Create a first system message that describes the context of the conversation
FIRST_SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a helpful AI assistant, you will help answer any questions that the user has. Format all your responses to be readable within a terminal window.",
}

CHAT_HISTORY.append(FIRST_SYSTEM_MESSAGE)

while True:
    prompt = input("You: ")
    CHAT_HISTORY.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=GPT_MODEL, messages=CHAT_HISTORY)

    AI_response = response.choices[0].message.content
    print(f"[green]AI: {AI_response}")

    CHAT_HISTORY.append(
        {
            "role": response.choices[0].message.role,
            "content": AI_response,
        }
    )

    # Check if user prompt includes the word "bye" to end the conversation
    if "bye" in prompt:
        break
