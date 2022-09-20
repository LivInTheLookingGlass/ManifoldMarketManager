from pytest import fixture

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
    return request.param


def test_import_rule(rule_name: str) -> None:
    assert issubclass(get_rule(rule_name), Rule)
