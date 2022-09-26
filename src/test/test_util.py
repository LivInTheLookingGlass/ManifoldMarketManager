from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from os import environ
from random import randrange
from secrets import token_hex
from typing import Any, List, cast

from pytest import mark, raises

from .. import Rule
from ..util import explain_abstract, require_env


def test_require_env() -> None:
    """Make sure that we are actually requiring environment variables when specified."""
    for _ in range(10):
        key = token_hex(16)

        @require_env(key)
        def test_func() -> None:
            ...

        orig = environ.get(key)
        try:
            if orig is not None:
                del environ[key]
            with raises(EnvironmentError):
                test_func()
            environ[key] = 'example'
            test_func()
        finally:
            if orig is None:
                del environ[key]
            else:
                environ[key] = orig


@mark.network
def test_explain_abstract() -> None:
    """Make sure that explain_abstract() calls to each of its fed Rules."""
    @dataclass
    class MockObject:
        called: bool = False

        def explain_abstract(self, **kwargs: Any) -> str:
            self.called = True
            return ""

    l1 = [MockObject() for _ in range(randrange(20))]
    l2 = [MockObject() for _ in range(randrange(20))]
    val = explain_abstract(cast(List[Rule[Any]], l1), cast(List[Rule[Any]], l2))
    assert isinstance(val, str)
    for obj in chain(l1, l2):
        assert obj.called
