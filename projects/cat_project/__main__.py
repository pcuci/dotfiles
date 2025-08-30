"""
This file allows the package to be run as an executable using `python -m catp`.
It serves as the main entry point, calling the command-line interface function.
"""
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())