"""Unit tests for app.utils.comfun utility functions."""
import pytest
from app.utils.comfun import generate_unique_id


class TestGenerateUniqueId:
    def test_returns_string(self):
        assert isinstance(generate_unique_id(), str)

    def test_non_empty(self):
        assert generate_unique_id() != ""

    def test_with_prefix(self):
        result = generate_unique_id(prefix="CMP-")
        assert result.startswith("CMP-")

    def test_two_calls_are_different(self):
        a = generate_unique_id()
        b = generate_unique_id()
        assert a != b

    def test_length_param_truncates(self):
        result = generate_unique_id(length=6)
        assert len(result) <= 6

    def test_length_zero_returns_empty(self):
        result = generate_unique_id(length=0)
        assert result == ""

    def test_prefix_with_length(self):
        result = generate_unique_id(prefix="TEST-", length=4)
        # The core is length characters; prefix is prepended
        assert result.startswith("TEST-")
        core = result[len("TEST-"):]
        assert len(core) <= 4
