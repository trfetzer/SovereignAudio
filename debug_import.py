import sys
import traceback

try:
    import server
    print("Import successful")
except Exception:
    traceback.print_exc()
