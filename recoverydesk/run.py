import os
import uvicorn
import sys

if __name__ == "__main__":
    os.environ["DATABASE_URL"] = "postgresql+psycopg://rd_owner:change-me@127.0.0.1:5432/recoverydesk"
    # Ensure the current directory is in PYTHONPATH so absolute imports work
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run("apps.api.main:app", port=8001)
