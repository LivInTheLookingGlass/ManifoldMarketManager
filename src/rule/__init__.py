from __future__ import annotations

from importlib import import_module
from typing import Any, Type, cast

from .. import AnyResolution, Rule
from ..util import dynamic_import


def get_rule(type_: str) -> Type[Rule[Any]]:
    """Dynamically import and return a rule type by name."""
    ret = getattr(
        import_module(".".join(("", *type_.split(".")[:-1])), __name__),
        type_.split(".")[-1]
    )
    if issubclass(ret, Rule):
        return cast(Type[Rule[Any]], ret)
    raise NameError()


class DoResolveRule(Rule[bool]):
    """The subtype of rule which determines if a market should resolve, returning a bool."""


class ResolutionValueRule(Rule[AnyResolution]):
    """The subtype of rule which determines what a market should resolve to."""


__all__ = ['get_rule', 'DoResolveRule', 'ResolutionValueRule']

# dynamically load optional plugins where able to
exempt = {'__init__', '__main__', '__pycache__'}
dynamic_import(__file__, __name__, __all__, exempt)
