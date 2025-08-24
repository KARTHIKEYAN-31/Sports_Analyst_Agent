"""LangGraph single-node graph template.

Returns a predefined response. Replace logic and configuration as needed.
"""

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
# from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, TypedDict

from langgraph.graph import StateGraph
from langchain_core.tools import tool
import requests
import json
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, SystemMessage
import agent.search_agent as s_a
import agent.sql_agent as sql_a
import getpass
import os
from langchain_google_genai import ChatGoogleGenerativeAI
import pydantic




llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-001")

search_agent = s_a.search_agent
sql_agent = sql_a.sql_agent

class SportState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    sql_result: Optional[str]
    search_result: Optional[str]
    
def search_llm(state: SportState):
    print("---calling search agent---")
    response = search_agent.invoke({"messages":[HumanMessage(content=state["messages"][-1].content)]})
    return {"search_result": response["messages"][-1].content}

class answer_with_query(pydantic.BaseModel):
    answer: Annotated[str, "Answer or summary or stats for the given question based on the extracted information"]
    query: Annotated[list[str], "Question to ask to the user which can be answered from the extracted information"]

class IsContinue(pydantic.BaseModel):
    is_continue: Annotated[bool, "Whether to continue the conversation or not"]



def analyst_node(state: SportState):
    print("---Analyst Node---")
    # print(state)
    input = [
        SystemMessage(content=f"""You are a sports analyst. Based on the information extracted form web search and internal datatabase,
answer the question by performing analysis. Return a well defined last match stats or summary and a historical matches comparison table.
Along with that suggest some question that can be answered from the extracted information.
Information from Web Search:
{state['search_result']}
Informaiton from Internal Database:
{state['sql_result']} 
Note:
    The answer must contain the summary and stats of the last match with a table to show stats.      
        """),
        HumanMessage(content=state["messages"][-1].content),
    ]

    response = llm.with_structured_output(answer_with_query).invoke(input)

    
    feedback = interrupt(
        {
            "question": response.query,
            "answer": response.answer,
        }
    )

    is_continue = llm.with_structured_output(IsContinue).invoke(feedback)

    print(is_continue)
    
    if is_continue.is_continue:
        update_message = {
                "messages":[AIMessage(content=response.answer), HumanMessage(content=response.query)]
            }
        return Command(
            goto = "analyst_node",
            update = update_message
        )
    else:
        update_message = {
                "messages":[AIMessage(content=response.answer)]
            }
        return Command(
            goto = END,
            update = update_message
        )

builder = StateGraph(SportState)
builder.add_node("sql_agent", sql_agent)
builder.add_node("search_agent", search_llm)
builder.add_node("analyst_node", analyst_node)

builder.add_edge(START, "sql_agent")
builder.add_edge(START, "search_agent")
builder.add_edge("sql_agent", "analyst_node")
builder.add_edge("search_agent", "analyst_node")


graph = builder.compile()





