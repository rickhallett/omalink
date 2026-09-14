# omalink

Pick visible links from the keyboard, including destinations hidden behind browser link labels.

**Super+U** reads the focused window and opens a centred, theme-aware Omarchy panel. Select with **j/k** or **↓/↑**, **Enter** opens in Chrome, **Esc** closes. **Super+Shift+U** scans the whole focused monitor instead.

Omalink first reads Foot's visible text or Chrome's native accessibility tree. Other applications use local Tesseract OCR. Exact repeat screenshots reuse a short-lived result cache. Python coordinates the work; the expensive pixel recognition runs in Tesseract's native engine.

On this machine, the direct paths reached the summon stage in **71 ms for Foot** and **104 ms for Chrome**, before the panel's own animation. On a frozen desktop sample, focused-window OCR with one thread took **2.01 s**, compared with **7.31 s** for the original full-monitor/default-thread OCR. These are measured samples, not latency guarantees. See [the experiment report](benchmarks/RESULTS.md).

## Behaviour

- Foot uses `pipe-visible`, without changing the clipboard or reading scrollback.
- Chrome uses AT-SPI, restricted to the active browser frame's visible web document. It reads link destinations, including labelled links and links exposed from shadow DOM. Editable fields are skipped. Offscreen and `display:none` fixture links were excluded. Accessibility visibility is semantic: occlusion, transparent elements, and partly clipped text can differ from pixel visibility.
- A missing, failed or slow text provider falls back to OCR. Chrome accessibility runs in a separate process with a 650 ms limit; traversal has a smaller time/node budget. A responsive provider without links also falls back, allowing links in images or browser UI to be found.
- OCR captures the window at its monitor's scale. Whole-monitor mode deliberately bypasses the text bridges. One Tesseract thread was fastest in the measured matrix.
- The footer shows the source and processing time. Launching again keeps the latest request; old OCR cannot overwrite newer direct results. Closing during OCR does not reopen the picker.

Chrome's most recently focused normal window is focused before opening a new tab. Chrome's single-instance handling reuses the running browser or starts one if absent. Existing profiles and sessions are preserved.

## Current installation

The command `~/.local/bin/omalink` links to this checkout. The native QML plugin is installed at `~/.config/omarchy/plugins/ms02.omalink/`, with shortcuts in `~/.config/hypr/bindings.lua`. The panel uses Omarchy's standard theme tokens and responds to theme changes.

`/usr/bin/python3 install_integrations.py` installs the text bridges while preserving existing settings:

- Foot gets an `Alt+Shift+U` visible-text pipe. It takes effect in **new Foot processes**.
- A local `google-chrome.desktop` override routes ordinary Chrome launches through `~/.local/share/omalink/bin/google-chrome-stable`. That wrapper enables Chrome's native accessibility interface. It takes effect when the **next Chrome process starts**, not merely when an existing process opens a new window.
- Existing Foot/Chrome processes retain the faster OCR fallback. Installation does not close either application.

The Chrome bridge requires system Python's PyGObject and the AT-SPI typelib. They are available on this installation. Enabling Chrome's accessibility tree has some browser-side processing/memory cost; whole-browser overhead has not been benchmarked. No extension, remote debugging port, background screenshot polling, or additional omalink daemon is installed.

## Configuration and commands

`~/.config/omalink/config.json`:

```json
{"scope":"window","threads":1,"cache_ttl_s":30,"direct":true}
```

`scope` can be `window` or `monitor`; threads can be 1, 2 or 4. Cache lifetime is capped at 300 seconds; zero disables it. `direct: false` skips text providers. Configuration is read on each invocation.

```sh
omalink capture
omalink capture --monitor
omalink demo
omalink extract 'See https://example.com/docs and github.com/rickhallett/omatag'
omalink open https://example.com
omarchy-shell omalink status
```

The backend accepts HTTP(S) URLs and existing local image paths/file URLs. Local images open in Chrome through encoded `file://` URLs. It deduplicates URLs, trims surrounding punctuation, preserves query strings, repairs scheme spacing, and recognises `www` and common bare-domain endings. Truncated addresses are skipped; OCR errors or arbitrary line wrapping can still produce incomplete URLs.

When an unresolved `[Image #N]` label appears, up to five recent images from `$CODEX_HOME/generated_images` are offered as explicitly labelled **candidates**, not an exact label-to-file mapping. Foot's plain text pipe generally does not expose hidden hyperlink destinations. Existing visible local paths and image file URLs are extracted directly.

## Local data

Screenshots live temporarily under `$XDG_RUNTIME_DIR/omalink` and are deleted after OCR. A later invocation removes captures older than five minutes left by interrupted processes. The cache stores extracted URLs and an image-label flag, never full OCR text or screenshots; expired entries are pruned on the next OCR call. It retains approximately 16 entries in a private runtime directory. Changing even one pixel causes a cache miss.

`timings.jsonl` in the same runtime directory contains only source, duration, capture duration and link count. It is size-bounded and contains no URLs, paths, titles or extracted text. Nothing is uploaded; the clipboard remains unchanged.

## Verification and rollback

```sh
/usr/bin/python3 -m unittest discover -v
omarchy plugin validate plugin
/usr/bin/python3 benchmarks/direct_smoke.py
/usr/bin/python3 benchmarks/accessibility_smoke.py
/usr/bin/python3 benchmarks/cache_smoke.py
/usr/bin/python3 benchmarks/panel_smoke.py
```

The desktop smoke tests briefly open disposable test windows/panels and close only those they create. The OCR matrix additionally samples the visible screen; screenshots and text stay in temporary runtime storage, with only timings/counts/result hashes retained. See [results and limitations](benchmarks/RESULTS.md).

For a quick OCR-only mode, set `direct` to `false`. To remove the browser-side accessibility cost on future launches, restore/remove this installation's local `google-chrome.desktop` override and remove the omalink browser wrapper. Remove the labelled `pipe-visible` line from Foot's config to remove its bridge. Existing configuration edits have timestamped `.bak-omalink-*` backups; restore only the relevant lines when later customizations exist. Returning to full-monitor/default-thread behaviour is possible from the baseline Git checkpoint `697623c`, but that checkout alone does not undo external configuration edits.

`plugin/LinkPopup.qml` derives from Omarchy's `Ui/KeyboardPanel.qml`, with central placement. Upstream MIT terms are retained in LICENSE.
