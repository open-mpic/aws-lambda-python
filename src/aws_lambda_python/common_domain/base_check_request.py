from abc import ABC
from pydantic import BaseModel


class BaseCheckRequest(BaseModel, ABC):
    domain_or_ip_target: str
