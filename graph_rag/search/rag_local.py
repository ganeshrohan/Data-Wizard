import os
import asyncio
import pandas as pd
import tiktoken
from langchain_openai import ChatOpenAI as LangchainChatOpenAI


from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.input.loaders.dfs import (
    store_entity_semantic_embeddings,
)
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.embedding import OpenAIEmbedding
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.question_gen.local_gen import LocalQuestionGen
from graphrag.query.structured_search.local_search.mixed_context import (
    LocalSearchMixedContext,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore

from .templet import graphrag_system_propmpt_instruct,graphrag_system_propmpt_sql
from pathlib import Path
from openai import OpenAI

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir,os.path.pardir))

# INPUT_DIR = os.path.join(BASE_DIR, "graph_rag", "output", "20240922-210929","artifacts")
# Best unified data 
# 1. 20250704-132231 - with relationships *******************
# 2. 20250703-160230 - without relationships
# 3. 20250722-181849 - with relationships - Deepseek
# 4. 20250723-173241 - with relationships - Deepseek - Enhanced 
# 5. 20250724-225519 - with relationships - Deepseek - Enhanced++ 
# 6. 20250726-181000 - with relationships - Deepseek - Enhanced+++ Latest -- Issue with derived col ******
# Seprate data
# 3. 20240922-210929 - old version without relationships - all
# 4. 20250704-133845 - seperate data ******
INPUT_DIR = os.path.join(BASE_DIR, "graph_rag", "output", "20250724-225519","artifacts")
LANCEDB_URI = os.path.join(BASE_DIR, "lancedb")


COMMUNITY_REPORT_TABLE = "create_final_community_reports"
ENTITY_TABLE = "create_final_nodes"
ENTITY_EMBEDDING_TABLE = "create_final_entities"
RELATIONSHIP_TABLE = "create_final_relationships"
#COVARIATE_TABLE = "create_final_covariates"
TEXT_UNIT_TABLE = "create_final_text_units"
COMMUNITY_LEVEL = 0


# read nodes table to get community and degree data
entity_df = pd.read_parquet(f"{INPUT_DIR}/{ENTITY_TABLE}.parquet")
entity_embedding_df = pd.read_parquet(f"{INPUT_DIR}/{ENTITY_EMBEDDING_TABLE}.parquet")

entities = read_indexer_entities(entity_df, entity_embedding_df, COMMUNITY_LEVEL)

# load description embeddings to an in-memory lancedb vectorstore
# to connect to a remote db, specify url and port values.
description_embedding_store = LanceDBVectorStore(
    collection_name="entity_description_embeddings",
)
description_embedding_store.connect(db_uri=LANCEDB_URI)
entity_description_embeddings = store_entity_semantic_embeddings(
    entities=entities, vectorstore=description_embedding_store
)

# print(f"Entity count: {len(entity_df)}")



relationship_df = pd.read_parquet(f"{INPUT_DIR}/{RELATIONSHIP_TABLE}.parquet")
relationships = read_indexer_relationships(relationship_df)

report_df = pd.read_parquet(f"{INPUT_DIR}/{COMMUNITY_REPORT_TABLE}.parquet")
reports = read_indexer_reports(report_df, entity_df, COMMUNITY_LEVEL)
text_unit_df = pd.read_parquet(f"{INPUT_DIR}/{TEXT_UNIT_TABLE}.parquet")
text_units = read_indexer_text_units(text_unit_df)


def llm_model(model_name, is_pandas_ai=False):
    if is_pandas_ai:
        llm = LangchainChatOpenAI(
            api_key=openrouter_api,
            model=model_name,
            # api_type=OpenaiApiType.OpenAI,  # OpenaiApiType.OpenAI
            max_retries=3,
            base_url="https://openrouter.ai/api/v1")
        return llm
    else:
        llm = ChatOpenAI(
                api_key=openrouter_api,
                model=model_name,
                api_type=OpenaiApiType.OpenAI,  # OpenaiApiType.OpenAI or OpenaiApiType.AzureOpenAI
                max_retries=3,
                api_base= 'https://openrouter.ai/api/v1'  #  'https://api.groq.com/openai/v1'
            )
       
        return llm

token_encoder = tiktoken.get_encoding("cl100k_base")

text_embedder = OpenAIEmbedding(
    api_key='ollama',
    api_base='http://localhost:11434/v1',
    api_type=OpenaiApiType.OpenAI,
    model=embedding_model,
    deployment_name=embedding_model,
    max_retries=20,
)



context_builder = LocalSearchMixedContext(
    community_reports=reports,
    text_units=text_units,
    entities=entities,
    relationships=relationships,
    # if you did not run covariates during indexing, set this to None
    covariates=None,
    entity_text_embeddings=description_embedding_store,
    embedding_vectorstore_key=EntityVectorStoreKey.ID,  # if the vectorstore uses entity title as ids, set this to EntityVectorStoreKey.TITLE
    text_embedder=text_embedder,
    token_encoder=token_encoder,
)


local_context_params = {
    "text_unit_prop": 0.5,
    "community_prop": 0.1,
    "conversation_history_max_turns": 1,
    "conversation_history_user_turns_only": False,
    "top_k_mapped_entities": 5,
    "top_k_relationships": 5,
    "include_entity_rank": True,
    "include_relationship_weight": True,
    "include_community_rank": True,
    "return_candidate_context": False,
    "embedding_vectorstore_key": EntityVectorStoreKey.ID, 
    "max_tokens": 20000,  
}

llm_params = {
    "max_tokens": 20000,  
    "temperature": 0.0,
}


async def search(query,llm):
    
    search_engine = LocalSearch(
        llm=llm,
        context_builder=context_builder,
        token_encoder=token_encoder,
        llm_params=llm_params,
        context_builder_params=local_context_params,
        response_type="prioritized list"  #  prioritized list report
        #system_prompt=graphrag_system_propmpt_sql
        )
    
    context = graphrag_system_propmpt_sql.format(query=query)
    result = await search_engine.asearch(query=context)
    return result

#query = "Calculate the total exposure amount and market value for each account type within each region, and rank the results by exposure amount within each region ?"

# query = """Identify the month with the highest total invoice revenue."""
# # # # #What are the trends in streams across different content?


# result = asyncio.run(search(query,llm_model(model_name=llm_model_)))
# print(context_builder)
# print('=============================================================')
# print(result.response)
# print('=============================================================')
# print(result.context_data)



# print(result.context_data["entities"])
# print('=============================================================')
# print(result.context_data["relationships"])
# print('=============================================================')
# print(result.context_data["reports"])
# print('=============================================================')
# print(result.context_data["sources"])
# print('=============================================================')
