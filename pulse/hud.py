"""Floating gesture-confidence HUD.

Shows a non-activating frosted-glass panel whenever a gesture fires:

    ┌──────────────────────────────────────┐
    │  ▶ wave_out               ████░ 87% │
    │  → claude_right                      │
    └──────────────────────────────────────┘

Call HUD.show() from any thread — it dispatches to the main queue internally.
"""
from __future__ import annotations

import AppKit  # type: ignore[import]
import objc    # type: ignore[import]

from pulse.window_targets import get_current_target

# ── Gesture display icons ─────────────────────────────────────────────────────
_ICON: dict[str, str] = {
    "fist":           "✊",
    "wave_in":        "◀",
    "wave_out":       "▶",
    "fingers_spread": "✋",
    "thumb_to_pinky": "↕",
}

# ── Layout (all in points) ────────────────────────────────────────────────────
_W, _H  = 320, 68
_PAD    = 14
_BAR_W  = 72
_BAR_H  = 5
_SECS   = 2.5          # auto-hide delay

# ── Confidence bar colours ────────────────────────────────────────────────────
_GREEN  = (0.188, 0.820, 0.345)   # ≥ 70 %
_YELLOW = (1.000, 0.839, 0.039)   # < 70 %


# ── Custom confidence bar view ────────────────────────────────────────────────

class _BarView(AppKit.NSView):
    """Slim rounded-rect confidence bar drawn with NSBezierPath."""

    def init(self) -> "_BarView":
        self = objc.super(_BarView, self).init()
        if self is None:
            return None  # type: ignore[return-value]
        self._f: float = 0.0
        return self

    def setFraction_(self, f: float) -> None:
        self._f = max(0.0, min(1.0, f))
        self.setNeedsDisplay_(True)

    def drawRect_(self, _rect: AppKit.NSRect) -> None:
        b = self.bounds()
        r = 2.5

        # Track (dim white)
        AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.25).setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, r, r).fill()

        # Fill (green ≥ 70 %, yellow otherwise)
        f = getattr(self, "_f", 0.0)
        if f > 0:
            rgb = _GREEN if f >= 0.70 else _YELLOW
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                rgb[0], rgb[1], rgb[2], 1.0
            ).setFill()
            fill = AppKit.NSMakeRect(0, 0, b.size.width * f, b.size.height)
            AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                fill, r, r
            ).fill()


# ── HUD ───────────────────────────────────────────────────────────────────────

class HUD:
    """Non-activating floating HUD. Thread-safe: call show() from anywhere."""

    def __init__(self) -> None:
        self._panel: AppKit.NSPanel | None = None
        self._gesture_lbl: AppKit.NSTextField | None = None
        self._conf_lbl: AppKit.NSTextField | None = None
        self._bar: _BarView | None = None
        self._detail_lbl: AppKit.NSTextField | None = None
        self._timer: AppKit.NSTimer | None = None
        self._build()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        mask = (
            AppKit.NSWindowStyleMaskBorderless
            | getattr(AppKit, "NSWindowStyleMaskNonactivatingPanel", 128)
        )
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, _W, _H),
            mask,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(AppKit.NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setAlphaValue_(0.0)
        self._panel = panel

        # Frosted-glass background
        mat = getattr(
            AppKit, "NSVisualEffectMaterialHUDWindow",
            getattr(AppKit, "NSVisualEffectMaterialDark", 1),
        )
        bg = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, _W, _H)
        )
        bg.setMaterial_(mat)
        bg.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        bg.setState_(AppKit.NSVisualEffectStateActive)
        bg.setWantsLayer_(True)
        bg.layer().setCornerRadius_(10.0)
        bg.layer().setMasksToBounds_(True)
        panel.setContentView_(bg)

        # Row 1 — gesture name (top-left)
        row1_y = _H - _PAD - 20
        g_lbl = AppKit.NSTextField.labelWithString_("")
        g_lbl.setFrame_(AppKit.NSMakeRect(_PAD, row1_y, 172, 20))
        g_lbl.setFont_(AppKit.NSFont.boldSystemFontOfSize_(14.0))
        g_lbl.setTextColor_(AppKit.NSColor.whiteColor())
        bg.addSubview_(g_lbl)
        self._gesture_lbl = g_lbl

        # Row 1 — confidence % (top-right)
        c_lbl = AppKit.NSTextField.labelWithString_("")
        c_lbl.setFrame_(AppKit.NSMakeRect(_W - _PAD - 38, row1_y, 38, 18))
        c_lbl.setFont_(
            AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(
                11.0, AppKit.NSFontWeightMedium
            )
        )
        c_lbl.setTextColor_(AppKit.NSColor.whiteColor())
        c_lbl.setAlignment_(AppKit.NSTextAlignmentRight)
        bg.addSubview_(c_lbl)
        self._conf_lbl = c_lbl

        # Row 1 — confidence bar (between gesture and %)
        bar_x = _W - _PAD - 38 - 6 - _BAR_W
        bar_y = row1_y + 7
        bar = _BarView.alloc().initWithFrame_(
            AppKit.NSMakeRect(bar_x, bar_y, _BAR_W, _BAR_H)
        )
        bg.addSubview_(bar)
        self._bar = bar

        # Row 2 — detail / target (bottom)
        d_lbl = AppKit.NSTextField.labelWithString_("")
        d_lbl.setFrame_(AppKit.NSMakeRect(_PAD, 9, _W - _PAD * 2, 15))
        d_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(11.0))
        d_lbl.setTextColor_(AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.55))
        bg.addSubview_(d_lbl)
        self._detail_lbl = d_lbl

    # ── Public API ────────────────────────────────────────────────────────────

    def show(
        self,
        gesture: str,
        confidence: float | None,
        action: str | None = None,
    ) -> None:
        """Thread-safe: dispatches UI work to the main queue."""
        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: self._show(gesture, confidence, action)
        )

    # ── Private (must run on main thread) ────────────────────────────────────

    def _show(
        self,
        gesture: str,
        confidence: float | None,
        action: str | None,
    ) -> None:
        if self._panel is None:
            return

        # Gesture name + icon
        icon = _ICON.get(gesture, "")
        self._gesture_lbl.setStringValue_(f"{icon}  {gesture}" if icon else gesture)

        # Confidence bar and label
        if confidence is not None:
            self._conf_lbl.setStringValue_(f"{int(confidence * 100)}%")
            self._bar.setFraction_(confidence)
            self._conf_lbl.setHidden_(False)
            self._bar.setHidden_(False)
        else:
            self._conf_lbl.setHidden_(True)
            self._bar.setHidden_(True)

        # Detail row: active target (+ action if supplied)
        target = get_current_target()
        parts: list[str] = []
        if target:
            parts.append(f"→ {target}")
        if action:
            parts.append(action)
        self._detail_lbl.setStringValue_("  ·  ".join(parts))

        # Position: bottom-centre of main screen (above dock)
        sr = AppKit.NSScreen.mainScreen().visibleFrame()
        x = sr.origin.x + (sr.size.width - _W) / 2
        y = sr.origin.y + 12
        self._panel.setFrame_display_(AppKit.NSMakeRect(x, y, _W, _H), False)

        # Fade in
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0.12)
        self._panel.animator().setAlphaValue_(0.95)
        AppKit.NSAnimationContext.endGrouping()
        self._panel.orderFront_(None)

        # Reset auto-hide timer
        if self._timer is not None:
            self._timer.invalidate()
        self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            _SECS, False, lambda _t: self._fade_out()
        )

    def _fade_out(self) -> None:
        if self._panel is None:
            return
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0.3)
        self._panel.animator().setAlphaValue_(0.0)
        AppKit.NSAnimationContext.endGrouping()
        self._timer = None
