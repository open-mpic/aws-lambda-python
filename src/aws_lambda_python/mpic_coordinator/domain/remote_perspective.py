from pydantic import BaseModel


class RemotePerspective(BaseModel):
    code: str
    name: str | None = None
    rir: str
    too_close_codes: list[str] | None = []

    def region_id(self):
        return f"{self.rir}.{self.code}"

    def is_perspective_too_close(self, perspective):
        return perspective.code in self.too_close_codes
