from pydantic import BaseModel


class ValidationError(BaseModel):
    error_type: str | None = None
    error_message: str | None = None
