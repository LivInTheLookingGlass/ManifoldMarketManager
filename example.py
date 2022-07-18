from datetime import datetime, timedelta
from pathlib import Path
from pickle import dumps, loads
from os import getenv
from sqlite3 import connect, register_adapter, register_converter, PARSE_COLNAMES, PARSE_DECLTYPES

from src import (market, rule)

register_adapter(rule.Rule, dumps)
register_converter("Rule", loads)
register_adapter(market.Market, dumps)
register_converter("Market", loads)


def require_env(func):
    def foo(*args, **kwargs):
        if not all(getenv(x) for x in ("ManifoldAPIKey", "GithubAPIKey", "DBName")):
            raise EnvironmentError("Please call 'source env.sh' first")
        return func(*args, **kwargs)

    return foo


@require_env
def register_db():
    do_initialize = not Path(getenv("DBName")).exists()
    conn = connect(getenv("DBName"), detect_types=PARSE_COLNAMES | PARSE_DECLTYPES)
    if do_initialize:
        conn.execute("CREATE TABLE markets "
                     "(id INTEGER, market Market, check_rate REAL, last_checked TIMESTAMP);")

        markets = []
        initial = [
            ('how-many-days-after-20220715-will-r', ('manifoldmarkets', 'manifold', 655), datetime(2022, 7, 15)),
            ('how-many-days-after-20220715-will-l', ('manifoldmarkets', 'manifold', 588), datetime(2022, 7, 15)),
            ('in-how-many-days-from-20220718-will', ('manifoldmarkets', 'manifold', 561), datetime(2022, 7, 18)),
        ]
        for slug, pr, start in initial:
            mkt = market.Market.from_slug(slug)
            mkt.do_resolve_rules.append(rule.ResolveWithPR(*pr))
            mkt.resolve_to_rules.append(rule.ResolveToPRDelta(*pr, start))
            markets.append(mkt)

        for idx, mkt in enumerate(markets):
            conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
    return conn


@require_env
def main():
    conn = register_db()
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
        if not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)):
            print(f"Currently checking ID {id_}: {mkt.market.question}")
            if mkt.should_resolve() and input(
               f"Hey, we need to resolve {id_} to {mkt.resolve_to()}. (y/N?").lower().startswith('y'):
                mkt.resolve()
                conn.execute(
                    "DELETE FROM markets WHERE id = ?;",
                    (id_, )
                )
            else:
                conn.execute(
                    "UPDATE markets SET last_checked = ? WHERE id = ?;",
                    (datetime.now(), id_)
                )


if __name__ == '__main__':
    main()
