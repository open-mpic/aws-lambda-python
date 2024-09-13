from pydantic import BaseModel


class AwsRegion(BaseModel):
    region_code: str
    region_name: str
    rir: str
    too_close_region_codes: list[str]

    def region_id(self):
        return f"{self.rir}.{self.region_code}"

    def is_region_too_close(self, region):
        return region.region_code in self.too_close_region_codes
