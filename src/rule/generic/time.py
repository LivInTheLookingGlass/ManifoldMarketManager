from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, cast

from .. import DoResolveRule, get_rule

if TYPE_CHECKING:
    from ...market import Market


@dataclass
class NegateRule(DoResolveRule):
    """Negate another DoResolveRule."""

    child: DoResolveRule

    def value(self, market: 'Market') -> bool:
        """Return the negation of the underlying rule."""
        return not self.child.value(market)

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return (
            f"{'  ' * indent}- If the rule below resolves False\n" +
            self.child.explain_abstract(indent + 1, **kwargs)
        )

    def explain_specific(self, market: 'Market', indent: int = 0, sig_figs: int = 4) -> str:
        return (
            f"{'  ' * indent}- If the rule below resolves False (-> {self.value(market)})\n" +
            self.child.explain_specific(market, indent + 1)
        )

    @classmethod
    def from_dict(cls, env: Dict[str, Any]) -> 'NegateRule':
        """Take a dictionary and return an instance of the associated class."""
        if "child" in env:
            try:
                type_, kwargs = env["child"]
                env["child"] = get_rule(type_).from_dict(kwargs)
            except Exception:
                pass
        return cast(NegateRule, super().from_dict(env))


@dataclass
class EitherRule(DoResolveRule):
    """Return the OR of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market: 'Market') -> bool:
        """Return True iff at least one underlying rule returns True."""
        return self.rule1.value(market) or self.rule2.value(market)

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def explain_specific(self, market: 'Market', indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If either of the rules below resolves True (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret

    @classmethod
    def from_dict(cls, env: Dict[str, Any]) -> 'EitherRule':
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = get_rule(type_).from_dict(kwargs)
                except Exception:
                    pass
        return cast(EitherRule, super().from_dict(env))


@dataclass
class BothRule(DoResolveRule):
    """Return the AND of two other DoResolveRules."""

    rule1: DoResolveRule
    rule2: DoResolveRule

    def value(self, market: 'Market') -> bool:
        """Return True iff both underlying rules return True."""
        return self.rule1.value(market) and self.rule2.value(market)

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True\n"
        ret += self.rule1.explain_abstract(indent + 1, **kwargs)
        ret += self.rule2.explain_abstract(indent + 1, **kwargs)
        return ret

    def explain_specific(self, market: 'Market', indent: int = 0, sig_figs: int = 4) -> str:
        ret = f"{'  ' * indent}- If both of the rules below resolves True (-> {self.value(market)})\n"
        ret += self.rule1.explain_specific(market, indent + 1)
        ret += self.rule2.explain_specific(market, indent + 1)
        return ret

    @classmethod
    def from_dict(cls, env: Dict[str, Any]) -> 'BothRule':
        """Take a dictionary and return an instance of the associated class."""
        for name in ('rule1', 'rule2'):
            if name in env:
                try:
                    type_, kwargs = env[name]
                    env[name] = get_rule(type_).from_dict(kwargs)
                except Exception:
                    pass
        return cast(BothRule, super().from_dict(env))


@dataclass
class ResolveAtTime(DoResolveRule):
    """Return True if the specified time is in the past."""

    resolve_at: datetime

    def value(self, market: 'Market') -> bool:
        """Return True iff the current time is after resolve_at."""
        try:
            return datetime.utcnow() >= self.resolve_at
        except TypeError:
            return datetime.now() >= self.resolve_at

    def explain_abstract(self, indent: int = 0, **kwargs: Any) -> str:
        return f"{'  ' * indent}- If the current time is past {self.resolve_at}\n"
