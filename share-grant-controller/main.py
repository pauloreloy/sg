import uvicorn
from bootstrap import create_app
from infrastructure.config import settings

app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.controller_host,
        port=settings.controller_port,
        reload=False,
    )
