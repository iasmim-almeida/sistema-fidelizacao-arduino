import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Wrapper do seed para a raiz do projeto
seed_script = os.path.join(os.path.dirname(__file__), "database", "seeds", "seed.py")
with open(seed_script, encoding="utf-8") as f:
    exec(f.read())
