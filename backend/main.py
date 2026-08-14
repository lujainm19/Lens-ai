"""
Lens backend — the Chrome extension talks only to this server, never
directly to an LLM provider. This keeps any API key off the client and
gives you one place to swap providers.

Run locally with: uvicorn main:app --reload
Requires Ollama running locally with `ollama pull llama3.2` done first
(https://ollama.com) if using the local provider.
"""

import os  # lets us read environment variables, like which AI provider to use
from fastapi import FastAPI  # the web framework that turns this file into a running server
from fastapi.middleware.cors import CORSMiddleware  # lets the Chrome extension (a different "origin") talk to this server
from pydantic import BaseModel  # used to define the exact shape of data we expect to receive

import requests  # simple, well-known library for making HTTP calls (used to call Tavily's API)
from dotenv import load_dotenv  # reads variables out of the .env file

load_dotenv()  # actually loads .env into the environment when the app starts

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")  # reads the Tavily API key, now safely from .env, not hardcoded




app = FastAPI()  # creates the actual server application

# Extensions run from a chrome-extension:// origin, browsers normally block a webpage/extension from calling a server on a different origin unless
# that server explicitly allows it. This middleware allows it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" means allow any origin, fine for local dev, tighten before publishing
    allow_methods=["POST"],  # we only need to allow POST requests (that's all sidepanel.js sends)
    allow_headers=["*"],  # allow any request headers
)

# Reads an environment variable called LLM_PROVIDER; if it's not set, defaults to "ollama"
# This is the "swap providers in one place" design (change this one value to switch AI backends)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")


# Defines the exact shape of the "context" object the extension sends. FastAPI will automatically reject requests that don't match this shape
class PageContext(BaseModel):
    title: str          # the page's title
    url: str             # the page's URL
    selectedText: str    # highlighted text, or empty string
    pageText: str        # the page's visible text


# Defines the shape of the full request body: a question plus the context above
class AskRequest(BaseModel):
    question: str
    context: PageContext


# Turns the question + context into a single text prompt to send to the AI model
def build_prompt(req: AskRequest, sources: list[dict]) -> str: # this function now takes a second argument: the list of search results (can be empty)

    focus = req.context.selectedText or req.context.pageText
    # this use selectedText if it's selected, otherwise all pageText

    sources_text = "" # start with an empty string, if there are no sources, nothing extra gets added to the prompt

    if sources: # this block only runs if the sources list actually has something in it
        sources_text = "\n\nWeb sources found:\n" + "\n".join(
            f"- {s['title']} ({s['url']}): {s['snippet'][:300]}"
            # builds one line per source
            # [:300] slices the string down to its first 300 characters, so not overloading the prompt
            for s in sources # loop over every source dict in the list
        )
        # "\n".join(...) glues all those lines together with newlines between them

    return (
        f"Page: {req.context.title} ({req.context.url})\n\n" # tells the model which page this question is about

        f"Relevant content:\n{focus}" # gives the model the actual text to read (selected text or full page)

        f"{sources_text}\n\n" # inserts the web sources block we built above, empty string if there were none

        f"Question: {req.question}\n\n" # the user's literal question

        "Answer using the page content and, if provided, the web sources "
        "above. If you use a web source, cite it by name with its URL. "
        "If you're unsure or don't have enough information, say so clearly "
        "rather than guessing."
        # instructions/ prompt telling the model how to answer (cite sources, don't make things up)
    )


def search_web(query: str) -> list[dict]:
    """Searches the web via Tavily and returns a short list of results with
    titles, URLs, and snippets — these become the 'sources' Lens can cite."""
    if not TAVILY_API_KEY:
        return []  # if no key is set, just skip search instead of crashing

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": 4,  # this caps the results to 4, keeping it small and short (just need a few good sources, not 20)
        },
    )
    data = response.json()  # .json() converts Tavily's raw response text into a Python dictionary we can work with
    return [
        {"title": r["title"], "url": r["url"], "snippet": r["content"]} # for each result Tavily gave us, keep only the 3 fields we actually need
        for r in data.get("results", []) # .get("results", []) means: use data["results"] if it exists, otherwise use an empty list
        # this prevents a crash if Tavily's response is ever malformed or empty
    ]


# Sends the prompt to a LOCAL model running via Ollama (no internet, no API key, $0 cost)
def ask_ollama(prompt: str) -> str:
    import ollama  # imported here (not at the top) so the app still runs even if ollama isn't installed and you're using the cloud path instead
    response = ollama.chat(
        model="llama3.2",  # the local model you downloaded with `ollama pull llama3.2`
        messages=[{"role": "user", "content": prompt}],  # same message format as most chat APIs
    )
    return response["message"]["content"]  # pull just the text answer out of Ollama's response object


# Sends the prompt to Anthropic's cloud API instead (higher quality, costs money, needs an API key)
def ask_anthropic(prompt: str) -> str:
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()  # automatically reads the ANTHROPIC_API_KEY environment variable — never hardcode a key in code
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,  # caps how long the answer can be
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text  # pull the text out of Claude's response object


# This is the actual API endpoint — sidepanel.js calls POST http://localhost:8000/ask
@app.post("/ask")
def ask(req: AskRequest):
    needs_search = any(
        phrase in req.question.lower() # .lower() converts the question to lowercase so "True" and "true" both match
        for phrase in ["true", "who is", "more about", "verify", "fact", "accurate", "real"] # checks if any of these words/phrases appear anywhere in the question
    )# any(...) returns True the moment ONE of these checks matches, otherwise False

    search_query = f"{req.context.title} {req.question}"  # combine the page's topic with the question so Tavily has real context
    sources = search_web(search_query) if needs_search else []
    # only call Tavily (and use a search credit) if the question seems like it might need a fact check or extra sources; otherwise, skip the search and return an empty list

    prompt = build_prompt(req, sources)  # to build the final prompt text, now including sources if there are any

    if LLM_PROVIDER == "anthropic":
        answer = ask_anthropic(prompt)
    else:
        answer = ask_ollama(prompt)

    return {"answer": answer, "sources": sources}
    # now returns both the answer text and the raw list of sources, the extension can use "sources" later to render clickable links



# This file is the actual "brain" of Lens: a small server that receives the question + page context from your extension, 
# builds a prompt, sends it to an AI model (Ollama running locally, or a cloud API if you switch it), and sends the answer back. 
# This is also where the API key (if using a cloud provider) stays hidden, so the extension never talks to an AI provider directly.
# The extension never contacts an AI provider on its own, it only ever calls this backend, which builds a proper prompt, asks the model, and hands back a plain answer.
# Keeping this separate is also what makes the "swap between free local AI and a paid cloud AI" trick possible with a single setting.




# An origin is basically "where a request is coming from," defined by the combination of protocol + domain + port. So:
# https://google.com is one origin and http://localhost:8000 is a different origin (different protocol)
# chrome-extension://ppnlbjcgkiclmjlcmplbijbjodfddfce (the Lens extension's ID) is yet another origin
# By default, browsers block a page/extension on one origin from making requests to a server on a different origin

# here sidepanel.js runs from the extension's own origin (chrome-extension://...), but it needs to call the backend at http://localhost:8000.
# Those are different origins, so without permission, Chrome would block the request entirely 
# so CORSMiddleware in main.py is the backend explicitly saying "it's fine, I'll accept requests from other origins." Right now it's set to allow_origins=["*"] (accept from anywhere)


# Why the extension talks to your backend, not the AI directly.  like a restaurant. You (the extension) don't walk into the kitchen and cook your own food
# you tell the waiter (your backend) what you want, and the waiter deals with the kitchen (the AI model)


# Local (Ollama) vs. cloud (Anthropic/API): This is about where the actual AI thinking happens, not about the waiter/kitchen structure above — both options still go through your backend.
# Ollama = the AI model runs on own laptop. No internet needed for the AI part, no cost, nothing about the page content ever leaves your machine. Downside: quality is a bit lower than the big cloud models, and it uses your laptop's own CPU/RAM to "think," so it can be slower.
# Anthropic (cloud API) = the backend sends the prompt over the internet to Anthropic's servers, which run a much bigger, smarter model, and send back an answer. Downside: costs money per request, needs an API key, and the page content technically leaves your machine (even though it's just for that one request, not stored).
# main.py has both ask_ollama() and ask_anthropic() functions, and the LLM_PROVIDER setting picks which one actually gets used. So the "kitchen" in the analogy can be either your own stove (Ollama, local) or a restaurant supplier you call up (Anthropic, cloud) — but you, the extension, always just talk to the one waiter (your backend) either way, and don't need to know or care which kitchen is being used behind the scenes.





# fastapi — the web framework that runs the /ask endpoint
# uvicorn — the actual server program that runs FastAPI (FastAPI defines what to do, uvicorn is what runs it)
# pydantic — powers the PageContext/AskRequest data validation classes in main.py
# ollama — the Python library that lets main.py talk to the local Ollama installation
# anthropic — only needed if you switch LLM_PROVIDER to "anthropic" later; harmless to have installed either way
