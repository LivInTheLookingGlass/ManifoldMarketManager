from os import getenv

from src import (market, rule)


def main():
    if not all(getenv(x) for x in ("ManifoldAPIKey", "GithubAPIKey")):
        raise EnvironmentError("Please call source env.sh first")

    c = market.get_client()
    apim = c.get_market_by_slug("test-of-the-api-please-ignore")
    m = market.Market(c, apim)
    m.do_resolve_rules.append(rule.ResolveWithPR('gappleto97', 'ManifoldMarketManager', 2))
    m.resolve_to_rules.append(rule.ResolveToPR('gappleto97', 'ManifoldMarketManager', 2))
    print(m.should_resolve())
    print(m.resolve_to())
