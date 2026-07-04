# Local development entry point. NOT used on Lambda.
# Run with:  python main.py   (http://127.0.0.1:8000)
from app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=3030, reload=True)
