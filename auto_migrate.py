import os
import sys
import time
import subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class ModelChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return

        # Watch every Python file inside the models folder
        if "/models/" not in event.src_path.replace("\\", "/"):
            return

        if not event.src_path.endswith(".py"):
            return

        print(f"\nModel changed: {event.src_path}")

        subprocess.run([sys.executable, "manage.py", "makemigrations"])
        subprocess.run([sys.executable, "manage.py", "migrate"])

if __name__ == "__main__":

    event_handler = ModelChangeHandler()

    observer = Observer()

    observer.schedule(
        event_handler,
        BASE_DIR,
        recursive=True
    )

    observer.start()

    print("Watching Django models.py files...")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        observer.stop()

    observer.join()