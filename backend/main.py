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
def build_prompt(req: AskRequest) -> str:
    # prefer the highlighted text if there is any, otherwise use the whole page's text
    focus = req.context.selectedText or req.context.pageText
    return (
        f"Page: {req.context.title} ({req.context.url})\n\n"  # tell the model what page this is
        f"Relevant content:\n{focus}\n\n"                       # give it the actual content to read
        f"Question: {req.question}\n\n"                          # the user's actual question
        "Answer using only the page content above unless you need to say "
        "you're unsure."  # instruction so the model doesn't just make things up
    )


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
def ask(req: AskRequest):  # FastAPI automatically parses the incoming JSON into an AskRequest object
    prompt = build_prompt(req)  # turn the question+context into one prompt string

    if LLM_PROVIDER == "anthropic":  # check which provider is configured
        answer = ask_anthropic(prompt)
    else:
        answer = ask_ollama(prompt)  # defaults to local/free

    # Context is used for this single call only. nothing is stored here, no database, no file write, no logging of page content.
    return {"answer": answer}  # FastAPI automatically converts this dict into a JSON response

# This is the actual "brain" of Lens: a small server that receives the question + page context from your extension, 
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
