import traceback
import random
import os
from dotenv import load_dotenv
from DataLoader import DataLoader
from helpers import map_input_to_messages_lambda, save_results, upload_results, PassportExtraction
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DATASET_NAME = "India"
IMAGE_PATH = "data/indian/indian_yes"
PROMPT_PATH = "prompt.txt"
MODEL = "gemini-2.0-flash"
GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
PROJECT_NAME = f"{DATASET_NAME} - {MODEL} - {random.randint(0, 100)}"
ADD_DATA = False

def main():
    client = Client(api_key=LANGSMITH_API_KEY)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.0,
        max_output_tokens=4096,
    )

    runnable = RunnableLambda(map_input_to_messages_lambda)
    llm_retry = llm.with_retry(stop_after_attempt=5)
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

    def exact_match(outputs: dict, reference_outputs: dict) -> bool:
        return outputs == reference_outputs
    
    try:
        def target(inputs: dict) -> dict:
            """
            This is the target function where we ensure the input only contains the image data.
            The prompt is embedded by Langchain.
            """

            formatted_inputs = {"multimodal_prompt": inputs["multimodal_prompt"]}

            return llm_chain_factory().invoke(formatted_inputs)


        # Run the evaluation
        results = evaluate(
            target,
            data=DATASET_NAME,
            evaluators=[exact_match],
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
