import traceback
import random
import os
import time
from dotenv import load_dotenv
from json.decoder import JSONDecodeError

from src.passport_extraction import PassportExtraction
from src.utils import save_results, postprocess, field_match, full_passport, ResultsAgent

from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

DATASET_NAME = "Sri Lanka"
MODEL = "gemini-2.5-pro-preview-05-06"
SPLITS = ["test"]

GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
PROJECT_NAME = f"{DATASET_NAME} - {MODEL} - {random.randint(0, 1000)}"

def get_prompt():
    """Load the prompt for a specific country"""
    try:
        with open(f"prompts/General.txt", "r", encoding="utf-8") as f:
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

def main():
    client = Client(api_key=LANGSMITH_API_KEY)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=1.0,
        max_tokens=30000,
        max_output_tokens=1024,
        thinking_budget=4096 if "2.5" in MODEL else None,
    )

    runnable = RunnableLambda(map_input_to_messages_lambda)
    llm_retry = llm.with_retry(retry_if_exception_type=(Exception, JSONDecodeError), stop_after_attempt=5)
    json_parser = JsonOutputParser(pydantic_object=PassportExtraction)
    postprocessor = RunnableLambda(postprocess)

    def llm_chain_factory():
        return runnable | llm_retry | json_parser

    print(f"\nStarting run on dataset '{DATASET_NAME}' with project name '{PROJECT_NAME}'...")

    def target(inputs: dict) -> dict:
        if "multimodal_prompt" not in inputs:
            inputs = inputs["inputs"]
        if "multimodal_prompt" not in inputs:
            raise ValueError("Missing 'multimodal_prompt' in inputs")
        
        formatted_inputs = {"multimodal_prompt": inputs["multimodal_prompt"]}
        results = llm_chain_factory().invoke(formatted_inputs)
        # time.sleep(1)
        return results
    
    try:
        results = evaluate(
            target,
            data=client.list_examples(dataset_name=DATASET_NAME, splits=SPLITS),
            evaluators=[field_match, full_passport],
            experiment_prefix=f"{MODEL} ",
            client=client,
            max_concurrency=20,
        )

        print("\nRun on dataset completed successfully!")
        results_path = f"results/{PROJECT_NAME}_results.csv"
        save_results(results, results_path)
        results_agent = ResultsAgent(
            spreadsheet_id=SPREADSHEET_ID,
            credentials_path=GOOGLE_SHEETS_CREDENTIALS_PATH,
            country=DATASET_NAME,
        )
        results_agent.upload_results(results_path)

    except Exception as e:
        print(f"\nAn error occurred during the run on dataset")
        traceback.print_exc()
        print("\nRun on dataset failed.")

if __name__ == "__main__":
    main() 