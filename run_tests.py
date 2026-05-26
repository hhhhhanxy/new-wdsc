#!/usr/bin/env python3
"""
Simple script to run tests, handling the root __init__.py issue.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    # Save the root __init__.py if it exists
    root_init = Path("__init__.py")
    backup_init = Path("__init__.py.backup")

    if root_init.exists():
        print(f"Temporarily renaming {root_init} to {backup_init}")
        shutil.move(root_init, backup_init)

    try:
        # Run the tests
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_models.py", "-v"],
            cwd=Path.cwd(),
            capture_output=False
        )
        return result.returncode
    finally:
        # Restore the root __init__.py
        if backup_init.exists():
            print(f"Restoring {backup_init} to {root_init}")
            shutil.move(backup_init, root_init)

if __name__ == "__main__":
    sys.exit(main())
