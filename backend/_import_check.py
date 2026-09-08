import sys

sys.path.insert(0, r"d:\internship project\Forge")
os_dummy = None
try:
    import backend.main as m
    print("IMPORT backend.main: OK")
    routes = [r.path for r in m.app.routes]
    for p in sorted(set(x for x in routes if x)):
        print("  ", p)
except Exception as e:
    import traceback
    print("IMPORT FAILED:", type(e).__name__, e)
    traceback.print_exc()