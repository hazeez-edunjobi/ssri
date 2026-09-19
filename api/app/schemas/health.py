from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str
