"""Rebuild semantic embeddings from the command line. Usage: python scripts/rebuild_embeddings.py [failed|all]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.app.db import SessionLocal
from server.app.services import index_service

mode = sys.argv[1] if len(sys.argv) > 1 else "failed"
index_service.rebuild(SessionLocal, mode, 0)
print(index_service.PROGRESS)
