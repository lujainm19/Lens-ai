// Lens side panel logic
// Page context is captured only when the user clicks "Ask" — never on load, never in the background. Context is sent to our own backend (never a third-party LLM API directly), and nothing is persisted server-side.

const BACKEND_URL = "http://localhost:8000/ask"; // will swap for the deployed backend later

// to reference the HTML elements defined in sidepanel.html, so we can read/update them from JS
const statusEl = document.getElementById("status");   // the small text line showing what Lens is currently doing
const messagesEl = document.getElementById("messages"); // the scrollable box where chat bubbles get added
const questionEl = document.getElementById("question"); // the text input box where you type your question
const askBtn = document.getElementById("askBtn");       // the "Ask" button

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
      body: JSON.stringify({ question, context })  // converts the question + context object into a JSON string to send
    });

    const data = await res.json();          // parses the backend's response body as JSON
    addMessage(data.answer ?? "No answer returned.", "lens"); // show the answer, fall back to a message if "answer" is missing
  } catch (err) {
    // this block runs if fetch() itself fails  e.g. the backend isn't running yet
    addMessage("Something went wrong reaching the backend.", "lens"); // show a friendly error in the chat
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

//listens for your question, grabs the current page's content at that exact moment (nothing before, nothing after), 
// sends both to your backend, and shows the reply. Everything about when data leaves your browser is controlled right here (privacy is controlled here)