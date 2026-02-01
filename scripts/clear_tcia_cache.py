#!/usr/bin/env python3
"""Clear TCIA search cache. Run from project root: python scripts/clear_tcia_cache.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcia_service import clear_tcia_cache

count = clear_tcia_cache()
print(f"Cleared {count} TCIA cache files.")
