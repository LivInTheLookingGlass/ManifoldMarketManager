"""Umbrella package for all rules.

Anyone who wants to develop a plugin is welcome to modify the values in this specific namespace. In particular, to add
a rule with your plugin:
1) Add your plugin's rules as a submodule of this using
   `from sys import modules; modules['.'.join((PATH_TO_RULE_MODULE, PATH_TO_YOUR_RULE))] = module[PATH_TO_YOUR_RULE]
2) Append your plugin's namespace to `rule.__all__`
3) Append each of your rules' import paths to `consts.AVAILABLE_RULES`
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Type, cast

from attrs import define

from .. import Rule
from ..consts import AnyResolution
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


@define(slots=False)  # type: ignore
class DoResolveRule(Rule[bool]):
    """The subtype of rule which determines if a market should resolve, returning a bool."""


@define(slots=False)  # type: ignore
class ResolutionValueRule(Rule[AnyResolution]):
    """The subtype of rule which determines what a market should resolve to."""


__all__ = ['get_rule', 'DoResolveRule', 'ResolutionValueRule']

# dynamically load optional plugins where able to
exempt = {'__init__', '__main__', '__pycache__'}
dynamic_import(__file__, __name__, __all__, exempt)
