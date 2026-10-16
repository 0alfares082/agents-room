"""Every test runs with the same small config, never the user's own config.json."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

TEST_CONFIG = {
    "projects": [
        {"name": "Acme", "keywords": ["acme"], "color": "#5cc8f5", "showAs": "Nova"},
        {"name": "Globex", "keywords": ["globex"], "color": "#b69cff", "showAs": "Atlas"},
        {"name": "Content", "keywords": ["reel"], "color": "#ff7ad9", "showAs": "Content"},
    ],
    "showAliases": {"John": "Sam"},
    "projectsDir": Path("/nonexistent"),
    "ledgerDir": None,
}


@pytest.fixture(autouse=True)
def test_config():
    saved = dict(config.CONFIG)
    config.CONFIG.clear()
    config.CONFIG.update(TEST_CONFIG)
    yield
    config.CONFIG.clear()
    config.CONFIG.update(saved)
