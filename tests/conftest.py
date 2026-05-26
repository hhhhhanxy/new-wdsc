import sys
import os

# Add parent directory to path so we can import web module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure pytest to not look in the parent directory
import pytest
def pytest_configure(config):
    # Set the test paths to only look in tests directory
    config.option.testpaths = ['tests']
