"""Optional external ROMA integration helper."""

import importlib
import os

roma_framework = None
ROMA_AVAILABLE = False

module_name = os.getenv('ROMA_FRAMEWORK_MODULE')
if module_name:
    try:
        roma_framework = importlib.import_module(module_name)
        ROMA_AVAILABLE = True
    except Exception as exc:
        print(f"Unable to import ROMA_FRAMEWORK_MODULE={module_name}: {exc}")

__all__ = ["ROMA_AVAILABLE", "roma_framework"]
