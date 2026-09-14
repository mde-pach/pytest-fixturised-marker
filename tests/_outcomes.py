import pytest


def deselected(result: pytest.RunResult) -> int:
    return int(result.parseoutcomes().get("deselected", 0))
