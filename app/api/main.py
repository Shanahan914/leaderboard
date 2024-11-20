from fastapi import FastAPI
from .routes import router as all_routes
from .database import create_db_and_tables
import uvicorn 

app = FastAPI(title='leaderboard_api', description='an api for a leaderboard service using redis')

app.include_router(all_routes)

@app.on_event("startup")
def on_strartup():
    create_db_and_tables()

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)