from gtts import gTTS
from pathlib import Path

# Define your text
text = """
        Good afternoon. I’m going to check your blood pressure now.
        I’ll start by taking it while you're seated. I’ll use your left arm for this.
        Please relax for a moment while I take the reading.
        Your blood pressure is 130 over 85.
        I’ll make a note of that. If there’s anything else, feel free to mention it later.
        """

# Initialize gTTS with your text and language (e.g., 'en' for English)
tts = gTTS(text=text, lang='en')

# Define the file path to save the audio
speech_file_path = Path(__file__).parent / "blood_pressure.mp3"

# Save the speech to a file
tts.save(speech_file_path)

print(f"Speech saved to {speech_file_path}")


# import openai
# from pathlib import Path

# # Define the file path
# speech_file_path = Path(__file__).parent / "speech.mp3"

# # Call the OpenAI API to generate the speech
# response = openai.Audio.create(
#     model="tts-1",
#     voice="alloy",
#     input="""
#         Let’s begin with your admission process.
#         I’m noting down the admission details, and I’ll write some admission notes here. You were transported by ambulance and accompanied by your son. Your primary diagnosis is hypertension, and your admission date is today, at 14:00.
#         Now, I’ll check your vitals. Your temperature is 98.6°F, your pulse is 72 beats per minute, and your respiration rate is 16 breaths per minute. Your blood pressure is 130/85. Your weight is 150 pounds, and your height is 65 inches. I’ll note that you don't have any known allergies, and your oxygen saturation is 98%.
#         Moving on to your skin condition, I’ll document that you have no visible skin issues at the moment.
#         Next, I’ll check your physical and communication status. Your respiratory rate remains steady at 16 breaths per minute. There are no signs of paralysis or contractures. I see that you wear glasses, and you’re independent with your transfers and bed mobility. You’re also able to ambulate independently without a device. You can bear full weight on both legs.
#         You don't use any supportive devices like elastic hose or an air mattress, and you don’t require traction.
#         Regarding your sensory abilities, your hearing is adequate in both ears without the need for aids, and your vision is fine with glasses in both eyes.
#         I’ll also document that you have your own teeth and don’t wear dentures. I see no significant oral issues.
#         When it comes to your daily activities, you’re independent in eating, personal hygiene, and dressing. You’re also independent with showers and other hygiene tasks.
#         For communication, your speech is clear, and you primarily speak English. Your comprehension is quick, and you answer questions readily.
#         I’m documenting that you don’t have any issues with bowel or bladder habits. You’re continent and don’t use any bowel or bladder devices. No laxatives or ostomies are needed, and you don’t use a catheter.
#         For your psychosocial status, I’ll note that you have a close relationship with your family, and you seem cooperative and friendly. You’re motivated for rehabilitation, and you don’t smoke or use alcohol.
#         Finally, for your orientation to the facility, I’ll explain the layout of the facility, the call light system, and our schedule. I’ll also mention the rules regarding meals and visiting hours.
#         """
# )

# # Stream the output to the file
# with open(speech_file_path, "wb") as f:
#     f.write(response['audio_data'])





# from pathlib import Path
# import openai
# client = OpenAI()

# speech_file_path = Path(__file__).parent / "speech.mp3"
# response = client.audio.speech.create(
#   model="tts-1",
#   voice="alloy",
#   input="""
#         Let’s begin with your admission process.
#         I’m noting down the admission details, and I’ll write some admission notes here. You were transported by ambulance and accompanied by your son. Your primary diagnosis is hypertension, and your admission date is today, at 14:00.
#         Now, I’ll check your vitals. Your temperature is 98.6°F, your pulse is 72 beats per minute, and your respiration rate is 16 breaths per minute. Your blood pressure is 130/85. Your weight is 150 pounds, and your height is 65 inches. I’ll note that you don't have any known allergies, and your oxygen saturation is 98%.
#         Moving on to your skin condition, I’ll document that you have no visible skin issues at the moment.
#         Next, I’ll check your physical and communication status. Your respiratory rate remains steady at 16 breaths per minute. There are no signs of paralysis or contractures. I see that you wear glasses, and you’re independent with your transfers and bed mobility. You’re also able to ambulate independently without a device. You can bear full weight on both legs.
#         You don't use any supportive devices like elastic hose or an air mattress, and you don’t require traction.
#         Regarding your sensory abilities, your hearing is adequate in both ears without the need for aids, and your vision is fine with glasses in both eyes.
#         I’ll also document that you have your own teeth and don’t wear dentures. I see no significant oral issues.
#         When it comes to your daily activities, you’re independent in eating, personal hygiene, and dressing. You’re also independent with showers and other hygiene tasks.
#         For communication, your speech is clear, and you primarily speak English. Your comprehension is quick, and you answer questions readily.
#         I’m documenting that you don’t have any issues with bowel or bladder habits. You’re continent and don’t use any bowel or bladder devices. No laxatives or ostomies are needed, and you don’t use a catheter.
#         For your psychosocial status, I’ll note that you have a close relationship with your family, and you seem cooperative and friendly. You’re motivated for rehabilitation, and you don’t smoke or use alcohol.
#         Finally, for your orientation to the facility, I’ll explain the layout of the facility, the call light system, and our schedule. I’ll also mention the rules regarding meals and visiting hours.
#         """
# )

# response.stream_to_file(speech_file_path)