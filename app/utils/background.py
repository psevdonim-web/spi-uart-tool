"""
Background task helper.

tkinter is not thread-safe: widgets can only be updated from the main thread.
Long-running operations (flashrom, serial reads) must run in a separate thread,
and their results must be delivered back to the main thread via root.after().

Usage:

    def on_done(result, error):
        if error:
            log("Error: " + str(error))
        else:
            log("Result: " + str(result))

    run_in_background(
        root=root,
        work=lambda: detect_chip(),   # runs in thread
        on_done=on_done,               # runs in main thread
    )
"""

import threading
import traceback
from typing import Any, Callable


def run_in_background(root,
                      work: Callable[[], Any],
                      on_done: Callable[[Any, Exception], None]):
    """
    Run work() in a separate thread.
    When done, call on_done(result, error) in the main thread via root.after().

    work     — function without arguments, returns a result.
    on_done  — function(result, error). Exactly one of them will be None.
    """
    def thread_body():
        result = None
        error = None
        try:
            result = work()
        except Exception as e:
            error = e
            traceback.print_exc()

        # Return to main thread
        root.after(0, lambda: on_done(result, error))

    t = threading.Thread(target=thread_body, daemon=True)
    t.start()
