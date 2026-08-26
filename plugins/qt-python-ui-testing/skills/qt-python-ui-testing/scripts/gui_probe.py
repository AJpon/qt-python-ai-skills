# /// script
# requires-python = ">=3.10"
# dependencies = ["qtpy>=2.4.3"]
# [tool]
# [tool.uv]
# required-version = ">=0.12.0"
# ///

"""Reusable helpers for driving Qt widgets like a user and capturing screenshots.

Adapt these into test files under tests/ rather than importing this module
directly from production code — it exists to be copied/trimmed per-test, per
the pattern in SKILL.md.

Two launch modes, picked by whether the widget under test is a GPU render
target (QRhiWidget, QOpenGLWidget, QQuickWidget, ...):

- show_offscreen(widget): plain QWidget subtrees. Requires
  QT_QPA_PLATFORM=offscreen to be set before QApplication is created.
- show_hidden_native(widget): GPU render targets. Must run under the real
  platform plugin (do NOT set QT_QPA_PLATFORM=offscreen) so the GPU backend
  (Direct3D/Metal/Vulkan) can create a real swapchain.

qtpy is an abstraction shim: the environment you run in must have a real Qt
binding installed (PySide6, PyQt5, ...). See SKILL.md "If qtpy import fails".
"""

from collections.abc import Callable

from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QWheelEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget


def show_offscreen(widget: QWidget) -> None:
    """Show a plain widget under the offscreen platform plugin and wait for it to paint."""
    widget.show()
    QTest.qWaitForWindowExposed(widget)


def show_hidden_native(
    widget: QWidget, app: QApplication, settle_iterations: int = 5
) -> None:
    """Show a QRhiWidget off-screen under the real platform plugin.

    `widget` may be the GPU render target itself (if it's the top-level
    widget) or any widget nested inside a larger window — this resolves to
    `widget.window()` internally, since `WA_DontShowOnScreen` must be set on
    the actual top-level window: a nested widget has no native surface of its
    own, so setting the attribute directly on it does nothing useful.
    Verified against a QRhiWidget nested three levels deep inside a
    QMainWindow (via QSplitter) in a real app.

    qWaitForWindowExposed() is unreliable for WA_DontShowOnScreen widgets (it can
    report False even after rendering has started), so this pumps the event loop
    a fixed number of times instead of waiting for an expose event.
    """
    top = widget.window()
    top.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    top.show()
    for _ in range(settle_iterations):
        app.processEvents()
        QTest.qWait(50)


def click(widget: QWidget, button: Qt.MouseButton = Qt.MouseButton.LeftButton) -> None:
    """Simulate a real mouse click through Qt's event queue (not widget.click())."""
    QTest.mouseClick(widget, button)
    QApplication.processEvents()


def key_clicks(widget: QWidget, text: str) -> None:
    """Type text into a widget through Qt's event queue."""
    QTest.keyClicks(widget, text)
    QApplication.processEvents()


def drag(
    widget: QWidget,
    start: QPoint,
    end: QPoint,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    steps: int = 8,
) -> None:
    """Simulate a click-drag-release gesture (camera orbit/pan, sliders, canvases).

    Moves through `steps` intermediate points so anything keyed off drag delta
    (not just start/end) sees a real gesture, not a single jump. Each
    intermediate point is a QTest.mouseMove() call, which is what actually
    delivers a QMouseEvent — a single mousePress()+mouseRelease() with no
    mouseMove() in between never fires mouseMoveEvent() at all.
    """
    QTest.mousePress(widget, button, pos=start)
    QApplication.processEvents()
    for i in range(1, steps + 1):
        t = i / steps
        point = QPoint(
            round(start.x() + (end.x() - start.x()) * t),
            round(start.y() + (end.y() - start.y()) * t),
        )
        QTest.mouseMove(widget, point)
        QApplication.processEvents()
    QTest.mouseRelease(widget, button, pos=end)
    QApplication.processEvents()


def wheel(widget: QWidget, pos: QPoint, angle_delta_y: int = 120) -> None:
    """Simulate a mouse wheel notch (zoom, scroll) via a synthesized QWheelEvent.

    QTest.mouseWheel is not available in every Qt/PySide build (verified
    absent in PySide6 6.11 — check with `hasattr(QTest, "mouseWheel")` on your
    version before assuming it exists). This constructs a real QWheelEvent and
    dispatches it through QApplication.sendEvent(), which still exercises the
    widget's real wheelEvent() handler — just not through QTest's recorder.
    One notch is angle_delta_y=120 (the Qt convention); negative scrolls the
    other direction.
    """
    event = QWheelEvent(
        QPointF(pos),
        widget.mapToGlobal(pos).toPointF(),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)
    QApplication.processEvents()


def screenshot(widget: QWidget, path: str) -> bool:
    """Grab the widget's current rendered pixels and save them as a PNG.

    Args:
        widget (:class:`QWidget`): The widget to capture.
        path (str): The file path to save the screenshot to.

    Returns:
        bool: True if the screenshot was saved successfully, False otherwise.
    """
    return widget.grab().save(path)


def record_steps(
    widget: QWidget, steps: list[tuple[str, Callable]], out_dir: str
) -> list[str]:
    """Run a sequence of (label, action) steps, screenshotting after each.

    Produces a numbered PNG per step (e.g. "0000-open_panel_menu.png") — a
    storyboard of the interaction, without pulling in a GIF/video dependency.
    The index is zero-padded to 4 digits so plain lexicographic sorting
    (`sorted(path.glob("*.png"))`, a file browser, ffmpeg's frame pattern)
    stays in the right order past 9 steps — unpadded "10-x.png" would
    otherwise sort before "2-y.png". Returns the list of saved file paths in
    order.

    Args:
        widget (:class:`QWidget`): The widget to interact with and capture screenshots from.
        steps (list[tuple[str, Callable]]): A list of (label, action) steps to perform.
        out_dir (str): Directory to save the screenshots.

    Returns:
        list[str]: List of saved screenshot file paths in order.
    """
    saved = []
    for index, (label, action) in enumerate(steps):
        action()
        QApplication.processEvents()
        path = f"{out_dir}/{index:04d}-{label}.png"
        screenshot(widget, path)
        saved.append(path)
    return saved
