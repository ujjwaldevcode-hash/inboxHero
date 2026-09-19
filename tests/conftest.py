import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inboxhero.loader import load_inbox

@pytest.fixture
def messages():
    return load_inbox(ROOT / 'inbox.json')
