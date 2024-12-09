"""
Unit and regression test for the mdi_rexmd package.
"""

# Import package, test suite, and other packages as needed
import sys

import pytest

import mdi_rexmd


def test_mdi_rexmd_imported():
    """Sample test, will always pass so long as import statement worked."""
    assert "mdi_rexmd" in sys.modules
