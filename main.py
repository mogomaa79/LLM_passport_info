import traceback
import random
import os
from dotenv import load_dotenv
from json.decoder import JSONDecodeError
from collections import Counter
from typing import List, Dict, Any

from src.passport_extraction import PassportExtraction, CertainField
from src.utils import save_results, postprocess, field_match, full_passport, ResultsAgent

from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.runnables import RunnableLambda
from langsmith import Client, evaluate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

DATASET_NAME = "Philippines"
MODEL = "gemini-2.5-pro"
SPLITS = ["no"]
NUM_RUNS = 3  # Number of times to run each extraction for certainty calculation

GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
PROJECT_NAME = f"{DATASET_NAME} - {MODEL} - {random.randint(0, 1000)}"

def get_prompt():
    """Load the Simple prompt for universal extraction"""
    try:
        with open(f"prompts/Simple.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error reading Simple prompt file: {e}")

def map_input_to_messages_lambda(inputs: dict):
    """Convert inputs to LangChain messages format"""
    multimodal_prompt = inputs.get("multimodal_prompt", [])
    prompt_text = get_prompt()
    
    multimodal_prompt.insert(0, {"type": "text", "text": prompt_text})
    messages = [
        HumanMessage(content=multimodal_prompt),
    ]
    
    return messages

def aggregate_results_with_certainty(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate multiple extraction results to determine most frequent values and certainty.
    
    Args:
        results: List of extraction results from multiple runs
        
    Returns:
        Dictionary with CertainField values including certainty information
    """
    if not results:
        return {}
    
    # Get all field names from the first result
    field_names = list(results[0].keys())
    aggregated = {}
    
    for field_name in field_names:
        # Collect all values for this field
        field_values = []
        for result in results:
            value = result.get(field_name, "")
            # Handle both string and CertainField values
            if hasattr(value, 'value'):
                field_values.append(str(value.value))
            else:
                field_values.append(str(value))
        
        # Count occurrences
        value_counts = Counter(field_values)
        
        # Get most frequent value
        most_frequent_value = value_counts.most_common(1)[0][0] if value_counts else ""
        
        # Calculate certainty (all runs agree)
        certainty = len(value_counts) == 1 and len(results) > 1
        
        # Create CertainField with aggregated result
        aggregated[field_name] = CertainField(most_frequent_value, certainty)
    
    return aggregated

def multiple_runs_extraction(llm_chain, formatted_inputs: dict, num_runs: int = NUM_RUNS) -> Dict[str, Any]:
    """
    Run extraction multiple times and aggregate results with certainty.
    
    Args:
        llm_chain: The LLM chain to use for extraction
        formatted_inputs: Input data for extraction
        num_runs: Number of times to run the extraction
        
    Returns:
        Aggregated results with certainty information
    """
    results = []
    
    for i in range(num_runs):
        try:
            result = llm_chain.invoke(formatted_inputs)
            results.append(result)
        except Exception as e:
            print(f"Error in run {i+1}: {e}")
            # Continue with other runs even if one fails
            continue
    
    if not results:
        raise ValueError("All extraction runs failed")
    
    # Aggregate results with certainty
    aggregated_result = aggregate_results_with_certainty(results)
    
    # Create PassportExtraction object with CertainField values
    passport_extraction = PassportExtraction()
    for field_name, certain_field in aggregated_result.items():
        if hasattr(passport_extraction, field_name):
            setattr(passport_extraction, field_name, certain_field)
    
    return passport_extraction

def simple_target_function(llm_chain):
    """
    Simple target function for LangSmith's num_repetitions parameter.
    Runs extraction once per call - LangSmith handles the repetitions.
    """
    def target(inputs: dict) -> dict:
        if "multimodal_prompt" not in inputs:
            inputs = inputs["inputs"]
        if "multimodal_prompt" not in inputs:
            raise ValueError("Missing 'multimodal_prompt' in inputs")
        
        formatted_inputs = {"multimodal_prompt": inputs["multimodal_prompt"]}
        
        # Run extraction once - LangSmith will handle repetitions
        result = llm_chain.invoke(formatted_inputs)
        
        # Apply postprocessing - handle both dict and Pydantic model objects
        if hasattr(result, 'model_dump'):
            # It's a Pydantic model
            postprocessed_results = postprocess(result.model_dump())
        elif isinstance(result, dict):
            # It's already a dict
            postprocessed_results = postprocess(result)
        else:
            # Fallback - try to convert to dict
            try:
                postprocessed_results = postprocess(dict(result))
            except Exception as e:
                print(f"Failed to convert result to dict: {e}")
                # Return empty dict as fallback
                postprocessed_results = {}
        
        # Convert to dictionary format expected by evaluators
        results_dict = {}
        for field_name, field_value in postprocessed_results.items():
            if isinstance(field_value, CertainField):
                str_value = str(field_value)
                # Handle "nan", "NaN", "NAN" strings specifically
                if str_value.lower() in ['nan', 'none', 'null', 'n/a', 'na']:
                    results_dict[field_name] = ""
                else:
                    results_dict[field_name] = str_value
            elif field_value is None:
                # Handle None values - convert to empty string
                results_dict[field_name] = ""
            else:
                str_value = str(field_value) if field_value is not None else ""
                # Handle "nan", "NaN", "NAN" strings specifically
                if str_value.lower() in ['nan', 'none', 'null', 'n/a', 'na']:
                    results_dict[field_name] = ""
                else:
                    results_dict[field_name] = str_value
        
        return results_dict
    
    return target

def field_match_with_repetitions(outputs: dict, reference_outputs: dict) -> dict:
    """
    Enhanced field match evaluator that works with LangSmith's num_repetitions.
    When num_repetitions is used, this evaluator runs multiple times per example.
    
    Args:
        outputs: Single output dictionary from one run
        reference_outputs: Reference outputs for comparison
        
    Returns:
        Dictionary with field match score in LangSmith format
    """
    try:
        # Calculate field match score using the standard field_match function
        field_score = field_match(outputs, reference_outputs)
        
        return {
            "key": "field_match_score",
            "score": field_score
        }
    
    except Exception as e:
        print(f"Error in field_match_with_repetitions: {e}")
        traceback.print_exc()
        return {"key": "field_match_score", "score": 0.0}



def full_passport_with_repetitions(outputs: dict, reference_outputs: dict) -> dict:
    """
    Enhanced full passport evaluator that works with LangSmith's num_repetitions.
    When num_repetitions is used, this evaluator runs multiple times per example.
    
    Args:
        outputs: Single output dictionary from one run
        reference_outputs: Reference outputs for comparison
        
    Returns:
        Dictionary with full passport match result in LangSmith format
    """
    try:
        # Calculate field match score using the standard field_match function
        field_score = field_match(outputs, reference_outputs)
        
        # Full passport match is true if field_match_score is 1.0
        full_match = field_score == 1.0
        
        return {
            "key": "full_passport_match",
            "score": 1.0 if full_match else 0.0
        }
    
    except Exception as e:
        print(f"Error in full_passport_with_repetitions: {e}")
        traceback.print_exc()
        return {"key": "full_passport_match", "score": 0.0}

def main():
    client = Client(api_key=LANGSMITH_API_KEY)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=1.0,
        max_tokens=10000,
        max_output_tokens=1024,
        thinking_budget=8192 if "2.5" in MODEL else None,
    )

    runnable = RunnableLambda(map_input_to_messages_lambda)
    llm_retry = llm.with_retry(retry_if_exception_type=(Exception, JSONDecodeError), stop_after_attempt=5)
    json_parser = JsonOutputParser(pydantic_object=PassportExtraction)

    def llm_chain_factory():
        return runnable | llm_retry | json_parser

    print(f"\nStarting run on dataset '{DATASET_NAME}' with project name '{PROJECT_NAME}'...")
    print(f"Using LangSmith's num_repetitions={NUM_RUNS} for certainty calculation...")

    # Create the simple target function for num_repetitions
    target = simple_target_function(llm_chain_factory())
    
    try:
        results = evaluate(
            target,
            data=client.list_examples(dataset_name=DATASET_NAME, splits=SPLITS),
            evaluators=[field_match_with_repetitions, full_passport_with_repetitions],
            experiment_prefix=f"{MODEL} ",
            client=client,
            max_concurrency=15,  # Increased concurrency since we're no longer doing multiple runs per example
            num_repetitions=NUM_RUNS,  # Use LangSmith's built-in repetitions
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