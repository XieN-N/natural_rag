from __future__ import annotations
import logging
from contextlib import contextmanager
from pathlib import Path
import sys


def remove_handlers(logger: logging.Logger):
    for handler in logger.handlers[:]:
        handler.flush()
        logger.removeHandler(handler)
        handler.close()

def redirect_to_stdout(logger: logging.Logger):
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('%(message)s'))
    remove_handlers(logger)
    logger.addHandler(stdout_handler)

def redirect_to_file(logger: logging.Logger, path: str | Path):
    file_handler = logging.FileHandler(Path(path), mode='w')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    remove_handlers(logger)
    logger.addHandler(file_handler)

@contextmanager
def log_to_file(logger: logging.Logger, path: str | Path):
    """Temporarily captures a logger's output to a file, restoring local state afterward (cringe)."""
    # 1. Save original state
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate
    
    # 2. Isolate the logger and clear existing handlers
    logger.propagate = False
    for handler in original_handlers:
        logger.removeHandler(handler)
        
    # 3. Attach temporary file handler
    file_handler = logging.FileHandler(Path(path), mode='w')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(file_handler)
    
    try:
        yield
    finally:
        # 4. Clean up file handler
        file_handler.flush()
        file_handler.close()
        logger.removeHandler(file_handler)
        
        # 5. Restore original state exactly as it was
        for handler in original_handlers:
            logger.addHandler(handler)
        logger.propagate = original_propagate