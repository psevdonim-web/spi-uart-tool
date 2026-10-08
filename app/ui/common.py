"""
Common UI utilities.

- colors
- text widget context menu
- tooltips
- progress bar drawing
"""

import tkinter as tk
from tkinter import ttk


# ---------- Color scheme ----------
# Logs are always dark (like a terminal), regardless of system theme.

LOG_BG = "#1e1e1e"
LOG_FG = "#d4d4d4"
LOG_SEL_BG = "#264f78"
BORDER_COLOR = "#555555"
PROG_COLOR = "#4ec9b0"

# Progress colors by operation type
PROG_READ = "#4ec9b0"     # green
PROG_VERIFY = "#dcdcaa"   # yellow
PROG_WRITE = "#f44747"    # red
PROG_ERASE = "#ce9178"    # orange
PROG_DEFAULT = "#4ec9b0"


# ---------- Common constants ----------
SPI_LABEL_WIDTH = 10
BTN_WIDTH = 14


# ---------- Text widget context menu ----------
def attach_text_context_menu(text_widget, on_clear=None):
    menu = tk.Menu(text_widget, tearoff=0)

    def copy_selection():
        try:
            selected = text_widget.get("sel.first", "sel.last")
            text_widget.clipboard_clear()
            text_widget.clipboard_append(selected)
        except tk.TclError:
            pass

    def select_all():
        text_widget.tag_add("sel", "1.0", "end-1c")
        text_widget.mark_set("insert", "1.0")
        text_widget.see("insert")
        return "break"

    def clear_all():
        if on_clear:
            on_clear()
        else:
            text_widget.delete("1.0", "end")

    menu.add_command(label="Copy", command=copy_selection)
    menu.add_command(label="Select All", command=select_all)
    menu.add_separator()
    menu.add_command(label="Clear", command=clear_all)

    def show_menu(event):
        try:
            text_widget.get("sel.first", "sel.last")
            menu.entryconfig("Copy", state="normal")
        except tk.TclError:
            menu.entryconfig("Copy", state="disabled")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    text_widget.bind("<Button-2>", show_menu)
    text_widget.bind("<Button-3>", show_menu)
    text_widget.bind("<Control-Button-1>", show_menu)

    # On macOS only uppercase C and A work
    text_widget.bind("<Command-C>", lambda e: (copy_selection(), "break")[1])
    text_widget.bind("<Command-A>", lambda e: select_all())


# ---------- Tooltip ----------
def make_tooltip(widget, text):
    def on_enter(event):
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        lbl = tk.Label(tip, text=text, background="#ffffe0",
                       relief="solid", borderwidth=1,
                       font=("Helvetica", 10), justify="left")
        lbl.pack()
        widget._tooltip = tip

    def on_leave(event):
        if hasattr(widget, "_tooltip"):
            widget._tooltip.destroy()
            del widget._tooltip

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


# ---------- Progress drawing on Canvas ----------
def draw_progress(canvas, value, max_value=100, color=None):
    """Draw a progress bar. color — HEX fill color."""
    canvas.delete("all")
    w = canvas.winfo_width()
    if w < 10:
        w = 400
    h = canvas.winfo_height()
    if h < 10:
        h = 20
    ratio = max(0.0, min(1.0, value / max_value))
    fill_w = int(w * ratio)
    if color is None:
        color = PROG_COLOR
    canvas.create_rectangle(0, 0, w, h, fill=BORDER_COLOR, outline="")
    canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")
    canvas.create_text(w // 2, h // 2,
                       text=f"{int(ratio * 100)}%",
                       fill=LOG_BG, font=("Menlo", 10))
