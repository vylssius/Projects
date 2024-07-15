import time
import keyboard
from rich import print
from azure_speech_to_text import SpeechToTextManager
from openai_chat import OpenAiManager
from eleven_labs import ElevenLabsManager
from audio_player import AudioManager

CHARACTER_NAME = "CowboyBob"

ELEVENLABS_VOICE = CHARACTER_NAME  # Replace this with the name of whatever voice you have created on Elevenlabs

BACKUP_FILE = "ChatHistoryBackup.txt"
PERSONALITY_FILE_PATH = "Personalities/" + CHARACTER_NAME + ".txt"

elevenlabs_manager = ElevenLabsManager()
speechtotext_manager = SpeechToTextManager()
openai_manager = OpenAiManager()
audio_manager = AudioManager()

with open(PERSONALITY_FILE_PATH, "r") as file:
    PERSONALITY = file.read()

FIRST_SYSTEM_MESSAGE = {
    "role": "system",
    "content": PERSONALITY,
}
openai_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)

print("[green]Starting the loop, press F4 to begin")
while True:
    # Wait until user presses "f4" key
    if keyboard.read_key() != "f4":
        time.sleep(0.1)
        if keyboard.read_key() == "end":
            break
        continue

    print("[green]User pressed F4 key! Now listening to your microphone:")

    # Get question from mic
    mic_result = speechtotext_manager.speechtotext_from_mic_continuous()

    if mic_result == "":
        print("[red]Did not receive any input from your microphone!")
        continue

    # Send question to OpenAi
    openai_result = openai_manager.chat_with_history(mic_result)

    # Write the results to txt file as a backup
    with open(BACKUP_FILE, "w") as file:
        file.write(str(openai_manager.chat_history))

    # Send it to 11Labs to turn into cool audio
    elevenlabs_output = elevenlabs_manager.text_to_audio(
        openai_result, ELEVENLABS_VOICE, False
    )

    # Enable the picture of Pajama Sam in OBS
    # obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Pajama Sam", True)

    # Play the mp3 file
    audio_manager.play_audio(elevenlabs_output, True, True, True)

    # Disable Pajama Sam pic in OBS
    # obswebsockets_manager.set_source_visibility("*** Mid Monitor", "Pajama Sam", False)

    print(
        "[green]\n!!!!!!!\nFINISHED PROCESSING DIALOGUE.\nREADY FOR NEXT INPUT\n!!!!!!!\n"
    )
