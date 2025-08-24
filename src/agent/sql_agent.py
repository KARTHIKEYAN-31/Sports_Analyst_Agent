
from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///sports_data.db")
print(db.dialect)
print(db.get_usable_table_names())

from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, SystemMessage



import operator
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import os
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode 
from langgraph.types import Command
from langgraph.types import interrupt
from langgraph.checkpoint.memory import InMemorySaver
from typing import Optional

load_dotenv()
import getpass
import os
from langchain_google_genai import ChatGoogleGenerativeAI


class State(TypedDict):
    query: str
    sql_result: str
    messages: Annotated[list[AnyMessage], add_messages]

from langchain.chat_models import init_chat_model

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-001")

from langchain_core.prompts import ChatPromptTemplate

system_message = """
Given an input question, create a syntactically correct {dialect} query to
run to help find the answer. Unless the user specifies in his question a
specific number of examples they wish to obtain, always limit your query to
at most {top_k} results. You can order the results by a relevant column to
return the most interesting examples in the database.

Never query for all the columns from a specific table, only ask for a the
few relevant columns given the question.

Pay attention to use only the column names that you can see in the schema
description. Be careful to not query for columns that do not exist. Also,
pay attention to which column is in which table.

Only use the following tables:
{table_info}
"""

user_prompt = "Question: {input}"

query_prompt_template = ChatPromptTemplate(
    [("system", system_message), ("user", user_prompt)]
)

for message in query_prompt_template.messages:
    message.pretty_print()


from typing_extensions import Annotated
import pydantic

class QueryOutput(pydantic.BaseModel):
    query: Annotated[str, "SQL query"]


def write_query(state: State):
    """Generate SQL query to fetch information."""
    print("write query")
    prompt = query_prompt_template.invoke(
        {
            "dialect": db.dialect,
            "top_k": 10,
            "table_info": db.get_table_info(),
            "input": state["messages"][-1].content,
        }
    )
    structured_llm = llm.with_structured_output(QueryOutput)
    # print(prompt)
    result = structured_llm.invoke(prompt)
    # print(type(result))
    return {"query": result.query}

from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool


def execute_query(state: State):
    print("execute query")
    """Execute SQL query."""
    execute_query_tool = QuerySQLDatabaseTool(db=db)
    return {"sql_result": execute_query_tool.invoke(state["query"])}

def generate_answer(state: State):
    print("generate answer")
    """Answer question using retrieved information as context."""
    prompt = (
        "Given the following user question, corresponding SQL query, "
        "and SQL result, answer the user question.\n\n"
        f"Question: {state['messages'][-1].content}\n"
        f"SQL Query: {state['query']}\n"
        f"SQL Result: {state['sql_result']}"
    )
    response = llm.invoke(prompt)
    return {"sql_result": response.content}

from langgraph.graph import START, StateGraph

graph_builder = StateGraph(State).add_sequence(
    [write_query, execute_query, generate_answer]
)
graph_builder.add_edge(START, "write_query")
sql_agent = graph_builder.compile()

