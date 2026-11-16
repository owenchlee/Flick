"""Headless CI has no display, and pyautogui reads $DISPLAY at import time; stub it there so app modules import."""
import os
import sys
import types

if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    stub = types.ModuleType("pyautogui")
    stub.FAILSAFE = False
    stub.PAUSE = 0
    stub.PyAutoGUIException = Exception
    stub.size = lambda: (1920, 1080)
    for name in ("moveTo", "click", "mouseDown", "mouseUp", "scroll"):
        setattr(stub, name, lambda *a, **k: None)
    sys.modules.setdefault("pyautogui", stub)
