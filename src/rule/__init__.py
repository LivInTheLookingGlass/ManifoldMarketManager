from abc import abstractmethod
from importlib import import_module
from pathlib import Path
from sys import modules
from traceback import print_exc
from typing import TYPE_CHECKING, Literal, Mapping, Optional, Sequence, Type, Union, cast
from warnings import warn

from .. import AnyResolution, Rule

if TYPE_CHECKING:
    from ..market import Market


def get_rule(type_: str) -> Type[Rule]:
    """Dynamically import and return a rule type by name."""
    ret = getattr(
        import_module(".".join(("", *type_.split(".")[:-1])), __name__),
        type_.split(".")[-1]
    )
    if issubclass(ret, Rule):
        return cast(Type[Rule], ret)
    raise NameError()


class DoResolveRule(Rule):
    """The subtype of rule which determines if a market should resolve, returning a bool."""

    @abstractmethod
    def value(self, market: "Market") -> bool:
        """Return True if a market should resolve."""
        raise NotImplementedError()


class ResolutionValueRule(Rule):
    """The subtype of rule which determines what a market should resolve to."""

    @abstractmethod
    def _value(
        self,
        market: "Market"
    ) -> AnyResolution:
        ...

    def value(
        self,
        market: "Market",
        format: Optional[Literal['BINARY', 'PSEUDO_NUMERIC', 'FREE_RESPONSE', 'MULTIPLE_CHOICE']] = None
    ) -> AnyResolution:
        """Return the resolution value of a market, appropriately formatted for its market type."""
        if format is None:
            format = market.market.outcomeType
        ret: Union[str, AnyResolution] = self._value(market)
        if ret is None:
            return ret
        elif ret == "CANCEL":
            return ret
        elif format in ('BINARY', 'PSEUDO_NUMERIC'):
            if not isinstance(ret, str) and isinstance(ret, Sequence) and len(ret) == 1:
                ret = ret[0]
            elif isinstance(ret, Mapping) and len(ret) == 1:
                ret = cast(Union[str, int, float], next(iter(ret.items()))[0])

            if isinstance(ret, (int, float, )):
                return ret
            elif isinstance(ret, str):
                ret = float(ret)
                if ret.is_integer():
                    return int(ret)
                return ret

            raise TypeError(ret, format, market)
        elif format in ('FREE_RESPONSE', 'MULTIPLE_CHOICE'):
            if isinstance(ret, Mapping):
                return {int(val): share for val, share in ret.items()}
            elif isinstance(ret, Sequence) and len(ret) == 1:
                ret = ret[0]

            if isinstance(ret, str):
                return {int(ret): 1}
            elif isinstance(ret, int):
                return {ret: 1}
            elif isinstance(ret, float):
                if ret.is_integer():
                    return {int(ret): 1}
                raise ValueError()

            raise TypeError(ret, format, market)
        raise ValueError()


__all__ = ['get_rule', 'DoResolveRule', 'ResolutionValueRule']

# dynamically load optional plugins where able to
exempt = {'__init__', '__main__', '__pycache__'}
for entry in Path(__file__).parent.iterdir():
    name = entry.name.rstrip(".py")
    if name.startswith('.') or name in exempt:
        continue
    try:
        setattr(modules[__name__], name, import_module("." + name, __name__))
        __all__.append(name)
    except ImportError:
        print_exc()
        warn(f"Unable to import extension module: {name}")
