from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import fixture, raises

from .. import Rule
from ..rule import get_rule

if TYPE_CHECKING:  # pragma: no cover
    from . import PytestRequest


@fixture(params=(
    "generic.NegateRule",
    "generic.EitherRule",
    "generic.BothRule",
    "generic.NANDRule",
    "generic.NeitherRule",
    "generic.XORRule",
    "generic.XNORRule",
    "generic.ImpliesRule",
    "generic.ResolveAtTime",
    "generic.ResolveToValue",
    "generic.AdditiveRule",
    "generic.MultiplicitiveRule",
    "generic.ModulusRule",
    "generic.ResolveRandomSeed",
    "generic.ResolveRandomIndex",
    "generic.ResolveMultipleValues",
    "github.ResolveWithPR",
    "github.ResolveToPR",
    "github.ResolveToPRDelta",
    "manifold.this.CurrentValueRule",
    "manifold.this.FibonacciValueRule",
    "manifold.this.PopularValueRule",
    "manifold.this.ThisMarketClosed",
    "manifold.other.AmplifiedOddsRule",
    "manifold.other.OtherMarketClosed",
    "manifold.other.OtherMarketResolved",
    "manifold.other.OtherMarketValue",
    "manifold.user.ResolveToUserProfit",
    "manifold.user.ResolveToUserCreatedVolume",
))
def rule_name(request: PytestRequest[str]) -> str:
    """Return the name of an existing rule."""
    return request.param


def test_import_rule(rule_name: str) -> None:
    """Make sure this function can import any existing rule."""
    assert issubclass(get_rule(rule_name), Rule)


def test_import_rule_failure() -> None:
    """Make sure this function can't import arbitrary objects."""
    for rule_name in ["time.sleep", "random.Random"]:
        with raises(Exception):
            get_rule(rule_name)
