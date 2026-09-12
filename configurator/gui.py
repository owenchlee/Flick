"""Desktop configurator: lets you decide what each hand gesture does.

Built with CustomTkinter for a flat, dark, dev-tool look consistent with
the on-screen HUD (gesture_control.theme is the single source of the
palette both surfaces draw from). Reads/writes the same config.json the
tracker app (main.py) loads at startup — press "C" in the tracker window
to hot-reload without restarting the camera.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

from gesture_control import theme
from gesture_control.actions import ACTIONS, actions_by_category
from gesture_control.config import (
    GESTURE_IDS,
    GESTURE_LABELS,
    SETTINGS_RANGES,
    AppConfig,
    load_config,
    save_config,
)

MAIN_PY = Path(__file__).resolve().parent.parent / "main.py"
CATEGORY_ORDER = ["General", "Reels", "System"]

GESTURE_HINTS = {
    "thumbs_up": "Curl fingers, point thumb up — aim at the like button first",
    "peace": "Extend index + middle, curl the rest — aim at the comments icon first",
    "fist": "Curl all fingers into a fist and hold — release for normal speed",
    "rock": "Extend index + pinky, curl the middle two — a distinct 'previous' gesture",
    "point": "Point your index finger and flick it upward — a calm point just aims the cursor",
}


def _action_choices() -> list[str]:
    grouped = actions_by_category()
    ordered = []
    for category in CATEGORY_ORDER:
        for spec in grouped.get(category, []):
            ordered.append(spec.id)
    return ordered


def _display_label(action_id: str) -> str:
    spec = ACTIONS[action_id]
    suffix = {"hold": " (hold)", "scroll": " (flick)"}.get(spec.kind, "")
    return f"{spec.category}  ·  {spec.label}{suffix}"


class GestureRow(ctk.CTkFrame):
    def __init__(self, master, gesture_id: str, config: AppConfig, on_change):
        super().__init__(master, fg_color=theme.SURFACE, corner_radius=10)
        self.gesture_id = gesture_id
        self.on_change = on_change
        self._label_to_id = {_display_label(a): a for a in _action_choices()}
        self._id_to_label = {v: k for k, v in self._label_to_id.items()}

        self.grid_columnconfigure(1, weight=1)

        dot = ctk.CTkLabel(
            self, text="●", text_color=theme.BRAND, width=18, height=16, font=(theme.UI_FONT_FAMILY, 14),
        )
        dot.grid(row=0, column=0, rowspan=2, padx=(14, 4), pady=10, sticky="n")

        name = ctk.CTkLabel(
            self, text=GESTURE_LABELS[gesture_id], font=(theme.UI_FONT_FAMILY, 14, "bold"),
            text_color=theme.TEXT, anchor="w", height=18,
        )
        name.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(10, 0))

        hint = ctk.CTkLabel(
            self, text=GESTURE_HINTS[gesture_id], font=(theme.UI_FONT_FAMILY, 11),
            text_color=theme.TEXT_MUTED, anchor="w", height=14,
        )
        hint.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(0, 10))

        current_action = config.bindings.get(gesture_id, "none")
        self.menu_var = ctk.StringVar(value=self._id_to_label.get(current_action, self._id_to_label["none"]))
        self.menu = ctk.CTkOptionMenu(
            self,
            values=[self._id_to_label[a] for a in _action_choices()],
            variable=self.menu_var,
            command=self._on_select,
            fg_color=theme.SURFACE_MUTED,
            button_color=theme.BRAND,
            button_hover_color=theme.BRAND_HOVER,
            dropdown_fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            width=230,
        )
        self.menu.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=10, sticky="e")

        self.hotkey_var = ctk.StringVar(value=config.custom_hotkeys.get(gesture_id, ""))
        self.hotkey_entry = ctk.CTkEntry(
            self, textvariable=self.hotkey_var, placeholder_text="e.g. ctrl+shift+s",
            fg_color=theme.SURFACE_MUTED, border_color=theme.BORDER, text_color=theme.TEXT, width=150,
        )
        self.hotkey_var.trace_add("write", lambda *_: self.on_change())
        self._place_hotkey_entry()

    def _place_hotkey_entry(self):
        if self.selected_action_id() == "custom_hotkey":
            self.hotkey_entry.grid(row=0, column=3, rowspan=2, padx=(0, 14), pady=10)
        else:
            self.hotkey_entry.grid_forget()

    def _on_select(self, _value):
        self._place_hotkey_entry()
        self.on_change()

    def selected_action_id(self) -> str:
        return self._label_to_id[self.menu_var.get()]

    def hotkey(self) -> str:
        return self.hotkey_var.get().strip()


class SliderRow(ctk.CTkFrame):
    def __init__(self, master, key: str, title: str, description: str, value, fmt, on_change):
        super().__init__(master, fg_color="transparent")
        self.key = key
        self.fmt = fmt
        self.on_change = on_change
        lo, hi, _default = SETTINGS_RANGES[key]
        is_int = isinstance(value, int)

        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=title, font=(theme.UI_FONT_FAMILY, 14, "bold"), text_color=theme.TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.value_label = ctk.CTkLabel(
            header, text=fmt(value), font=(theme.UI_FONT_FAMILY_MONO, 13), text_color=theme.BRAND_HOVER,
        )
        self.value_label.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self, text=description, font=(theme.UI_FONT_FAMILY, 11), text_color=theme.TEXT_MUTED, anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(0, 6))

        steps = (hi - lo) if is_int else 100
        self.slider = ctk.CTkSlider(
            self, from_=lo, to=hi, number_of_steps=max(1, int(steps)),
            command=self._on_slide, progress_color=theme.BRAND, button_color=theme.BRAND_HOVER,
            fg_color=theme.SURFACE_MUTED,
        )
        self.slider.set(value)
        self.slider.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        self._is_int = is_int

    def _on_slide(self, value):
        value = int(round(value)) if self._is_int else round(float(value), 2)
        self.value_label.configure(text=self.fmt(value))
        self.on_change()

    def value(self):
        raw = self.slider.get()
        return int(round(raw)) if self._is_int else round(float(raw), 2)


class ConfiguratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.config = load_config()
        self._dirty = False

        self.title("Thumb-Detector — Configurator")
        self.geometry("880x680")
        self.minsize(760, 560)
        self.configure(fg_color=theme.BACKGROUND)

        self._build_header()
        self._build_tabs()
        self._build_footer()

    # ─── Layout ─────────────────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 8))

        title = ctk.CTkLabel(
            header, text="THUMB-DETECTOR", font=(theme.UI_FONT_FAMILY, 22, "bold"), text_color=theme.TEXT,
        )
        title.pack(side="left")
        badge = ctk.CTkLabel(
            header, text="CONFIGURATOR", font=(theme.UI_FONT_FAMILY, 12, "bold"),
            text_color=theme.BACKGROUND, fg_color=theme.BRAND, corner_radius=6, padx=8, pady=3,
        )
        badge.pack(side="left", padx=(10, 0))

        self.status_label = ctk.CTkLabel(header, text="", font=(theme.UI_FONT_FAMILY, 12), text_color=theme.SUCCESS)
        self.status_label.pack(side="right")

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self, fg_color=theme.SURFACE, segmented_button_selected_color=theme.BRAND,
            segmented_button_selected_hover_color=theme.BRAND_HOVER,
            segmented_button_unselected_color=theme.SURFACE_MUTED, text_color=theme.TEXT,
        )
        self.tabs.pack(fill="both", expand=True, padx=28, pady=8)

        gestures_tab = self.tabs.add("Gestures")
        sensitivity_tab = self.tabs.add("Sensitivity")
        camera_tab = self.tabs.add("Camera")
        about_tab = self.tabs.add("About")

        self._build_gestures_tab(gestures_tab)
        self._build_sensitivity_tab(sensitivity_tab)
        self._build_camera_tab(camera_tab)
        self._build_about_tab(about_tab)

    def _build_gestures_tab(self, tab):
        intro = ctk.CTkLabel(
            tab, text="Choose what each hand gesture does. Changes apply once you Save.",
            font=(theme.UI_FONT_FAMILY, 12), text_color=theme.TEXT_MUTED, anchor="w",
        )
        intro.pack(fill="x", padx=4, pady=(10, 10))

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self.rows: dict[str, GestureRow] = {}
        for gesture_id in GESTURE_IDS:
            row = GestureRow(scroll, gesture_id, self.config, on_change=self._mark_dirty)
            row.pack(fill="x", pady=4)
            self.rows[gesture_id] = row

    def _build_sensitivity_tab(self, tab):
        wrap = ctk.CTkFrame(tab, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=6, pady=16)

        settings = self.config.settings
        self.sliders: dict[str, SliderRow] = {}

        specs = [
            ("smoothing", "Cursor smoothing", "Higher = steadier cursor, more lag.", lambda v: f"{v} frames"),
            ("action_cooldown", "Action cooldown", "Minimum time between repeated likes/comments.", lambda v: f"{v:.2f}s"),
            ("cursor_margin", "Cursor tracking margin", "Frame edge margin excluded from cursor mapping.", lambda v: f"{v:.2f}"),
            ("scroll_sensitivity", "Scroll sensitivity", "How far each next/previous flick scrolls.", lambda v: f"{v}"),
            ("flick_velocity", "Flick sensitivity", "Lower = a gentler finger flick triggers the next reel.", lambda v: f"{v:.2f}"),
        ]
        for key, title, desc, fmt in specs:
            row = SliderRow(wrap, key, title, desc, getattr(settings, key), fmt, on_change=self._mark_dirty)
            row.pack(fill="x")
            self.sliders[key] = row

    def _build_camera_tab(self, tab):
        wrap = ctk.CTkFrame(tab, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=6, pady=16)

        ctk.CTkLabel(
            wrap, text="Camera index", font=(theme.UI_FONT_FAMILY, 14, "bold"), text_color=theme.TEXT, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            wrap, text="Which webcam to use, if you have more than one (0 is usually the default camera).",
            font=(theme.UI_FONT_FAMILY, 11), text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(fill="x", pady=(0, 8))
        self.camera_index_var = ctk.StringVar(value=str(self.config.settings.camera_index))
        camera_entry = ctk.CTkEntry(
            wrap, textvariable=self.camera_index_var, width=80,
            fg_color=theme.SURFACE_MUTED, border_color=theme.BORDER, text_color=theme.TEXT,
        )
        camera_entry.pack(anchor="w", pady=(0, 20))
        self.camera_index_var.trace_add("write", lambda *_: self._mark_dirty())

        self.switch_vars: dict[str, ctk.BooleanVar] = {}
        for key, label, desc in [
            ("mirror", "Mirror the camera feed", "Flip horizontally so it acts like a mirror."),
            ("show_landmarks", "Show hand skeleton", "Draw the tracked hand landmarks on screen."),
            ("show_grid", "Show coordinate grid", "Overlay a grid for debugging tracking."),
        ]:
            row = ctk.CTkFrame(wrap, fg_color="transparent")
            row.pack(fill="x", pady=6)
            var = ctk.BooleanVar(value=getattr(self.config.settings, key))
            switch = ctk.CTkSwitch(
                row, text="", variable=var, progress_color=theme.BRAND, button_color=theme.TEXT,
                command=self._mark_dirty,
            )
            switch.pack(side="left")
            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", padx=(10, 0))
            ctk.CTkLabel(
                text_col, text=label, font=(theme.UI_FONT_FAMILY, 13, "bold"), text_color=theme.TEXT, anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col, text=desc, font=(theme.UI_FONT_FAMILY, 11), text_color=theme.TEXT_MUTED, anchor="w",
            ).pack(anchor="w")
            self.switch_vars[key] = var

    def _build_about_tab(self, tab):
        wrap = ctk.CTkFrame(tab, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=6, pady=16)

        ctk.CTkLabel(
            wrap, text="Thumb-Detector", font=(theme.UI_FONT_FAMILY, 18, "bold"), text_color=theme.TEXT, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            wrap,
            text="Scroll and react to short-form video feeds — Reels, Shorts, TikTok — with hand gestures.",
            font=(theme.UI_FONT_FAMILY, 12), text_color=theme.TEXT_MUTED, anchor="w", justify="left",
        ).pack(fill="x", pady=(4, 18))

        ctk.CTkLabel(
            wrap, text="Tracker window shortcuts", font=(theme.UI_FONT_FAMILY, 14, "bold"),
            text_color=theme.TEXT, anchor="w",
        ).pack(fill="x", pady=(0, 6))

        for key, desc in [
            ("G", "Toggle the coordinate grid overlay"),
            ("L", "Toggle the hand-skeleton overlay"),
            ("R", "Reset cursor smoothing"),
            ("C", "Reload config.json without restarting"),
            ("Q / Esc", "Quit"),
        ]:
            row = ctk.CTkFrame(wrap, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=key, font=(theme.UI_FONT_FAMILY_MONO, 12, "bold"), text_color=theme.BRAND_HOVER, width=70,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=desc, font=(theme.UI_FONT_FAMILY, 12), text_color=theme.TEXT_MUTED, anchor="w",
            ).pack(side="left")

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=(8, 24))

        reset_btn = ctk.CTkButton(
            footer, text="Reset to Defaults", fg_color="transparent", border_width=1,
            border_color=theme.DANGER, text_color=theme.DANGER, hover_color=theme.SURFACE_MUTED,
            command=self._reset_defaults,
        )
        reset_btn.pack(side="left")

        launch_btn = ctk.CTkButton(
            footer, text="Save & Launch", fg_color=theme.SUCCESS, hover_color="#16A34A",
            text_color=theme.BACKGROUND, font=(theme.UI_FONT_FAMILY, 13, "bold"),
            command=self._save_and_launch,
        )
        launch_btn.pack(side="right")

        save_btn = ctk.CTkButton(
            footer, text="Save", fg_color=theme.BRAND, hover_color=theme.BRAND_HOVER,
            text_color=theme.TEXT, font=(theme.UI_FONT_FAMILY, 13, "bold"),
            command=self._save,
        )
        save_btn.pack(side="right", padx=(0, 10))

    # ─── State ─────────────────────────────────────────────────────────
    def _mark_dirty(self):
        self._dirty = True
        self.status_label.configure(text="Unsaved changes", text_color=theme.WARNING)

    def _collect_config(self) -> AppConfig:
        bindings = {g: row.selected_action_id() for g, row in self.rows.items()}
        custom_hotkeys = {
            g: row.hotkey() for g, row in self.rows.items()
            if row.selected_action_id() == "custom_hotkey" and row.hotkey()
        }

        settings = self.config.settings
        for key, slider in self.sliders.items():
            setattr(settings, key, slider.value())
        settings.mirror = self.switch_vars["mirror"].get()
        settings.show_landmarks = self.switch_vars["show_landmarks"].get()
        settings.show_grid = self.switch_vars["show_grid"].get()
        try:
            settings.camera_index = int(self.camera_index_var.get())
        except ValueError:
            settings.camera_index = 0
        settings.clamp()

        return AppConfig(bindings=bindings, custom_hotkeys=custom_hotkeys, settings=settings)

    def _save(self):
        self.config = self._collect_config()
        save_config(self.config)
        self._dirty = False
        self.status_label.configure(text="Saved ✓", text_color=theme.SUCCESS)
        self.after(2500, lambda: self.status_label.configure(text=""))

    def _save_and_launch(self):
        self._save()
        subprocess.Popen([sys.executable, str(MAIN_PY)], cwd=str(MAIN_PY.parent))
        self.status_label.configure(text="Saved ✓ · Launching…", text_color=theme.SUCCESS)

    def _reset_defaults(self):
        self.config = AppConfig.default()
        save_config(self.config)
        self.destroy()
        run_configurator()


def run_configurator():
    ctk.set_appearance_mode("dark")
    ctk.set_widget_scaling(1.0)
    app = ConfiguratorApp()
    app.mainloop()


if __name__ == "__main__":
    run_configurator()
