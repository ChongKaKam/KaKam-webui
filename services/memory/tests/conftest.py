import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'services/memory'))
sys.path.insert(0, str(ROOT / 'backend'))

# Import the adapter namespace without executing Open WebUI's CLI entrypoint.
if 'open_webui' not in sys.modules:
    package = types.ModuleType('open_webui')
    package.__path__ = [str(ROOT / 'backend/open_webui')]
    sys.modules['open_webui'] = package
