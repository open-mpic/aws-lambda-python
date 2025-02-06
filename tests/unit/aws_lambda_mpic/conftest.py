# conftest.py
import logging
from io import StringIO
import pytest


@pytest.fixture(autouse=True)
def setup_logging():
    # Clear existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    log_output = StringIO()  # to be able to inspect what gets logged
    handler = logging.StreamHandler(log_output)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # Configure fresh logging
    logging.basicConfig(handlers=[handler])

    yield log_output
