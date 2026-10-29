from fastapi import FastAPI

app = FastAPI(title="Meridian")


@app.get("/health")
def health():
    return {"status": "ok"}

