# Writing Assistant Browser Extension

This is the first browser-side bridge and popup for Writing Assistant.

## Install for local testing

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Click "Load unpacked".
4. Select this `browser_extension` folder.
5. Start Writing Assistant with realtime recognition enabled if you want to use the desktop AI correction flow.
6. Click a web text field, then click the Writing Assistant extension icon.
7. Open DevTools Console on the page to see the selected editor debug log.

The content script still sends focused browser editor text to `http://127.0.0.1:8766/capture`.
The popup can also call `http://127.0.0.1:8766/correct` for desktop correction. If the desktop app is not running, it falls back to a small local dummy correction.

## Current scope

- `input[type="text"]` and `textarea`: reads text and selection offsets, replaces selected text.
- `input[type="search"]` and `input[type="email"]`: reads text and selection offsets.
- `contenteditable`: reads selected text, HTML fragment, and basic computed CSS segments.
- `role="textbox"` and editor-like fields with labels/placeholders such as compose, message, body, 글쓰기, 내용, 본문, 메시지.
- Gmail and cafe-style editors are detected with stronger candidate scoring, but Copy is still the stable fallback for complex sites.
- Popup: get focused text, show correction result, copy result, and best-effort apply result.
- Rich replacement is still plain text in this first pass. The captured style segments are already sent to the desktop app for the next implementation step.

## Why this exists

Desktop UI Automation can often read browser text, but it cannot reliably see DOM/CSS styles. The content script runs inside the page, so it can use `Selection`, `Range`, and `getComputedStyle()`.
