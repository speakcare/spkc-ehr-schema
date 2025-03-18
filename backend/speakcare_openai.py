import json
import openai
from openai import OpenAI
from datetime import datetime, timezone
from os_utils import Timer
from dotenv import load_dotenv
import os
import re
import argparse
from speakcare_logging import SpeakcareLogger

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_TEMPERATURE= float(os.getenv("OPENAI_TEMPERATURE", 0.2))
OPENAI_MAX_COMPLETION_TOKENS= int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", 4096))
OPENAI_MODEL= os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")


__open_ai_default_system_prommpt= "You are an expert in parsing medical transcription and filling treatment forms."


logger = SpeakcareLogger('speakcare_openai')
openai_client = OpenAI()

def openai_chat_completion(system_prompt: str, user_prompt: str, num_choices: int = 1) -> dict:

   
    logger.info(f"Calling OpenAI API model '{OPENAI_MODEL}' with temperature '{OPENAI_TEMPERATURE}' and max_completion_tokens '{OPENAI_MAX_COMPLETION_TOKENS}' num_choices '{num_choices}'")
    logger.debug(f"System Prompt: {system_prompt}")
    logger.debug(f"User Prompt: {user_prompt}")

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=OPENAI_TEMPERATURE,
        max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
        n=num_choices
    )
    logger.info("OpenAI done")
    logger.debug(f"OpenAI Response: {response}")
    response_choices = []
    for choice in response.choices:
        content = choice.message.content.strip()
        response_choices.append({
            "role": choice.message.role,
            "content": content,
            "finish_reason": choice.finish_reason,
            "index": choice.index
        })
        logger.info(f"response_choices[{choice.index}]: role: {choice.message.role}, finish_reason: {choice.finish_reason}")
        logger.debug(f"response_choices[{choice.index}]: content: {content}")
    
    return response_choices


def main():
    parser = argparse.ArgumentParser(description='OpenAI Chat Completion')
    parser.add_argument('-u', '--user_prompt', required=False, type=str, help='User prompt')
    parser.add_argument('-s', '--system_prompt', required=False, type=str, help='System prompt')
    parser.add_argument('-n', '--num_choices', required=False, type=int, default=1, help='Number of choices')
    parser.add_argument('-uf', '--user_prompt_file', required=False, type=str, help='User prompt file')

    args = parser.parse_args()

    user_prompt = ""
    if args.user_prompt_file:
        try:
            with open(args.user_prompt_file, 'r') as f:
                user_prompt = f.read()
        except Exception as e:
            logger.log_exception(f"Error reading user prompt file: {args.user_prompt_file}", e)
            return
    elif args.user_prompt:
        user_prompt = args.user_prompt
    else:
        logger.error("User prompt or user prompt file is required.")
        return
    
    system_prompt = __open_ai_default_system_prommpt
    if args.system_prompt:
        system_prompt = args.system_prompt

    num_choices = 1
    if args.num_choices:
        num_choices = args.num_choices


    response = openai_chat_completion(system_prompt, user_prompt, num_choices)
    logger.debug(f"OpenAI Responses:")
    for choice in response:
        print(f"\nChoice index: {choice['index']}\nFinish Reason: {choice['finish_reason']}\n{choice['role']}: {choice['content']}\n")
        print("")

if __name__ == "__main__":
    main()