import traceback
import random
import os
from dotenv import load_dotenv
from DataLoader import DataLoader
from helpers import map_input_to_messages_lambda, save_results, upload_results
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.runnables.retry import RunnableRetry
from google.api_core.exceptions import ResourceExhausted


load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# DATASET_NAME = "Passport Images - PHL 2"
DATASET_NAME = "Passport Images - ETH"
PROJECT_NAME = f"Passport Extraction {random.randint(1, 1000)}{random.randint(1, 1000)}"
IMAGE_PATH = "filipina_yes"
PROMPT_PATH = "prompt.txt"
GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "10w_D5gaP7bQNvYUlXDu_7pzZJqqfe5WlhkX-qBO3Ns8"
ADD_DATA = False

def main():
    client = Client(api_key=LANGSMITH_API_KEY)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.0,
        max_output_tokens=4096,
        max_retries=10
    )
    dataloader = DataLoader(
        client=client,
        dataset_name=DATASET_NAME,
        prompt_path=PROMPT_PATH,
        image_path=IMAGE_PATH,
    )

    json_parser = dataloader.json_parser
    input_mapper_runnable = RunnableLambda(map_input_to_messages_lambda)

    if ADD_DATA:
        try:
            client = dataloader.run()
            print("Data loading completed.")
        except Exception as e:
            print(f"\nAn error occurred during data loading: {e}")
            traceback.print_exc()

    def llm_chain_factory():
        return input_mapper_runnable | llm | json_parser

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
