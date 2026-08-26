---
name: qt-python-ui-testing
description: |
    Use when writing or reviewing GUI tests for a Qt app (accessed through the qtpy abstraction layer) that need to simulate real mouse/keyboard interaction and capture what actually rendered (screenshots), instead of only instantiating a widget and asserting its properties. Also applies when a test must run headless/CI.
    Do not use for pure logic/model tests with no UI interaction, property-only smoke tests, or web UI testing.
allowed-tools: Bash(uv *)
---

# Qt GUI Testing

## Overview

Existing tests in `tests/` (e.g. `test_toolbar.py`) construct a widget and assert
its properties — they never simulate a click or verify what rendered. This skill
drives widgets with real Qt input events via `QtTest.QTest` and captures the
result with `widget.grab()`, closer to a Playwright-style interaction test than a
constructor smoke test.

All Qt imports go through **qtpy**, the Qt API abstraction layer over whichever
binding is installed — never import a concrete binding directly in tests or
helpers. The project already lists `qtpy` in `pyproject.toml` and supplies its
chosen binding separately, so code written against qtpy survives a future
binding switch (PyQt5/6, PySide2, or another supported binding).

## When to Use

- A test needs to verify a click/keypress actually does something (opens a menu,
  toggles an action, fires a signal) — not just that the widget exists.
- A test needs visual evidence of what rendered (screenshot per step), e.g. for
  `renderer.py`'s `QRhiWidget`.
- Any of the above must run without a visible window (CI, sandboxed agent).

## When NOT to Use

- Non-widget logic (`scene.py`, `fbx_importer.py`, camera math) — plain pytest,
  no `QApplication` needed.
- Property-only assertions on widgets the test configures directly (the
  existing constructor smoke-test style) — no interaction or rendered pixels
  involved.
- Web/browser UI or non-Qt toolkits — use browser automation tooling, not
  QtTest.
- Video/GIF capture of interactions — out of scope by default; `record_steps()`
  PNG storyboards are the intended substitute. If a video deliverable is
  explicitly requested, see [video-encoding.md](./references/video-encoding.md)
  for a verified ffmpeg recipe rather than adding a video/GIF dependency.

## Core Pattern: Two Launch Modes

The right headless mode depends on whether the widget under test is a GPU
render target (`QRhiWidget`, `QOpenGLWidget`, `QQuickWidget`) or a plain
widget tree:

- **Plain widgets** (buttons, menus, toolbars, trees): run under
  `QT_QPA_PLATFORM=offscreen`.
- **GPU render targets**: run under the real platform plugin and set
  `Qt.WA_DontShowOnScreen` on the top-level window (`widget.window()`, not
  necessarily the render widget itself — see below) before `show()` — the
  offscreen plugin has no native surface, so the RHI backend can never create
  a swapchain.

Both modes still need a windowing session behind the platform plugin (a
logged-in desktop on Windows/macOS, Xvfb on Linux). If the GPU widget is
nested inside a larger window (the common case — a `QMainWindow` with
toolbars/panels around the viewport), `WA_DontShowOnScreen` goes on the
**top-level window**, not the nested widget; see
[headless-modes.md](./references/headless-modes.md) for the verified example,
platform requirements, and a smoke-test recipe to run before scripting a full
interaction sequence.

## Working around modal dialogs

`QFileDialog`, `QMessageBox`, and other modal dialogs block the event loop and
can't be driven through `QTest` the way in-window widgets can. Don't try —
call whatever the dialog's result would have fed into directly, and replicate
the rest of the slot's post-processing:

```python
# Real UI path: toolbar.open_btn.clicked -> QFileDialog.getOpenFileName -> scene.import_fbx(path)
# Automated: skip the dialog, call what it would have fed
scene.import_fbx(str(fbx_path))
outliner.scene = scene
outliner._populate()          # whatever else the slot did after import
renderer.set_scene(scene)
```

This generalizes to any modal Open/Save/confirm dialog: find what the dialog
hands to the rest of the app (a path, a bool, a chosen item) and supply that
value directly instead of trying to automate the dialog.

## Implementation

Reusable helpers: [gui_probe.py](./scripts/gui_probe.py) — `click()`,
`key_clicks()`, `drag()` (click-drag-release gestures — orbit/pan cameras,
sliders, canvases), `wheel()` (synthesized `QWheelEvent`, for Qt/PySide builds
without `QTest.mouseWheel`), `screenshot()`, `record_steps()` (numbered PNG
sequence per interaction step, the closest thing to a recording without
adding a GIF/video dependency).

### Running scripts with uv

The script embeds PEP 723 inline script metadata — the `# /// script` block at
the top of the file:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["qtpy>=2.4.3"]
# [tool]
# [tool.uv]
# required-version = ">=0.12.0"
# ///
```

Executing it through uv resolves these dependencies automatically — no manual
venv or pip install:

```bash
uv run --active ${CLAUDE_SKILL_DIR}/scripts/gui_probe.py
```

`--active` means "prefer the already-active virtual environment over the
project's" (`uv run --help`): if you're running from inside an activated
project venv (the common case — right after `uv sync`), the script's `qtpy`
dependency resolves into *that* persistent venv, picking up whatever Qt
binding the project already has installed. If no venv is active, uv falls
back to its normal ephemeral, cached-per-script environment instead — `qtpy`
alone won't have a real Qt binding to forward to there; see "If qtpy import
fails" below.

Only qtpy is declared, deliberately: qtpy is an abstraction shim over whatever
binding is installed, and these helpers are meant to be copied into a project
that already pins its own binding (supplied by `uv sync`). Hard-coding one
binding here would break portability to projects using another.

### Example

```python
from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

from fbx_view.ui.toolbar import TopToolbar

app = QApplication.instance() or QApplication([])  # QT_QPA_PLATFORM=offscreen for plain widgets
toolbar = TopToolbar()
toolbar.show()
QTest.qWaitForWindowExposed(toolbar)

QTest.mouseClick(toolbar.panel_btn, Qt.MouseButton.LeftButton)
app.processEvents()
assert toolbar.panel_menu.isVisible()  # real popup, not a mocked signal

toolbar.grab().save("panel_menu_open.png")
```

For a `QRhiWidget`, skip `QT_QPA_PLATFORM=offscreen`, set
`Qt.WidgetAttribute.WA_DontShowOnScreen` on the **top-level window** before
`show()` (the widget itself only if it has no parent window — nested is the
common case), and replace `qWaitForWindowExposed` with a few
`processEvents()`/`qWait()` iterations, or just call
`gui_probe.show_hidden_native(widget, app)`, which resolves the top-level
window for you — see [headless-modes.md](./references/headless-modes.md).

## If qtpy import fails

An `ImportError` on `qtpy` (or "no Qt binding found" at runtime) means the
environment has no real Qt binding installed — qtpy is only a shim. Fix it in
this order:

1. Run inside the project environment instead of standalone: sync/activate the
   target project first (`uv sync`); its pinned binding supplies what qtpy
   forwards to.
2. If you must run the script standalone, temporarily add any one binding
   locally for the check (e.g. `uv run --with PySide6 gui_probe.py`) — a local
   diagnostic, not a dependency decision.
3. Never commit a binding-specific dependency into the script metadata or the
   project's pyproject just to make qtpy import — that couples the helper to
   one binding and defeats the abstraction.

## Common Mistakes

- Using `QT_QPA_PLATFORM=offscreen` for a `QRhiWidget` test — the RHI backend
  never initializes; `render()` silently never runs.
- Setting `WA_DontShowOnScreen` on a nested GPU widget instead of the
  top-level window it lives in — the widget has no native surface of its own,
  so the attribute doesn't do what you'd expect. `show_hidden_native()`
  resolves this via `widget.window()`; see
  [headless-modes.md](./references/headless-modes.md).
- Calling `.click()` on the button object directly instead of
  `QTest.mouseClick()` — bypasses the real event queue, so popups/hover states
  that depend on actual mouse events won't trigger.
- Trying to drive a `QFileDialog`/`QMessageBox` with `QTest` — it's modal and
  blocks the event loop. Call the underlying method the dialog's result would
  have fed into instead (see "Working around modal dialogs" above).
- `mousePress()` immediately followed by `mouseRelease()` with no
  `mouseMove()` calls in between, expecting drag behavior — `mouseMoveEvent()`
  only fires from an actual `QTest.mouseMove()` call, not from the press/
  release pair. Use `drag()`.
- Assuming `QTest.mouseWheel` exists — check with
  `hasattr(QTest, "mouseWheel")` first; it's absent on some Qt/PySide
  versions (confirmed absent on PySide6 6.11). Use `wheel()` as a fallback,
  which dispatches a real `QWheelEvent` via `QApplication.sendEvent()`.
- Asserting on `grab()` output immediately after `show()` without pumping the
  event loop — the first paint may not have happened yet.
- Scripting a full multi-step interaction sequence before confirming the
  headless mode actually works for this widget hierarchy — run the
  smoke-test recipe in headless-modes.md first; it's cheaper to debug a
  4-line check than a 60-step script.
- Importing a concrete binding (`PySide6`, `PyQt5`, ...) directly instead of
  `qtpy` — couples the test to one binding and diverges from the rest of the
  codebase.
- Renaming or reformatting the `# /// script` header line (e.g. to the file
  name) — uv then ignores the metadata block entirely and the declared
  dependencies are never installed.
- Reaching for `pytest-qt` or a screen-recording library — not needed; plain
  `QtTest` + `grab()` covers interaction and screenshotting with zero new
  dependencies (ask the user first if a real need for one emerges).
