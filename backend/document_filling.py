import json
import os
import openai
from stt import transcribe_audio
from speakcare_emr_utils import EmrUtils
from speakcare_emr import SpeakCareEmr
from speakcare_logging import create_logger
from speakcare_emr_utils import EmrUtils

openai.api_key = os.getenv("OPENAI_API_KEY")

from dotenv import load_dotenv
import os
import re

def fill_schema_with_transcription_as_dict(transcription, schema):
    """
    Fills a schema based on the conversation transcription, returning a dictionary.
    The dictionary contains field names as keys and the corresponding filled values as values,
    with each value cast to the appropriate type based on the schema definition.
    If the value is "no answer", the field is omitted from the final dictionary.
    
    Parameters:
        transcription (str): The conversation transcription.
        schema (JSON): The JSON schema template to fill.
        
    Returns:
        dict: Dictionary of the filled schema
    """

    prompt = f"""
    You are given a transcription of a conversation related to a nurse's treatment of a patient. 
    Based on the transcription, fill in the following fields as dictionary if you are sure of the answers.
    If you are unsure of any field, please respond with "no answer".
    
    Transcription: {transcription}
    
    Schema template:
    {json.dumps(schema, indent=2)}
    
    Return a dictionary by filling in only the fields you are sure about. 
    Return a dictionary of field name and value, making sure the values are cast as per their correct type (number, text, etc.).
    If uncertain, use "no answer" as the value.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert in parsing medical transcription and filling treatment forms."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )

    filled_schema_str = response.choices[0].message.content.strip()

    # print(filled_schema_str)

    cleaned_filled_schema_str = re.sub(r'```json|```', '', filled_schema_str).strip()

    try:
        filled_schema_dict = json.loads(cleaned_filled_schema_str)
        return filled_schema_dict
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return {}

if __name__ == "__main__":


    transcriptions = [
        # # 1. Complete Information
        # """
        # The nurse measured the patient's weight using a standing scale. 
        # The weight recorded was 160.2 pounds. The patient prefers to use imperial units.
        # """,

        # # 2. Missing Weight
        # """
        # The nurse used a mechanical lift to weigh the patient. 
        # The patient requested the weight to be recorded in kilograms. 
        # However, the scale was not working correctly, and no weight could be recorded.
        # """,

        # # 3. Missing Unit Type
        # """
        # The nurse weighed the patient using a bed scale, 
        # and the weight was recorded as 73.5. The patient was cooperative throughout the process.
        # """

        # # 4. Complete Information
        # """
        # During the nurse’s visit, the patient was weighed using a sitting scale. 
        # The recorded weight was 180.6 pounds. The patient expressed a preference for pounds over kilograms.
        # """,

        # # 5. Missing Scale Type
        # """
        # The patient's weight was measured as 55.4 kilograms during the evening shift. 
        # """,

        # # 6. Missing Scale and Unit
        # """
        # The nurse documented the patient’s weight during a routine check-up. 
        # Unfortunately, the exact scale and unit were not recorded, but the weight was noted as 68.9.
        # """,

        # # 7. Complete Information
        # """
        # The nurse weighed the patient using a wheelchair scale, 
        # and the recorded weight was 145.2 pounds. The patient requested to continue using pounds as the preferred unit.
        # """,

        # # 8. Missing Weight and Unit
        # """
        # The patient was weighed using a bath scale, but due to a discrepancy with the scale's calibration, 
        # no accurate weight was recorded. The nurse plans to weigh the patient again the next day.
        # """,

        # # 9. Complete Information
        # """
        # The nurse used a mechanical lift to weigh the patient, 
        # and the weight was documented as 120.4 kilograms. The patient was unable to stand and requested the weight in kilograms.
        # """,

        # # 10. Missing Unit
        # """
        # The nurse used a bed scale to measure the patient's weight, 
        # which was recorded as 154.6. However, the unit (kilograms or pounds) was not noted in the record.
        # """

        # 11. Blood presure
        """
        Good afternoon. I’m going to check your blood pressure now.
        I’ll start by taking it while you're seated. I’ll use your left arm for this.
        Please relax for a moment while I take the reading.
        Your blood pressure is 130 over 85. That’s 130 systolic and 85 diastolic.
        I’ll make a note of that. If there’s anything else, feel free to mention it later.
        """


        # 12. Admission
        # """
        # Good afternoon, Mr. Smith. I see you’re feeling a little weak today but managing. I’m here to go over some information for your admission form, and I’ll start by gathering a few details. You were transported here by ambulance, and your wife accompanied you. I’ll note that.
        # Now, let’s review your diagnoses. You’ve shared that you have diabetes and high blood pressure. I’ll record that in your chart, and today’s admission date is September 22, 2024.
        # Next, I’ll check your vitals. Your temperature is 99.1°F, pulse is 78 bpm, respiration is 18 breaths per minute, and your blood pressure is 140/90 mmHg. Your weight is 180 lbs, and your height is 68 inches. You’ve mentioned that you're allergic to sulfa drugs, so I’ll make sure to note that as well.
        # Moving on to your skin assessment, you’ve said there are no issues, and from my check, your skin does appear a bit dry but warm. There’s no redness or other visible concerns, which is good.
        # Now, let’s talk about your physical status. Your breathing seems fine with no issues, and you have no paralysis or contractures. I’ll also make a note that you wear glasses and have dentures for both your upper and lower teeth.
        # Regarding mobility, you mentioned that you can transfer from bed or a chair, though you may need a little help from your wife, so I’ll record that as contact guard assistance. You’re able to walk on your own, but you use a cane for support. It’s great that you’re able to bear full weight on both sides, and there’s no need for additional supportive devices like elastic hose or an air mattress.
        # Let’s move on to your sensory abilities. Your hearing is good, and with your glasses, your vision is also fine. That’s all noted. Now, in terms of eating, you’re able to eat independently, and you don’t need any adaptive equipment for that.
        # For hygiene, I’ll note that you need some assistance with showering but can brush your teeth and shave on your own. You also mentioned that you need help with dressing, so I’ll make a note of that.
        # Next, we’ll review your bowel and bladder habits. You’ve confirmed that you’re continent of both bowel and bladder, and you don’t use a catheter. There are no issues with constipation or laxatives, which is good to hear.
        # Let’s talk about your psychosocial aspects. You’ve shared that you have a close relationship with your wife, who is your main caregiver. I’ll note that you describe yourself as alert and friendly, and your mood seems to be okay overall, though you sometimes feel homesick and worried about your health, which is understandable.
        # Lastly, I’ll confirm that you’re not a smoker and don’t use alcohol, so that’s all set.
        # Now, I’ll review your orientation to the facility. You’ve been shown around and know how to use the call lights, and you’re aware of the visiting hours, meal times, and facility rules.
        # That concludes our assessment, Mr. Smith. Thank you for answering all the questions. I’ll make sure your care plan is updated accordingly.
        # """
    ]

    # schema = EmrUtils.get_record_writable_schema(SpeakCareEmr.WEIGHTS_TABLE)
    # audio_path = 'Weighing_a_patient.mp3'
    # transcription_from_audio = transcribe_audio(audio_path)
    # transcriptions.append(transcription_from_audio)

    # schema = EmrUtils.get_record_writable_schema(SpeakCareEmr.BLOOD_PRESSURES_TABLE)

    schema = EmrUtils.get_record_writable_schema(SpeakCareEmr.ADMISSION_ASSESSMENTS_TABLE)

    for transcription in transcriptions:
        filled_schema_dict = fill_schema_with_transcription_as_dict(transcription, schema)
        print("-" * 80)
        print(f"Transcription:\n{transcription}")
        # print(schema)
        print("Filled Schema:")
        print(filled_schema_dict)



