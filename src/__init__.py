from pathlib import Path
from pickle import dumps, loads
from sqlite3 import register_adapter, register_converter
from sys import path as _sys_path
from typing import Dict, Optional, Union

_sys_path.append(str(Path(__file__).parent.joinpath("PyManifold")))

from pymanifold.types import DictDeserializable  # noqa: E402


class Rule(DictDeserializable):
    def value(self, market: 'Market') -> Optional[Union[int, float, str, Dict[int, float]]]:
        raise NotImplementedError()


from . import market  # noqa: E402
from . import rule  # noqa: E402
from .market import Market  # noqa: E402
from .rule import DoResolveRule, ResolutionValueRule  # noqa: E402

register_adapter(rule.Rule, dumps)
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)

__version_info__ = (0, 2, 0, 0, 0)
__all__ = ("__version_info__", "market", "rule", "Market", "DoResolveRule", "ResolutionValueRule", "Rule")
