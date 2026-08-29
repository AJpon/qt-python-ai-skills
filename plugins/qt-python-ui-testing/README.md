# Qt for Python UI Testing

This is a plugin for Claude Code / GitHub Copilot CLI to review and automate GUI tests for Qt for Python applications. It enables not only generating widgets and validating properties, but also simulating real mouse/keyboard actions and writing tests that verify rendering results with screenshots.

## Installation

Add this repository as a marketplace and then install:

```bash
/plugin marketplace add AJpon/qt-python-ai-skills
/plugin install qt-python-ui-testing@ajpon-qt-python-plugins
```

## Provided skill

### qt-python-ui-testing

- **When to use**: When you want to verify that clicks/key inputs actually cause something (opening a menu, toggling an action, emitting a signal, etc.), when you want to inspect rendering results of GPU-backed widgets (like QRhiWidget) with step-by-step screenshots, or when you need to run in headless environments (CI or sandboxed agents).
- **When not to use**: Tests that do not involve a UI (logic/model-only tests), smoke tests that only verify widget properties, or web UI tests.
- **Included contents:**
  - [SKILL.md](skills/qt-python-ui-testing/SKILL.md) — The main skill. Summarizes headless execution methods for flat widgets and GPU rendering targets (QRhiWidget/QOpenGLWidget/QQuickWidget), ways to avoid modal dialogs, and common pitfalls.
  - [references/headless-modes.md](skills/qt-python-ui-testing/references/headless-modes.md) — Guidance on choosing between `QT_QPA_PLATFORM=offscreen` and `WA_DontShowOnScreen`, and smoke test steps that have been verified.
  - [references/video-encoding.md](skills/qt-python-ui-testing/references/video-encoding.md) — ffmpeg recipes when a video artifact is explicitly required.
  - [scripts/gui_probe.py](skills/qt-python-ui-testing/scripts/gui_probe.py) — Reusable helpers such as `click()`, `key_clicks()`, `drag()`, `wheel()`, `screenshot()`, and `record_steps()` (with inline script metadata per PEP 723), runnable directly via `uv run`.

## Prerequisites

- The target project must have [qtpy](https://github.com/spyder-ide/qtpy) and some Qt binding (PySide6/PyQt6, etc.) installed.
- `gui_probe.py` is intended to be run with `uv run --active` (the project's venv should be active so the bindings can be resolved).

## License

[MIT License](https://github.com/AJpon/qt-python-ai-skills/blob/main/LICENSE)
