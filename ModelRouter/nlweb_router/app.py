"""Azure Web App entry point for the analysis server."""
import sys
from pathlib import Path

# Add scripts directory to path so imports work
scripts_dir = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Import the Flask app from analysis_server
from analysis_server import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
