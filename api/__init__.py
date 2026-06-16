from importlib import import_module
from pathlib import Path
import sys


APP_PATH = Path(__file__).resolve().parent.parent / "app"
__path__ = [str(APP_PATH)]

app = import_module("app")
sys.modules["api"] = app
__all__ = getattr(app, "__all__", [])
