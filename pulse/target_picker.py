"""Floating window-target picker — AppKit / Quartz, no tkinter required.

Run as a subprocess via launch_picker(); the selected target name is
written to stdout so the parent process can call focus_target() on it.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from typing import Callable

import AppKit  # type: ignore[import]
import objc  # type: ignore[import]

from pulse.window_targets import WindowTarget, focus_target, list_targets

# ── Layout ────────────────────────────────────────────────────────────────────
CARD_W, CARD_H = 240, 185
THUMB_W, THUMB_H = 240, 145
COLS_MAX = 3
PAD = 12
HEADER_H = 40

# ── Quartz thumbnail capture ──────────────────────────────────────────────────

def _find_window_id(app: str, title: str) -> int | None:
    try:
        from Quartz import (  # type: ignore[import]
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionAll,
        )
        for w in CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID):
            owner = (w.get("kCGWindowOwnerName") or "").lower()
            wname = (w.get("kCGWindowName") or "").lower()
            if owner == app.lower() and (not title or title.lower() in wname):
                wid = w.get("kCGWindowNumber")
                if wid:
                    return int(wid)
    except Exception:
        pass
    return None


def _capture_nsimage(app: str, title: str) -> AppKit.NSImage | None:
    wid = _find_window_id(app, title)
    if wid is None:
        return None
    try:
        from Quartz import (  # type: ignore[import]
            CGWindowListCreateImage,
            CGRectNull,
            kCGWindowImageDefault,
            kCGWindowListOptionIncludingWindow,
        )
        cg_img = CGWindowListCreateImage(
            CGRectNull,
            kCGWindowListOptionIncludingWindow,
            wid,
            kCGWindowImageDefault,
        )
        if cg_img is None:
            return None
        return AppKit.NSImage.alloc().initWithCGImage_size_(
            cg_img, AppKit.NSZeroSize
        )
    except Exception:
        return None


# ── Custom card view ──────────────────────────────────────────────────────────

class _CardView(AppKit.NSView):
    """Dark rounded card with thumbnail + label."""

    _on_click: Callable[[str], None]
    _name: str
    _img_view: AppKit.NSImageView
    _hovered: bool

    def init(self) -> "_CardView":
        self = objc.super(_CardView, self).init()
        if self is None:
            return None  # type: ignore[return-value]
        self._hovered = False
        self._on_click = lambda _: None
        self._name = ""
        return self

    # Rounded dark background with hover highlight
    def drawRect_(self, dirty_rect: AppKit.NSRect) -> None:
        color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
            0.26, 0.26, 0.27, 1.0
        ) if not self._hovered else AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
            0.33, 0.33, 0.35, 1.0
        )
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 8.0, 8.0
        )
        color.setFill()
        path.fill()

    def mouseEntered_(self, event: object) -> None:
        self._hovered = True
        self.setNeedsDisplay_(True)

    def mouseExited_(self, event: object) -> None:
        self._hovered = False
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event: object) -> None:
        self._on_click(self._name)

    def updateTrackingAreas(self) -> None:
        for area in self.trackingAreas():
            self.removeTrackingArea_(area)
        opts = (
            AppKit.NSTrackingMouseEnteredAndExited
            | AppKit.NSTrackingActiveAlways
        )
        self.addTrackingArea_(
            AppKit.NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(), opts, self, None
            )
        )

    def acceptsFirstMouse_(self, _: object) -> bool:
        return True


def _make_card(
    x: float, y: float, name: str, target: WindowTarget,
    on_click: Callable[[str], None],
) -> tuple[_CardView, AppKit.NSImageView]:
    frame = AppKit.NSMakeRect(x, y, CARD_W, CARD_H)
    card = _CardView.alloc().initWithFrame_(frame)
    card._name = name
    card._on_click = on_click

    # Thumbnail image view
    img_view = AppKit.NSImageView.alloc().initWithFrame_(
        AppKit.NSMakeRect(0, CARD_H - THUMB_H, THUMB_W, THUMB_H)
    )
    img_view.setImageScaling_(AppKit.NSImageScaleAxesIndependently)
    img_view.setImageAlignment_(AppKit.NSImageAlignCenter)
    img_view.setWantsLayer_(True)
    img_view.layer().setCornerRadius_(6.0)
    img_view.layer().setMasksToBounds_(True)
    card.addSubview_(img_view)

    # Target name label
    name_lbl = AppKit.NSTextField.labelWithString_(name)
    name_lbl.setFrame_(AppKit.NSMakeRect(6, 22, CARD_W - 12, 18))
    name_lbl.setFont_(AppKit.NSFont.boldSystemFontOfSize_(12.0))
    name_lbl.setTextColor_(AppKit.NSColor.whiteColor())
    name_lbl.setAlignment_(AppKit.NSTextAlignmentCenter)
    card.addSubview_(name_lbl)

    # App name label
    app_lbl = AppKit.NSTextField.labelWithString_(target.app)
    app_lbl.setFrame_(AppKit.NSMakeRect(6, 4, CARD_W - 12, 16))
    app_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(10.0))
    app_lbl.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
        0.56, 0.56, 0.58, 1.0
    ))
    app_lbl.setAlignment_(AppKit.NSTextAlignmentCenter)
    card.addSubview_(app_lbl)

    card.updateTrackingAreas()
    return card, img_view


# ── Picker window builder ─────────────────────────────────────────────────────

def _build_window(
    targets: dict[str, WindowTarget],
    on_select: Callable[[str], None],
) -> tuple[AppKit.NSPanel, list[tuple[str, WindowTarget, AppKit.NSImageView]]]:
    cols = min(len(targets), COLS_MAX)
    rows = (len(targets) + cols - 1) // cols
    w = cols * CARD_W + (cols + 1) * PAD
    h = HEADER_H + rows * CARD_H + (rows + 1) * PAD

    panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        AppKit.NSMakeRect(0, 0, w, h),
        (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskHUDWindow
            | AppKit.NSWindowStyleMaskUtilityWindow
        ),
        AppKit.NSBackingStoreBuffered,
        False,
    )
    panel.setTitle_("Focus Window")
    panel.setLevel_(AppKit.NSFloatingWindowLevel)
    panel.setMovableByWindowBackground_(True)
    panel.setAppearance_(
        AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua)
    )

    content = panel.contentView()
    img_views: list[tuple[str, WindowTarget, AppKit.NSImageView]] = []

    for i, (name, target) in enumerate(targets.items()):
        row, col = divmod(i, cols)
        x = PAD + col * (CARD_W + PAD)
        # y=0 is bottom in AppKit — cards fill upward from bottom padding
        y = PAD + (rows - 1 - row) * (CARD_H + PAD)
        card, img_view = _make_card(x, y, name, target, on_select)
        content.addSubview_(card)
        img_views.append((name, target, img_view))

    panel.center()
    return panel, img_views


# ── Main picker function ──────────────────────────────────────────────────────

def show_picker() -> str | None:
    """Show the picker overlay. Returns the selected target name, or None."""
    targets = list_targets()
    if not targets:
        return None

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    selected: list[str | None] = [None]

    def on_select(name: str) -> None:
        selected[0] = name
        app.terminate_(None)

    panel, img_views = _build_window(targets, on_select)

    # Wire close button to quit
    panel.setDelegate_(
        _PanelDelegate.alloc().initWithApp_(app)  # type: ignore[attr-defined]
    )

    panel.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)

    # Load thumbnails in parallel on background threads
    def load_thumb(name: str, target: WindowTarget, img_view: AppKit.NSImageView) -> None:
        ns_img = _capture_nsimage(target.app, target.title)
        if ns_img:
            AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: img_view.setImage_(ns_img)
            )

    for name, target, img_view in img_views:
        threading.Thread(
            target=load_thumb, args=(name, target, img_view), daemon=True
        ).start()

    app.run()
    return selected[0]


class _PanelDelegate(AppKit.NSObject):
    _app: AppKit.NSApplication

    def initWithApp_(self, app: AppKit.NSApplication) -> "_PanelDelegate":
        self = objc.super(_PanelDelegate, self).init()
        if self is None:
            return None  # type: ignore[return-value]
        self._app = app
        return self

    def windowWillClose_(self, notification: object) -> None:
        self._app.terminate_(None)


# ── Subprocess launcher ───────────────────────────────────────────────────────

def launch_picker() -> None:
    """Spawn the picker subprocess and focus the chosen target on completion."""
    def _run() -> None:
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pulse.target_picker"],
                stdout=subprocess.PIPE,
                text=True,
            )
            out, _ = proc.communicate(timeout=30)
            name = out.strip()
            if name:
                focus_target(name)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True, name="pulse-picker").start()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = show_picker()
    if result:
        sys.stdout.write(result)
