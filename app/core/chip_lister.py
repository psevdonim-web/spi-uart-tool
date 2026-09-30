"""
List of supported chips via libflashrom.

Uses flashrom_supported_flash_chips() — works without the flashrom CLI.
"""

from .libflashrom import LibFlashrom


def list_chips(lib: LibFlashrom = None) -> list:
    """
    Return sorted list of chip names.
    If lib is None — creates a temporary one.
    """
    own_lib = False
    if lib is None:
        lib = LibFlashrom()
        own_lib = True

    try:
        chips = lib.supported_flash_chips()
    except Exception:
        chips = []
    finally:
        if own_lib:
            try:
                lib.close()
            except Exception:
                pass

    return chips
