# Privacy Policy — Lens

Last updated: August 2026

## The core principle

Lens only sees what you explicitly ask it to see. There is no background
monitoring, no passive reading of pages, and no tracking of your browsing.

## What Lens accesses, and when

Lens only reads page content at the exact moment you ask a question never on page load, never continuously, never in the background.

When you ask a question, Lens may read:
- The current page's title and URL
- Text you've highlighted (if any)
- The page's visible text (if no text is highlighted)
- A screenshot of the visible browser window *(V2 — only when you
  explicitly trigger the "Analyze this page" action)*

Lens does **not** access:
- Browsing history
- Cookies or login sessions
- Passwords or form inputs
- Data from tabs other than the one you're actively asking about
- Anything on a page before you've clicked the Lens icon on that tab

## Why access is limited to `activeTab`

Lens requests Chrome's `activeTab` permission rather than broad access to
all websites. This means Lens can only read a page after you've actively
clicked its icon (or used "Ask Lens" on selected text) on that specific
tab. The tradeoff: if you switch to a new tab, you'll need to click the
Lens icon again before asking, but this is intentional, not a bug, and it's
what keeps Lens from being able to read pages you haven't invited it into.

## What happens to your data

- **Page content and your question** are sent to Lens's own backend
  server over HTTPS, which then sends them to an AI model to generate an
  answer.
- **By default, this AI model runs locally** on your own machine via
  Ollama — meaning page content never leaves your computer in that mode.
- **If configured to use a cloud AI provider** instead, page content is
  sent to that provider for the single request needed to answer your
  question, and not stored by Lens afterward.
- **If your question needs a web search** (e.g. fact-checking, "who is
  X"), your question — not your page content — is sent to a search
  provider (Tavily) to retrieve relevant sources.
- **Nothing is stored on the backend.** Page content, screenshots, and
  questions are used only for the single request and then discarded —
  there is no database, no logging of page content, and no analytics.
- **Conversation history** (your recent questions and Lens's answers) is
  kept only in the side panel's memory for your current session. It is
  never written to disk and disappears when you close the panel or
  reload it.

## API keys

If Lens is configured to use a paid cloud AI provider, that provider's
API key is stored only on the backend server (via an environment
variable) and is never included in the extension itself — so it can't be
extracted by inspecting the extension's code.

## Screenshots (V2)

Screenshot analysis is never automatic. It requires an explicit click on
an "Analyze this page" action, and the side panel shows a visible
indicator whenever Lens is actively reading page content or a screenshot,
so it's always clear what Lens currently has access to.

## Questions

This is a student portfolio project, not a published product. If Lens is
ever published to the Chrome Web Store, this policy will be updated to
match its actual published data practices at that time.