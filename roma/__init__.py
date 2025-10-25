"""Optional ROMA integration helper.

This module detects whether the external ROMA framework is installed and
exposes a simple flag and the imported module (if available). The rest of the
codebase uses the flag to decide whether to delegate to ROMA or use the
local fallback implementations.
"""

try:
	import roma as roma_framework  # type: ignore
	ROMA_AVAILABLE = True
except Exception:
	roma_framework = None
	ROMA_AVAILABLE = False

__all__ = ["ROMA_AVAILABLE", "roma_framework"]
