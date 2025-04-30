import traceback
import random
import os
from dotenv import load_dotenv
from DataLoader import DataLoader
from helpers import map_input_to_messages_lambda, save_results, upload_results, PassportExtraction
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.output_parsers import JsonOutputParser
from json.decoder import JSONDecodeError

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATASET_NAME = "test_india"
IMAGE_PATH = "data/indian/indian_yes"
PROVIDER = "google"
MODEL = "gemini-2.0-flash"
GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
PROJECT_NAME = f"{DATASET_NAME} - {MODEL} - {random.randint(0, 100)}"
ADD_DATA = False

def main():
    client = Client(api_key=LANGSMITH_API_KEY)

    if PROVIDER == "openai":
        llm = ChatOpenAI(
            model=MODEL,
            temperature=0.0,
            max_tokens=2048,
        )
    elif PROVIDER == "google":
        llm = ChatGoogleGenerativeAI(
            model=MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.0,
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
        return runnable | llm_retry | json_parser

    print(f"\nStarting run on dataset '{DATASET_NAME}' with project name '{PROJECT_NAME}'...")
    
    def field_match(outputs: dict, reference_outputs: dict) -> float:
        reference_outputs = reference_outputs["reference_output"]
        correct = 0
        correct += outputs["number"] == reference_outputs["passport id"]
        correct += outputs["expiry date"] == reference_outputs["passport expiry date"]
        correct += outputs["issue date"] == reference_outputs["passport issue date"]
        correct += outputs["birth date"] == reference_outputs["birthdate"]
        correct += outputs["place of issue"] == reference_outputs["passport place(en)"]
        correct += outputs["place of birth"] == reference_outputs["birth place"]
        correct += outputs["country of issue"] == reference_outputs["country of issue"]
        correct += outputs["country"] == "IND"
        correct += outputs["gender"] == reference_outputs["gender"][0]
        correct += outputs["name"] == reference_outputs["first name"]
        correct += outputs["father name"] == reference_outputs["last name"]
        correct += outputs["mother name"] == reference_outputs["mother name"].split()[0]
        #correct += outputs["middle name"] == reference_outputs["middle name"]
        #correct += outputs["surname"] == reference_outputs["surname"]

        return correct / 12
    
    def full_passport(outputs: dict, reference_outputs: dict) -> bool:
        return field_match(outputs, reference_outputs) == 1
    try:
        def target(inputs: dict) -> dict:
            formatted_inputs = {"multimodal_prompt": inputs["multimodal_prompt"]}
            return llm_chain_factory().invoke(formatted_inputs)

        results = evaluate(
            target,
            data=DATASET_NAME,
            evaluators=[full_passport, field_match],
            experiment_prefix="Passport Images experiment ",
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
