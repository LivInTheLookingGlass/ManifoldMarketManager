from abc import abstractmethod
from importlib import import_module
from typing import Literal, Mapping, Union, Dict, Sequence

from .. import Rule


def get_rule(type_):
    return getattr(
        import_module(".".join(("", *type_.split(".")[:-1])), __name__),
        type_.split(".")[-1]
    )


class DoResolveRule(Rule):
    """The subtype of rule which determines if a market should resolve, returning a bool."""

    @abstractmethod
    def value(self, market) -> bool:
        raise NotImplementedError()


class ResolutionValueRule(Rule):
    """The subtype of rule which determines what a market should resolve to."""

    @abstractmethod
    def _value(
        self,
        market
    ) -> Union[int, float, str, Dict[Union[str, int, float], float]]:
        ...

    def value(
        self,
        market,
        format: Literal['BINARY', 'PSEUDO_NUMERIC', 'FREE_RESPONSE', 'MULTIPLE_CHOICE'] = 'BINARY'
    ) -> Union[int, float, str, Dict[Union[str, int, float], float]]:
        ret = self._value(market)
        if ret in (None, 'CANCEL'):
            return ret
        elif format in ('BINARY', 'PSEUDO_NUMERIC'):
            if isinstance(ret, Sequence) and len(ret) == 1:
                ret = ret[0]
            elif isinstance(ret, Mapping) and len(ret) == 1:
                ret = tuple(ret.items())[0][0]

            if isinstance(ret, (int, float, )):
                return ret
            elif isinstance(ret, str):
                return float(ret)

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

# from .manifold.value import *
# from .github.time import *
# from .github.value import *
# from .generic import *
