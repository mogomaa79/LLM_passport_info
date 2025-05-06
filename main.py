import traceback
import random
import os
import time
from dotenv import load_dotenv
import pandas as pd
from json.decoder import JSONDecodeError

from src.data_loader import DataLoader
from src.passport_extraction import PassportExtraction
from src.utils import (save_results, upload_results, postprocess)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATASET_NAME = "Kenya"
IMAGE_PATH = "data/kenya/kenya_yes"

MODEL = "gemini-2.0-flash"
GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
PROJECT_NAME = f"{DATASET_NAME} - {MODEL} - {random.randint(0, 100)}"
ADD_DATA = False

def get_prompt():
    """Load the prompt for a specific country"""
    try:
        with open(f"prompts/{DATASET_NAME}.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error reading prompt file for {DATASET_NAME}: {e}")

def map_input_to_messages_lambda(inputs: dict):
    """Convert inputs to LangChain messages format"""
    multimodal_prompt = inputs.get("multimodal_prompt")
    prompt_text = get_prompt()
    
    multimodal_prompt.insert(0, {"type": "text", "text": prompt_text})
    messages = [
        HumanMessage(content=multimodal_prompt),
    ]
    
    return messages

def field_match(outputs: dict, reference_outputs: dict) -> float:
    try:
        if "reference_output" in reference_outputs:
            reference_outputs = reference_outputs["reference_output"]
        convert = lambda value: pd.to_datetime(value).strftime('%d/%m/%Y') if pd.to_datetime(value, errors='coerce') is not pd.NaT else value
        correct = 0
        correct += outputs["number"] == reference_outputs["passport id"]
        correct += outputs["expiry date"] == convert(reference_outputs["passport expiry date"])
        correct += outputs["issue date"] == convert(reference_outputs["passport issue date"])
        correct += outputs["birth date"] == convert(reference_outputs["birthdate"])
        correct += outputs["place of issue"] == reference_outputs["passport place(en)"]
        correct += outputs["place of birth"] == reference_outputs["birth place"]
        correct += outputs["country of issue"] == reference_outputs["country of issue"]
        correct += outputs["country"] == "KEN"
        correct += outputs["gender"] == reference_outputs["gender"][0]
        correct += outputs["name"] == reference_outputs["first name"]
        correct += outputs["father name"] == ""
        correct += outputs["mother name"] == ""
        correct += outputs["middle name"] == ""
        correct += outputs["surname"] == reference_outputs["last name"]

        return correct / 14
    
    except Exception as e:
        print(f"\nAn error occurred during field matching: {e}")
        traceback.print_exc()
        return 0

def full_passport(outputs: dict, reference_outputs: dict) -> bool:
    return field_match(outputs, reference_outputs) == 1      

def main():
    client = Client(api_key=LANGSMITH_API_KEY)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.0,
        max_tokens=50000,
        max_output_tokens=2048,
    )

    runnable = RunnableLambda(map_input_to_messages_lambda)
    llm_retry = llm.with_retry(retry_if_exception_type=(Exception, JSONDecodeError), stop_after_attempt=5)
    json_parser = JsonOutputParser(pydantic_object=PassportExtraction)

    if ADD_DATA:
        dataloader = DataLoader(
            client=client,
            dataset_name=DATASET_NAME,
            image_path=IMAGE_PATH,
        )
        try:
            client = dataloader.run()
            print("Data loading completed.")
        except Exception as e:
            print(f"\nAn error occurred during data loading: {e}")
            traceback.print_exc()

    def llm_chain_factory():
        return runnable | llm_retry | json_parser | RunnableLambda(postprocess)

    print(f"\nStarting run on dataset '{DATASET_NAME}' with project name '{PROJECT_NAME}'...")

    def target(inputs: dict) -> dict:
        if "multimodal_prompt" not in inputs:
            inputs = inputs["inputs"]
        if "multimodal_prompt" not in inputs:
            raise ValueError("Missing 'multimodal_prompt' in inputs")
        
        formatted_inputs = {"multimodal_prompt": inputs["multimodal_prompt"]}
        results = llm_chain_factory().invoke(formatted_inputs)
        return results
    
    try:
        results = evaluate(
            target,
            data=client.list_examples(dataset_name=DATASET_NAME, splits=["base"]),
            evaluators=[field_match, full_passport],
            experiment_prefix=f"{MODEL} ",
            client=client,
        )

        print("\nRun on dataset completed successfully!")
        results_path = f"results/{PROJECT_NAME}_results.csv"
        save_results(results, results_path)
        upload_results(
            results_path,
            spreadsheet_id=SPREADSHEET_ID,
            credentials_path=GOOGLE_SHEETS_CREDENTIALS_PATH,
        )

    except Exception as e:
        print(f"\nAn error occurred during the run on dataset")
        traceback.print_exc()
        print("\nRun on dataset failed.")

if __name__ == "__main__":
    main() 