"""The toy-graph closed forms hold symbolically and against igraph PRPACK (see verify_margin.py)."""
import importlib.util
from pathlib import Path


def test_verify_margin_all_checks_pass():
    spec = importlib.util.spec_from_file_location("verify_margin", Path(__file__).with_name("verify_margin.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
