from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, path: str):
    print(f"[{request.method}] /{path}")
    print("Headers:", request.headers)
    print("Cookies:", request.cookies)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8101)
