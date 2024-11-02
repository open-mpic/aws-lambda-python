from pydantic import BaseModel


class MpicValidationError(BaseModel):
    error_type: str | None = None
    error_message: str | None = None
