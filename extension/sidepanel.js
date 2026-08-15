// Lens side panel logic
// Page context is captured only when the user clicks "Ask" — never on load, never in the background. Context is sent to our own backend (never a third-party LLM API directly), and nothing is persisted server-side.

const BACKEND_URL = "http://localhost:8000/ask"; // will swap for the deployed backend later

// to reference the HTML elements defined in sidepanel.html, so we can read/update them from JS
const statusEl = document.getElementById("status");   // the small text line showing what Lens is currently doing
const messagesEl = document.getElementById("messages"); // the scrollable box where chat bubbles get added
const questionEl = document.getElementById("question"); // the text input box where you type your question
const askBtn = document.getElementById("askBtn");       // the "Ask" button

// Runs once when the side panel loads/opens, checks if a highlight-to-ask action just happened, and if so automatically sends that question
async function checkForPendingQuestion() {
  const { pendingQuestion } = await chrome.storage.local.get("pendingQuestion");
  // reads whatever background.js may have stashed, undefined if nothing's there

  if (pendingQuestion) {
    questionEl.value = `Explain this: "${pendingQuestion}"`;
    // pre-fills the input box with a natural question wrapping the highlighted text

    await chrome.storage.local.remove("pendingQuestion"); // clears it immediately so it doesn't get reused if the panel reloads later

    askLens(); // automatically send it (no need for the user to also click "Ask")
  }
}

checkForPendingQuestion();// call this once right when the panel's script loads



// keeps track of the conversation so far in this session, so follow-up questions make sense
// lives only in memory, clears if you close the panel or reload, nothing saved to disk
// each entry looks like: { question: "...", answer: "..." }
let conversationHistory = [];

// Adds one chat bubble to the message list
function addMessage(text, who) {
  const div = document.createElement("div");     // create a new empty <div> element in memory (not on screen yet)
  div.className = `msg ${who}`;                   // give it CSS classes "msg user" or "msg lens" so it's styled correctly
  div.textContent = text;                         // put the actual message text inside the div
  messagesEl.appendChild(div);                    // attach the div to the messages container so it becomes visible
  messagesEl.scrollTop = messagesEl.scrollHeight; // automatically scrolls to the bottom so the newest message is visible
}

// Captures context from the current page only, and only called at the moment of asking, never automatically
async function getPageContext() {
  // ask Chrome which tab is currently active and focused
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  // chrome.tabs.query returns an array (even though there's only  one active tab)

  // this runs a function inside that tab's webpage and gets back whatever it returns
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },  // tells Chrome which tab to run the function in
    func: () => ({               // this whole function actually executes inside the webpage, not the extension
      title: document.title,                              // the page's <title> text
      url: location.href,                                 // the full current URL
      selectedText: window.getSelection().toString(),      // whatever text the user has highlighted, or "" if nothing
      pageText: document.body.innerText.slice(0, 8000)     // all visible text on the page, capped at 8000 characters so we don't send huge pages
    })
  });
  // executeScript returns an array of results (one per frame); we only care about the first one, and only its "result" property

  return result; // returns the {title, url, selectedText, pageText} object 
}

// The main flow: read the question, grab page context, call the backend, and display the answer
async function askLens() {
  const question = questionEl.value.trim(); // reads whatever the user typed, and strips leading/trailing whitespace
  if (!question) return;                    // if the box was empty, do nothing (no point sending a blank question)

  addMessage(question, "user");             // show the user's own question in the chat as a "user" bubble
  questionEl.value = "";                    // clear the input box so it's ready for the next question
  statusEl.textContent = "🟢 Reading the current page..."; // update the status line so the user sees Lens is now active

  try {
    const context = await getPageContext(); // actually capture the page content NOW, at the moment of asking

    const res = await fetch(BACKEND_URL, {        // sends an HTTP request to your backend
      method: "POST",                              // POST because we're sending data, not just requesting a page
      headers: { "Content-Type": "application/json" }, // tells the backend the body is JSON
      body: JSON.stringify({
        question,
        context,
        history: conversationHistory  // sends everything asked so far in this session, so the backend can understand follow-ups
      })
    });

    const data = await res.json();          // parses the backend's response body as JSON
    addMessage(data.answer ?? "No answer returned.", "lens"); // show the answer, fall back to a message if "answer" is missing

    // remembers this exchange so the NEXT question can reference it as a follow-up
    conversationHistory.push({ question, answer: data.answer });

  } catch (err) {
    // this block runs if fetch() itself fails, OR if getPageContext() throws before we even get to fetch
    // checks specifically for Chrome's activeTab permission error, which happens when you switch tabs
    // without re-clicking the Lens icon there first (activeTab only grants access per-tab, on click)
    if (err.message && err.message.includes("Cannot access contents")) {
      addMessage(
        "Click the Lens icon on this tab first, then ask again — Lens only reads a page after you've actively opened it there.",
        "lens"
      );
    } else {
      addMessage("Something went wrong reaching the backend.", "lens"); // show a friendly error in the chat for any other failure
    }
    console.error(err); // log the real error to the browser console for debugging
  } finally {
    // the finally block runs whether the try succeeded or the catch triggered
    statusEl.textContent = "🔒 Lens hasn't read this page yet — ask a question to begin."; // resets the status line back 
  }
}

// Connect the UI events to the askLens() function above
askBtn.addEventListener("click", askLens); // clicking the "Ask" button triggers askLens
questionEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") askLens();        // pressing Enter in the input box also triggers askLens, like a normal chat app
});

// this filelistens for your question, grabs the current page's content at that exact moment (nothing before, nothing after), 
// sends both to your backend, and shows the reply. Everything about when data leaves your browser is controlled right here (privacy is controlled here)
// conversationHistory is what makes follow-up questions possible — it's the only thing "remembered" between questions,
// and it only lives in this tab's memory, never written to disk or sent anywhere except back to your own backend

