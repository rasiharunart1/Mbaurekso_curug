import sys
from pathlib import Path

# Add "<project>/src" to sys.path so we can import the vas package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vas.main import App

if __name__ == "__main__":
    app = App()
    app.root.mainloop()