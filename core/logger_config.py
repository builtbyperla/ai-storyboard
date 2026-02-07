"""
Centralized logging configuration using loguru.
Provides async-safe console logging with structured output.
"""
import sys
from loguru import logger

def setup_logger():
    """
    Configure loguru for async console logging.
    Removes default handler and adds a new one with custom format.
    """
    # Remove the default handler
    logger.remove()
    
    # Add console handler with custom format
    logger.add(
        sys.stdout,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="DEBUG",
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    return logger

# Initialize logger on module import
logger = setup_logger()
