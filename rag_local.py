import os
import asyncio
import pandas as pd
import tiktoken
from pathlib import Path
from langchain_openai import ChatOpenAI as LangchainChatOpenAI

from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.input.loaders.dfs import store_entity_semantic_embeddings
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.embedding import OpenAIEmbedding
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.question_gen.local_gen import LocalQuestionGen
from graphrag.query.structured_search.local_search.mixed_context import (
    LocalSearchMixedContext,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore

# Assuming your templates are in a file named 'templates.py' in the same directory
# from .templet import graphrag_system_propmpt_instruct,graphrag_system_propmpt_sql
# Example content for templates.py:
# graphrag_system_propmpt_sql = "Based on the data, answer the user query: {query}"
from templates import graphrag_system_propmpt_instruct, graphrag_system_propmpt_sql


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "ollama")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE") # e.g., for local Ollama

LLM_MODEL_NAME = "openai/gpt-4o"  # Or any other model from OpenRouter
EMBEDDING_MODEL_NAME = "nomic-embed-text" # Or your preferred embedding model

# --- Path Configuration ---
# Use pathlib for modern, cross-platform path management
BASE_DIR = Path(__file__).resolve().parent

# Path to GraphRAG output. Replace <your_run_id> with the timestamped folder name.
RUN_ID = "<your_run_id>"
INPUT_DIR = BASE_DIR / "output" / RUN_ID / "artifacts"

# Path to the LanceDB vector database
LANCEDB_URI = str(BASE_DIR / "lancedb")

# --- GraphRAG Table & Parameter Configuration ---
COMMUNITY_REPORT_TABLE = "create_final_community_reports"
ENTITY_TABLE = "create_final_nodes"
ENTITY_EMBEDDING_TABLE = "create_final_entities"
RELATIONSHIP_TABLE = "create_final_relationships"
TEXT_UNIT_TABLE = "create_final_text_units"
COMMUNITY_LEVEL = 2 # The community level to analyze



# --- Load GraphRAG Artifacts ---
entity_df = pd.read_parquet(INPUT_DIR / f"{ENTITY_TABLE}.parquet")
entity_embedding_df = pd.read_parquet(INPUT_DIR / f"{ENTITY_EMBEDDING_TABLE}.parquet")
entities = read_indexer_entities(entity_df, entity_embedding_df, COMMUNITY_LEVEL)

# --- Setup Vector Store ---
description_embedding_store = LanceDBVectorStore(collection_name="entity_description_embeddings")
description_embedding_store.connect(db_uri=LANCEDB_URI)
store_entity_semantic_embeddings(entities=entities, vectorstore=description_embedding_store)

# --- Load Remaining Data ---
relationship_df = pd.read_parquet(INPUT_DIR / f"{RELATIONSHIP_TABLE}.parquet")
relationships = read_indexer_relationships(relationship_df)

report_df = pd.read_parquet(INPUT_DIR / f"{COMMUNITY_REPORT_TABLE}.parquet")
reports = read_indexer_reports(report_df, entity_df, COMMUNITY_LEVEL)

text_unit_df = pd.read_parquet(INPUT_DIR / f"{TEXT_UNIT_TABLE}.parquet")
text_units = read_indexer_text_units(text_unit_df)

# --- Setup LLM and Embedder ---
def get_llm(model_name=LLM_MODEL_NAME):
    """Initializes the ChatOpenAI model."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable not set.")
    
    return ChatOpenAI(
        api_key=OPENROUTER_API_KEY,
        model=model_name,
        api_type=OpenaiApiType.OpenAI,
        api_base=OPENROUTER_API_BASE,
        max_retries=3
    )

token_encoder = tiktoken.get_encoding("cl100k_base")

text_embedder = OpenAIEmbedding(
    api_key=EMBEDDING_API_KEY,
    api_base=EMBEDDING_API_BASE,
    api_type=OpenaiApiType.OpenAI,
    model=EMBEDDING_MODEL_NAME,
    deployment_name=EMBEDDING_MODEL_NAME,
    max_retries=20,
)

# --- Setup Context Builder and Search Parameters ---
context_builder = LocalSearchMixedContext(
    community_reports=reports,
    text_units=text_units,
    entities=entities,
    relationships=relationships,
    covariates=None,  # Set to None if covariates were not generated during indexing
    entity_text_embeddings=description_embedding_store,
    embedding_vectorstore_key=EntityVectorStoreKey.ID,
    text_embedder=text_embedder,
    token_encoder=token_encoder,
)

local_context_params = {
    "text_unit_prop": 0.5,
    "community_prop": 0.1,
    "conversation_history_max_turns": 5,
    "top_k_mapped_entities": 10,
    "top_k_relationships": 10,
    "max_tokens": 5000,
}

llm_params = {
    "max_tokens": 1500,
    "temperature": 0.0,
}



async def perform_search(query: str):
    """
    Performs a search using the configured GraphRAG local search engine.
    """
    llm = get_llm()
    search_engine = LocalSearch(
        llm=llm,
        context_builder=context_builder,
        token_encoder=token_encoder,
        llm_params=llm_params,
        context_builder_params=local_context_params,
        response_type="report",  # "report" or "prioritized list"
    )

    # Use a structured prompt for better results
    prompt_context = graphrag_system_propmpt_sql.format(query=query)
    result = await search_engine.asearch(prompt_context)
    return result



async def main():
    """
    Main function to run the search query.
    """
    # Ensure all required configurations are set
    if not all([RUN_ID != "<your_run_id>", OPENROUTER_API_KEY]):
        print("🚨 Error: Please configure RUN_ID and set your OPENROUTER_API_KEY environment variable.")
        return

    user_query = "Who is the main person of interest in the data?"
    print(f"Executing search for query: '{user_query}'")
    
    result = await perform_search(user_query)
    
    print("\n--- Search Result ---")
    print(result.response)
    print("\n--- Context Data ---")
    for item_id, data in result.context_data["entities"].items():
        print(f"Entity: {data['entity'].title}, Rank: {data['rank']}")


if __name__ == "__main__":
    asyncio.run(main())