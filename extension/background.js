// Lens background service worker
// This file does not run on every page load — it only wakes up when the user clicks the extension icon or triggers the right-click menu.
// No background monitoring of tabs happens here.

chrome.action.onClicked.addListener(async (tab) => {
  // "tab" is the webpage the user was on when they clicked the icon (the tab user is currently viewing)
  // We open the side panel for that specific tab.
  await chrome.sidePanel.open({ tabId: tab.id });
});

// This runs once, when the extension is first installed (not on every page load). It registers a right-click menu item that only shows up
// when the user has text selected on a page.
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "ask-lens",
    title: "Ask Lens about this",
    contexts: ["selection"] // only appears when text is highlighted
  });
});


// Runs when the user clicks "Ask Lens about this" in the right-click menu
chrome.contextMenus.onClicked.addListener((info, tab) => {
  // no longer "async" at the top level, sidePanel.open() needs to run
  // immediately, synchronously, as the direct response to the click, or Chrome may not recognize it as a valid user-triggered action
  if (info.menuItemId !== "ask-lens") return;

  chrome.sidePanel.open({ tabId: tab.id });
  // called 1st, with no await before it, so it fires the instant the click happens. this is what Chrome actually requires

  chrome.storage.local.set({ pendingQuestion: info.selectionText });
  // storing the highlighted text can safely happen after, the panel opening doesn't depend on this finishing first
});


//chrome.action.onClicked — this activates the moment you click the Lens toolbar icon. It's an event listener: the code inside only runs in response to that click, not on a timer or continuously.
//chrome.sidePanel.open({ tabId: tab.id }) — tells Chrome "open the side panel, and attach it to this specific browser tab." await is used because opening the panel is an asynchronous operation (it takes a moment, and JavaScript doesn't want to block while waiting).
//chrome.runtime.onInstalled — a separate event that fires once, when you first load the extension (or when it updates). It's the right place to set up one-time things like menu items — you don't want to recreate the context menu every single time someone clicks the icon.
//chrome.contextMenus.create(...) — registers a new item in Chrome's right-click menu. contexts: ["selection"] means it only appears when the user has highlighted text — this is intentional scoping, so the menu item doesn't clutter every right-click.