from pytest import fixture, raises

from .. import Rule
from ..rule import get_rule
from . import PytestRequest


@fixture(params=(
    "generic.time.NegateRule",
    "generic.time.EitherRule",
    "generic.time.BothRule",
    "generic.time.ResolveAtTime",
    "generic.value.ResolveToValue",
    "generic.value.ResolveRandomSeed",
    "generic.value.ResolveRandomIndex",
    "generic.value.ResolveMultipleValues",
    "manifold.value.CurrentValueRule",
    "manifold.value.PopularValueRule",
    "manifold.value.ResolveToUserProfit",
    "manifold.value.ResolveToUserCreatedVolume",
    "github.time.ResolveWithPR",
    "github.value.ResolveToPR",
    "github.value.ResolveToPRDelta",
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
