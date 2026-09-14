# Omalink performance experiments — 14 September 2026

All four strategies were implemented and exercised on MS-02 Ultra: direct application text, focused-window OCR, OCR thread tuning, and reuse of identical captures. Existing user browser/terminal processes were left running.

## Controlled OCR comparison

`ocr_matrix.py` froze one 3440×1440 monitor image, cropped the focused terminal from the same pixels, and ran three samples per setting. English, PSM 11, OEM 1, 150 DPI were held constant. Every sample recovered the same single URL (identical result hashes). This is a controlled latency comparison, not a broad OCR accuracy benchmark.

| Scope | Thread limit | Median elapsed | Median CPU time |
|---|---:|---:|---:|
| Monitor | Unset, original default | 7.309 s | 12.327 s |
| Monitor | 1 | 4.853 s | 4.845 s |
| Monitor | 2 | 6.648 s | 7.734 s |
| Monitor | 4 | 7.398 s | 12.387 s |
| Window | Unset | 3.218 s | 5.558 s |
| Window | **1, selected default** | **2.010 s** | **2.007 s** |
| Window | 2 | 2.782 s | 3.319 s |
| Window | 4 | 3.180 s | 5.537 s |

The selected combination reduced OCR elapsed time by **72.5%** and CPU time by **83.7%** relative to the original configuration on this sample. Whole-monitor mode remains available explicitly.

PNG compression was a separate avoidable cost: level 6 took 249 ms median versus 56 ms at level 0. The latter uses roughly 14.9 MB rather than 1.3 MB temporarily in runtime storage. No resizing or accuracy-reducing preprocessing was needed. Raw results: [ocr-results.json](ocr-results.json).

## Direct text and caching

| Experiment | Measured result | Correctness check |
|---|---|---|
| Foot visible-text pipe | 42.51 / 42.31 / 41.71 ms | Both fixture URLs, no clipboard use |
| Foot capture pipeline | 71 ms to result/summon preparation | Native panel contained both links |
| Chrome accessibility, including fresh Python process | 72.03 / 70.70 / 70.49 ms | Printed URL, labelled hidden href, shadow DOM link |
| Chrome capture pipeline | 104 ms to result/summon preparation | Native panel contained all three links |
| Cache, 1701×1390 two-URL synthetic fixture | 143.90 ms cold; 0.20 / 0.13 / 0.12 ms cached | Identical expected URLs; capture deleted |
| Cache through native panel, dense synthetic fixture | 1338 ms cold; 11 ms cached | Both include a synthetic 10 ms capture-duration argument |

Pipeline times shown by the footer exclude the final panel animation and subsequent keyboard selection. Cache lookup figures exclude the next real screenshot and its fade delay. Actual cache hit frequency was not measured: blinking cursors, videos and any changed pixels cause misses.

A final live-screen fallback check exercised both routes through the real picker: window capture-to-ready took 502 ms and monitor capture-to-ready 1873 ms on the then-current, less text-dense screen. These are functional checks, not comparable to the frozen baseline.

## Browser strategy decision

An unpacked Chrome extension was prototyped, but current branded Chrome ignored the `--load-extension` launch flag. Chromium's [official removal announcement](https://groups.google.com/a/chromium.org/g/chromium-extensions/c/1-g8EFx2BBY) confirms that support was removed in Chrome 137. Browser automation also blocked the extensions settings URL, so that route was not pursued. The experimental flag and native-messaging installation were removed.

The selected implementation uses Chrome's native Linux accessibility interface. Chromium [documents the accessibility model](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/accessibility/overview.md), and its [AT-SPI test harness uses `ACCESSIBILITY_ENABLED`](https://chromium.googlesource.com/chromium/src/+/9360d08502357e2ea00f4f052bb6a8ca9277e27a/chrome/test/fuzzing/atspi_in_process_fuzzer.cc). The local Chrome launcher combines that environment setting with `--force-renderer-accessibility`. No global screen-reader setting was changed.

The test used an isolated Chrome profile and a localhost fixture. Offscreen, `display:none`, and editable-field URLs were excluded. The bridge reads the active frame, uses document bounds, and stops at time/node/text budgets. An unavailable or over-budget bridge falls back to OCR. Semantic accessibility visibility can differ from actual pixels for occluded/transparent content or partially clipped text. Browser-wide overhead from retaining the accessibility tree has not been quantified; this is the main remaining measurement limitation.

## Verification

- 25 automated tests pass: extraction, safe URL dispatch, local images, same/changed/expired/corrupt caches, capture deletion on failure, content-free metric permissions, scaled/rotated/clipped geometry, mutually exclusive grim capture options, request correlation, timeout cleanup, and hidden destinations supplied as text.
- Real Foot and Chrome smoke tests verified source extraction and populated the real QML panel.
- Real QML IPC tests passed: cold OCR, identical capture reuse, stale OCR cannot replace newer direct results, the latest queued capture wins, closing during OCR does not reopen the panel.
- Both window and monitor capture paths were exercised. The final panel was visually inspected in the active Omarchy theme.
- Plugin validation, desktop-file validation, Foot configuration validation, Hyprland configuration validation, and Git whitespace checks passed.
- Opening a URL uses the previously verified Chrome handoff, retained by this change. Existing user Chrome was not shut down to retest the cold browser launch case.

Defaults are window scope, one OCR thread, 30-second exact-image cache, and direct text enabled. New Foot processes and the next ordinary Chrome process load their bridges; existing processes immediately benefit from the OCR improvements.
