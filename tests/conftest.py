# tests/conftest.py
# Adds backend/ to sys.path for all tests in this directory tree.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
