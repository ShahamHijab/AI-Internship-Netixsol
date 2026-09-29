import asyncio

from app.voice import text_to_speech


async def main():

    audio = await text_to_speech(
        "Assalam-o-Alaikum! Main Ahmed hoon. "
        "Aap kis type ki property dhoond rahe hain?"
    )

    with open("test_fish.mp3", "wb") as f:
        f.write(audio)

    print("Created test_fish.mp3")
    print("Audio bytes:", len(audio))


asyncio.run(main())