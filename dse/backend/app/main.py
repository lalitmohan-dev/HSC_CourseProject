from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.projects import router as projects_router

app = FastAPI(
    title="DSE Framework",
    description="Hardware-Software Co-design Design Space Exploration",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
