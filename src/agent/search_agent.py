from langchain_core.tools import tool
import requests
import json
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

# NOTE: The ESPN API is not officially public. These endpoints are what the ESPN website uses.
# They can change without notice. This is for demonstration purposes.
# A more robust solution might involve a paid API like SportRadar.
ESPN_NEWS_API_URL = "http://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/news"
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-001")
@tool
def espn_tool(sport: str, league: str, limit: int = 5) -> str:
    """
    Fetches the latest sports news headlines for a given sport and league from the ESPN API.
    For example, to get the latest NFL news, use sport='football' and league='nfl'.
    To get the latest NBA news, use sport='basketball' and league='nba'.
    To get the latest MLB news, use sport='baseball' and league='mlb'.
    To get the latest Soccer news for the Premier League, use sport='soccer' and league='eng.1'.
    """
    try:
        url = ESPN_NEWS_API_URL.format(sport=sport, league=league)
        params = {'limit': limit}
        response = requests.get(url, params=params)
        response.raise_for_status()  # Will raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        articles = data.get('articles', [])
        
        if not articles:
            return f"No recent news found for {sport}/{league}."
            
        # Format the news for the LLM
        formatted_news = []
        for article in articles:
            headline = article.get('headline', 'No Headline')
            description = article.get('description', 'No Description')
            link = article.get('links', {}).get('web', {}).get('href', '#')
            formatted_news.append(f"Headline: {headline}\nSummary: {description}\nLink: {link}\n")
            
        return "\n---\n".join(formatted_news)

    except requests.exceptions.RequestException as e:
        return f"Error fetching news from ESPN API: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to parse JSON response from ESPN API."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent

# Initialize Tavily Search Tool
tavily_search_tool = TavilySearch(
    max_results=5,
    topic="general",
)

search_agent = create_react_agent(llm, [tavily_search_tool, espn_tool],
                                  prompt="""You are a sports analyst agent. You are given a question about sports news.
perform the following steps:
    - firstly search for the question in web using tavily search tool
    - answer question based on the information obtained
Note:
    call espn_tool tool using leauge name and sport name gathered from search.
give detailed answer, ignore error and give answer based on the information gathered like summary of the information""")

