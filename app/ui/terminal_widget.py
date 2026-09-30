"""
Terminal widget: renders pyte screen into tkinter.Text, handles keys.
Tracks window resize with debounce (500 ms).
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
from typing import Callable, Optional

from .common import LOG_BG, LOG_FG


DEFAULT_FONT_SIZE = 11
RESIZE_DELAY_MS = 500


class TerminalWidget(ttk.Frame):
    """Terminal: pyte screen rendering + input + dynamic resize."""

    def __init__(self, parent, on_key: Callable[[str], None],
                 on_resize: Optional[Callable[[int, int], None]] = None,
                 font_size: int = DEFAULT_FONT_SIZE):
        super().__init__(parent)
        self.on_key = on_key
        self.on_resize = on_resize
        self.font_size = font_size
        self._resize_after_id = None
        self._last_cols = 0
        self._last_rows = 0

        # Container
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        # Display widget (no focus ring)
        self.text = tk.Text(self.container, wrap="none",
                            font=("Menlo", self.font_size),
                            bg=LOG_BG, fg=LOG_FG,
                            insertbackground=LOG_BG,
                            selectbackground="#264f78",
                            relief="solid", borderwidth=1,
                            highlightthickness=1,
                            highlightbackground=LOG_BG,
                            highlightcolor=LOG_BG,
                            spacing1=0, spacing2=0, spacing3=0)
        self.text.pack(side="left", fill="both", expand=True)

        # Scrollbar
        self.scroll = ttk.Scrollbar(self.container, orient="vertical",
                                    command=self.text.yview)
        self.scroll.pack(side="right", fill="y")
        self.text.config(yscrollcommand=self.scroll.set)

        # Cursor tag — filled block
        self.text.tag_config("cursor", background="#d4d4d4",
                             foreground="#1e1e1e")

        # Key handler
        self.text.bind("<Key>", self._on_key_event)

        # Right click
        self.text.bind("<Button-2>", self._on_right_click)
        self.text.bind("<Button-3>", self._on_right_click)
        self.text.bind("<Control-Button-1>", self._on_right_click)

        # Auto scroll
        self._auto_scroll = True
        self.text.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        self.text.bind("<Button-4>", self._on_mouse_wheel, add="+")
        self.text.bind("<Button-5>", self._on_mouse_wheel, add="+")

        # Resize tracking
        self.container.bind("<Configure>", self._on_configure)

        self.text.focus_set()

    # ---------- Font size ----------
    def set_font_size(self, size: int):
        try:
            size = int(size)
        except (ValueError, TypeError):
            return
        if size < 6 or size > 40:
            return
        self.font_size = size
        try:
            self.text.config(font=("Menlo", size))
        except Exception:
            pass
        self._schedule_resize()

    # ---------- Resize ----------
    def _on_configure(self, event=None):
        self._schedule_resize()

    def _schedule_resize(self):
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.after(RESIZE_DELAY_MS, self._do_resize)

    def _do_resize(self):
        self._resize_after_id = None
        if not self.on_resize:
            return

        cols, rows = self._calc_cols_rows()
        if cols == self._last_cols and rows == self._last_rows:
            return
        self._last_cols = cols
        self._last_rows = rows

        try:
            self.on_resize(cols, rows)
        except Exception:
            pass

    def _calc_cols_rows(self):
        try:
            f = tkfont.Font(font=self.text.cget("font"))
            char_w = f.measure("M") or 1
            char_h = f.metrics("linespace") or 1

            w = self.text.winfo_width()
            h = self.text.winfo_height()

            cols = max(20, (w - 8) // char_w)
            rows = max(5, (h - 8) // char_h)
            return cols, rows
        except Exception:
            return 80, 24

    # ---------- Scroll ----------
    def _on_mouse_wheel(self, event=None):
        self.after(50, self._check_auto_scroll)
        return None

    def _check_auto_scroll(self):
        try:
            yview = self.text.yview()
            self._auto_scroll = yview[1] >= 0.99
        except Exception:
            pass

    # ---------- Render ----------
    def render(self, lines, cursor_x, cursor_y, history_offset):
        try:
            yview_top = self.text.yview()[0]
        except Exception:
            yview_top = 0.0

        self.text.delete("1.0", "end")

        lines = list(lines)
        cursor_line = history_offset + cursor_y + 1

        if 1 <= cursor_line <= len(lines):
            line_idx = cursor_line - 1
            line_text = lines[line_idx]
            if len(line_text) <= cursor_x:
                line_text = line_text + " " * (cursor_x - len(line_text) + 1)
                lines[line_idx] = line_text

        if lines:
            self.text.insert("1.0", "\n".join(lines))

        if 1 <= cursor_line <= len(lines):
            try:
                pos = f"{cursor_line}.{cursor_x}"
                end_pos = f"{cursor_line}.{cursor_x + 1}"
                self.text.tag_add("cursor", pos, end_pos)
            except Exception:
                pass

        try:
            if self._auto_scroll:
                self.text.see(f"{cursor_line}.0")
            else:
                self.text.yview_moveto(yview_top)
        except Exception:
            pass

    # ---------- Clipboard actions ----------
    def _do_copy(self):
        try:
            selected = self.text.get("sel.first", "sel.last")
            self.text.clipboard_clear()
            self.text.clipboard_append(selected)
        except tk.TclError:
            pass

    def _do_select_all(self):
        try:
            self.text.tag_add("sel", "1.0", "end-1c")
            self.text.mark_set("insert", "1.0")
            self.text.see("insert")
        except Exception:
            pass

    def _do_paste(self):
        try:
            data = self.clipboard_get()
        except Exception:
            return
        if data:
            self.on_key(data)

    def _do_cut(self):
        try:
            selected = self.text.get("sel.first", "sel.last")
            self.text.clipboard_clear()
            self.text.clipboard_append(selected)
        except tk.TclError:
            pass

    # ---------- Right click ----------
    def _on_right_click(self, event=None):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy", command=self._do_copy)
        menu.add_command(label="Select All", command=self._do_select_all)
        menu.add_separator()
        menu.add_command(label="Paste", command=self._do_paste)

        try:
            self.text.get("sel.first", "sel.last")
            menu.entryconfig("Copy", state="normal")
        except tk.TclError:
            menu.entryconfig("Copy", state="disabled")

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    # ---------- Input ----------
    def _on_key_event(self, event):
        keysym = event.keysym

        # Cmd+...
        if event.state & 0x8:
            ch = (event.char or "").lower()
            if ch == "c":
                self._do_copy()
                return "break"
            if ch == "a":
                self._do_select_all()
                return "break"
            if ch == "v":
                self._do_paste()
                return "break"
            if ch == "x":
                self._do_cut()
                return "break"
            return "break"

        # Ctrl+...
        if event.state & 0x4:
            if keysym.lower() == "c":
                self.on_key("\x03")
                return "break"
            if keysym.lower() == "d":
                self.on_key("\x04")
                return "break"
            if keysym.lower() == "z":
                self.on_key("\x1a")
                return "break"
            if len(keysym) == 1 and "a" <= keysym.lower() <= "z":
                code = ord(keysym.lower()) - ord("a") + 1
                self.on_key(chr(code))
                return "break"

        # Special keys
        if keysym == "Return":
            self.on_key("\r")
            return "break"
        if keysym == "BackSpace":
            self.on_key("\x7f")
            return "break"
        if keysym == "Tab":
            self.on_key("\t")
            return "break"
        if keysym == "Escape":
            self.on_key("\x1b")
            return "break"

        arrows = {
            "Up": "\x1b[A", "Down": "\x1b[B",
            "Right": "\x1b[C", "Left": "\x1b[D",
            "Home": "\x1b[H", "End": "\x1b[F",
            "Prior": "\x1b[5~", "Next": "\x1b[6~",
            "Delete": "\x1b[3~",
        }
        if keysym in arrows:
            self.on_key(arrows[keysym])
            return "break"

        # Printable
        if event.char and event.char.isprintable():
            self.on_key(event.char)
            return "break"

        return "break"

    def focus_terminal(self):
        self.text.focus_set()
