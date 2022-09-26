from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ... import BinaryResolution
from .. import DoResolveRule
from . import BinaryRule, UnaryRule

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from ...market import Market


class NegateRule(UnaryRule[BinaryResolution]):
    """Negate another DoResolveRule."""

    def _value(self, market: Market) -> bool:
        return not self.child._value(market)

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the rule below resolves False\n{self.child.explain_abstract(indent + 1, **kwargs)}"

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        return f"{'  ' * indent}- If the rule below resolves False (-> {self.value(market)})\n" +\
               self.child.explain_specific(market, indent + 1)


class EitherRule(BinaryRule[BinaryResolution]):
    """Return the OR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) or bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True (-> {self.value(market, format='NONE')})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class BothRule(BinaryRule[BinaryResolution]):
    """Return the AND of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) and bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class NANDRule(BinaryRule[BinaryResolution]):
    """Return the NAND of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) and self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If one or more of the rules below resolves False\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If one or more of the rules below resolves False (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class NeitherRule(BinaryRule[BinaryResolution]):
    """Return the NOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not (self.rule1._value(market) or self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves False\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves False (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class XORRule(BinaryRule[BinaryResolution]):
    """Return the XOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(bool(self.rule1._value(market)) ^ bool(self.rule2._value(market)))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If exactly one of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If exactly one of the rules below resolves True (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class XNORRule(BinaryRule[BinaryResolution]):
    """Return the XNOR of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return bool(self.rule1._value(market)) == bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolve to the same value\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolve to the same value (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


class ImpliesRule(BinaryRule[BinaryResolution]):
    """Return the implication of two other DoResolveRules."""

    def _value(self, market: Market) -> bool:
        return not self.rule1._value(market) or bool(self.rule2._value(market))

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If next rule resolves False, or both below resolve True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def _explain_specific(self, market: Market, indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If next rule resolves False, or both below resolve True (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret


@dataclass
class ResolveAtTime(DoResolveRule):
    """Return True if the specified time is in the past."""

    resolve_at: datetime

    def _value(self, market: Market) -> bool:
        """Return True iff the current time is after resolve_at."""
        try:
            return datetime.now(timezone.utc) >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at

    def _explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the current time is past {self.resolve_at}\n"
