"""Tests for main CLI module."""

import pytest


def test_main_import():
    """Test that main module imports without errors."""
    from src import main

    assert hasattr(main, "main")


def test_argument_parser():
    """Test that argparse configuration is valid."""
    from src.main import main
    import sys
    from unittest.mock import patch

    # Just verify the parser doesn't crash on --help
    with patch.object(sys, "argv", ["gh-stars", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # --help exits with 0
        assert exc_info.value.code == 0
