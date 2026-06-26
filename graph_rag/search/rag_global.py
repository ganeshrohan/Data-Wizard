import pandas as pd
import tiktoken
import asyncio
from graphrag.query.indexer_adapters import read_indexer_entities, read_indexer_reports
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.global_search.community_context import (GlobalCommunityContext,)
from graphrag.query.structured_search.global_search.search import GlobalSearch



llm = ChatOpenAI(
    api_key=api_key,
    model=llm_model,
    api_base='https://api.groq.com/openai/v1',
    api_type=OpenaiApiType.OpenAI,  # OpenaiApiType.OpenAI or OpenaiApiType.AzureOpenAI
    max_retries=20,
)

token_encoder = tiktoken.get_encoding("cl100k_base")


# parquet files generated from indexing pipeline
INPUT_DIR = "C:\\Code\\snowChat-main\\ragtest\\output\\20240922-014401\\artifacts"
COMMUNITY_REPORT_TABLE = "create_final_community_reports"
ENTITY_TABLE = "create_final_nodes"
ENTITY_EMBEDDING_TABLE = "create_final_entities"

# community level in the Leiden community hierarchy from which we will load the community reports
# higher value means we use reports from more fine-grained communities (at the cost of higher computation cost)
COMMUNITY_LEVEL = 0


entity_df = pd.read_parquet(f"{INPUT_DIR}/{ENTITY_TABLE}.parquet")
report_df = pd.read_parquet(f"{INPUT_DIR}/{COMMUNITY_REPORT_TABLE}.parquet")
entity_embedding_df = pd.read_parquet(f"{INPUT_DIR}/{ENTITY_EMBEDDING_TABLE}.parquet")

reports = read_indexer_reports(report_df, entity_df, COMMUNITY_LEVEL)
entities = read_indexer_entities(entity_df, entity_embedding_df, COMMUNITY_LEVEL)
print(f"Report records: {len(report_df)}")
report_df.head()

context_builder = GlobalCommunityContext(
    community_reports=reports,
    entities=entities,  # default to None if you don't want to use community weights for ranking
    token_encoder=token_encoder,
)

context_builder_params = {
    "use_community_summary": True,  # False means using full community reports. True means using community short summaries.
    "shuffle_data": False,
    "include_community_rank": True,
    "min_community_rank": 0,
    "community_rank_name": "rank",
    "include_community_weight": True,
    "community_weight_name": "occurrence weight",
    "normalize_community_weight": True,
    "max_tokens":  8000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
    "context_name": "Reports",
}

map_llm_params = {
    "max_tokens": 1000,
    "temperature": 0.0,
    "response_format": {"type": "json_object"}, #json_object
}

reduce_llm_params = {
    "max_tokens": 8000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 1000-1500)
    "temperature": 0.0,
}

search_engine = GlobalSearch(
    llm=llm,
    context_builder=context_builder,
    token_encoder=token_encoder,
    max_data_tokens=8000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
    map_llm_params=map_llm_params,
    reduce_llm_params=reduce_llm_params,
    allow_general_knowledge=False,  # set this to True will add instruction to encourage the LLM to incorporate general knowledge in the response, which may increase hallucinations, but could be useful in some use cases.
    json_mode=True,  # set this to False if your LLM model does not support JSON mode.
    context_builder_params=context_builder_params,
    concurrent_coroutines=32,
    response_type="multiple paragraphs",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
)

"""Write a single SQL that answers the given question, first, identify the relevant table names and column names.
Ensure you pick the exact names of the tables and columns required. Next, determine the appropriate joins between the tables 
and specify any filter conditions that are most pertinent to addressing the question. 
If the provided question is too generic or unclear, ask the user if they need additional help to clarify their query.



Please retrieve the necessary table names, column names, and any required joins to answer the following query: {query}.
Important: Include joins and filters only if they are truly required to satisfy the query.
Ensure that table names, column names, joins, and filters align with the current knowledge base. Avoid generating the SQL syntax itself; focus solely on the elements needed to construct it.
"""
async def search(query):

    result = await search_engine.asearch(f"""{query}""")
    return result


query = "what is the data about explain it?" #how many customers stream more than 2 hours
result = asyncio.run(search(query))

print(result.response)
# inspect the data used to build the context for the LLM responses
result.context_data["reports"]

# inspect number of LLM calls and tokens
print(f"LLM calls: {result.llm_calls}. LLM tokens: {result.prompt_tokens}")

# print(result.context_text)

# print(result.completion_time)

# result.context_data["entities"].head()
# result.context_data["relationships"].head()
# result.context_data["reports"].head()
# result.context_data["sources"].head()
