# omalink

Pick URLs you can see, without reaching for the mouse.

**Super+U** captures the focused monitor and opens a centred, theme-aware Omarchy panel. Select a URL with **j/k** or **↓/↑**, press **Enter** to open it in Chrome, or **Esc** to dismiss. Mouse selection also works.

The screenshot is taken before the picker appears. Tesseract performs local OCR; no screenshot or extracted text is uploaded. Captures live in `$XDG_RUNTIME_DIR/omalink` and are deleted after OCR. The clipboard is not changed. A later invocation removes captures older than five minutes left behind by interrupted processes.

Chrome's most recently focused normal browser window is focused before opening a new tab. Chrome's own single-instance handling reuses the running browser or starts it when absent. No profile flags are overridden.

## Commands

```sh
omalink capture
omalink demo
omalink extract 'See https://example.com/docs and github.com/rickhallett/omatag'
omalink open https://example.com
```

The backend accepts HTTP(S) URLs and existing local image paths/file URLs. Local images open in Chrome through encoded `file://` URLs. It removes duplicates and surrounding punctuation, preserves query strings, repairs spacing around `https://`, and recognises `www` and common bare-domain endings. It skips addresses containing visible ellipses. Arbitrarily wrapped or OCR-misread URLs may still be incomplete: inspect the full displayed address before opening it. Link text whose destination is hidden cannot be recovered from pixels.

## Implementation

Python 3, `grim`, Tesseract with English data, Hyprland, Chrome and Omarchy's native QML components. The panel uses the same theme tokens as Omarchy's status popups. Screen capture and OCR are separate from the desktop UI; the panel remains responsive during extraction. Repeated invocations while OCR is active retain the in-flight scan.

Installed plugin: `~/.config/omarchy/plugins/ms02.omalink/`. Installed command links to this checkout. Shortcut is a labelled line in `~/.config/hypr/bindings.lua`.

```sh
python3 -m unittest discover -v
omarchy plugin validate plugin
```

Twelve tests cover extraction, punctuation, deduplication, scheme spacing, truncation, accepted schemes, capture-path ownership and argument-safe Chrome dispatch. A real OCR fixture recovered two complete URLs and deleted its capture. The central panel and j-navigation were visually verified; Chrome handoff opened an Example Domain tab in the existing browser. Launching from a fully stopped Chrome session was not tested to avoid closing existing windows.

`plugin/LinkPopup.qml` derives from Omarchy's `Ui/KeyboardPanel.qml`, with central placement for a standalone panel. Upstream MIT terms are retained in LICENSE.

When OCR sees a label such as `[Image #1]` without its destination, omalink offers up to five recently generated images from `$CODEX_HOME/generated_images` (default `~/.codex/generated_images`). The panel explicitly identifies these as candidates, not an exact label-to-file mapping. Visible absolute paths, quoted paths with spaces, `~/` paths and `file://` image URLs are extracted directly when the files exist.
