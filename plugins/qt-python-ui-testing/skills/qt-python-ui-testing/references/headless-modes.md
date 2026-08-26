# Headless Launch Modes

Reference for choosing how to show a Qt widget without a visible window when
running GUI tests. SKILL.md summarizes the decision rule; this file has the
full comparison, platform requirements, and a verified example.

## Decision table

| Widget under test | Mode | Why |
|---|---|---|
| Plain `QWidget` subtrees (`QPushButton`, `QMenu`, toolbars, tree/panel views) | `QT_QPA_PLATFORM=offscreen` env var | Full software platform plugin; no real window needed; fastest. |
| GPU render targets: `QRhiWidget` subclasses, `QOpenGLWidget`, `QQuickWidget` | Real platform plugin (default) + `Qt.WA_DontShowOnScreen` on the top-level widget | The offscreen plugin has no native surface, so Metal/Vulkan/Direct3D cannot create a swapchain — `initialize()`/`render()` never fire. `WA_DontShowOnScreen` keeps the real native window (real GPU backend works) but keeps it off the physical display. |

Set `QT_QPA_PLATFORM=offscreen` before creating the `QApplication`. For the GPU
mode, do NOT set the variable at all.

## Platform requirements

Both modes still require an actual window/desktop session behind the platform
plugin:

- Windows/macOS: a logged-in desktop session.
- Linux CI: a virtual display such as Xvfb (`xvfb-run pytest ...`).

`Qt.WA_DontShowOnScreen` means "not visible", not "no windowing system at all".

## Gotcha: qWaitForWindowExposed returns False for WA_DontShowOnScreen

Confirmed by testing: `QTest.qWaitForWindowExposed()` returns `False` for a
`WA_DontShowOnScreen` widget even though it renders correctly — do not gate on
it in the GPU mode. Instead call `show()`, then pump the event loop a few times
before `grab()`. `top` below is the top-level window — the GPU widget itself
only if it has no parent window; see the next section if it's nested:

```python
top.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
top.show()
for _ in range(5):
    app.processEvents()
    QTest.qWait(50)
pixmap = top.grab()  # or a specific nested widget's .grab(), once `top` is shown
```

`show_offscreen()` / `show_hidden_native()` in
[gui_probe.py](../scripts/gui_probe.py) implement both modes.

## Verified example

In this repository, `src/fbx_view/renderer.py` (`FBXRenderer(QRhiWidget)`) ran
in the GPU mode under Direct3D11 on Windows: `initialize()` and `render()`
fired, and `grab()` returned the expected pixel color. The same widget under
`QT_QPA_PLATFORM=offscreen` failed silently — no RHI initialization, no render
calls.

## Nested GPU widgets: set the attribute on the top-level window

A `QRhiWidget` (or other GPU render target) is rarely the top-level widget in
a real app — it's usually embedded in a `QMainWindow` via layouts/splitters,
alongside toolbars, panels, and menus. `Qt.WA_DontShowOnScreen` must be set on
the **top-level window** (the `QMainWindow`/`QDialog`), not on the nested GPU
widget itself — child widgets don't get their own native surface, they
composite into the top-level window's.

Verified against `fbx-view`'s real window (`FBXRenderer` nested three levels
deep inside `QMainWindow` → `QSplitter` → `QSplitter`): setting the attribute
on the `QMainWindow` and calling `window.show()` correctly initialized the
renderer's Direct3D11 backend and produced correct pixels on `grab()`.

`gui_probe.show_hidden_native(widget, app)` resolves this automatically via
`widget.window()` (the standard Qt call that walks up to a widget's top-level
window, returning the widget itself if it has none) — pass either the render
widget or the window, both land on the same top-level window internally.
Verified: calling it with the nested `FBXRenderer` produced the same correct
Direct3D11 render as calling it with the `QMainWindow` directly.

Screenshot the whole top-level window (not just the GPU widget) when you want
the surrounding UI state visible in the capture — toolbar/menu state, slider
position, selection highlight. Screenshot the specific widget when you want a
tight, narrowly-scoped comparison target.

## Smoke-test before scripting a full sequence

Before writing a multi-step interaction script (drag sequences, mode
switches, playback loops), run a 4-line smoke check first: show the window
headless, load one real data file, grab once, and confirm the pixel content
changed from a known baseline. This is cheap and catches placement mistakes
(previous section), missing `processEvents()` pumps, or wrong widget targets
before they're buried inside a 60-step script that's expensive to debug.

```python
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
window.show()
for _ in range(8):
    app.processEvents()
    QTest.qWait(50)
cx, cy = 400, 300  # any point inside the widget you expect the action to change
before = window.grab().toImage().pixelColor(cx, cy)
# ... perform one action ...
after = window.grab().toImage().pixelColor(cx, cy)
assert before != after, "no visible change — check WA_DontShowOnScreen placement and event pumping"
```
