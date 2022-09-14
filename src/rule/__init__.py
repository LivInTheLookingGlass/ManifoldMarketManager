from typing import Literal, Union, Dict, Sequence

from .. import Rule


class DoResolveRule(Rule):
    """The subtype of rule which determines if a market should resolve, returning a bool."""

    def value(self, market) -> bool:
        raise NotImplementedError()


class ResolutionValueRule(Rule):
    """The subtype of rule which determines what a market should resolve to."""

    def value(
        self,
        market,
        format: Literal['BINARY', 'PSEUDO_NUMERIC', 'FREE_RESPONSE', 'MULTIPLE_CHOICE'] = 'BINARY'
    ) -> Union[int, float, str, Dict[Union[str, int, float], float]]:
        ret = self._value(market)
        if ret in (None, 'CANCEL'):
            return ret
        elif format in ('BINARY', 'PSEUDO_NUMERIC'):
            if isinstance(ret, (int, float, )):
                return ret
            elif isinstance(ret, str):
                return float(ret)
            elif isinstance(ret, Sequence) and len(ret) == 1:
                return float(ret[0])
            elif isinstance(ret, dict) and len(ret) == 1:
                return float(ret.popitem()[0])
            else:
                raise TypeError(ret, format, market)
        elif format in ('FREE_RESPONSE', 'MULTIPLE_CHOICE'):
            if isinstance(ret, dict):
                return ret
            elif isinstance(ret, (str, int, float, )):
                return {ret: 1}
            elif isinstance(ret, Sequence) and len(ret) == 1:
                return {ret[0]: 1}
            else:
                raise TypeError(ret, format, market)
        raise ValueError()

# from .manifold.value import *
# from .github.time import *
# from .github.value import *
# from .generic import *
