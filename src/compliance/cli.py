import logging

from compliance.app import run_pipeline
from compliance.logging_utils import configure_logging

if __name__ == "__main__":
    configure_logging(level="DEBUG", is_tutorial=False)
    run_pipeline()