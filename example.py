from argparse import ArgumentParser
from datetime import datetime, timedelta
from pathlib import Path
from pickle import dumps, loads
from os import getenv
from sqlite3 import connect, register_adapter, register_converter, PARSE_COLNAMES, PARSE_DECLTYPES
from sys import exit
from typing import cast, Tuple

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
        conn.commit()
    return conn


def watch_reply(id_, mkt):
    conn = register_db()
    if input(
            f"Hey, we need to resolve {id_} to {mkt.resolve_to()}. It currently has a value of "
            f"{mkt.current_answer()}. (y/N)?"
    ).lower().startswith('y'):
        mkt.resolve()
        conn.execute(
            "DELETE FROM markets WHERE id = ?;",
            (id_, )
        )
        conn.commit()


@require_env
def main():
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
        print(f"Currently checking ID {id_}: {mkt.market.question}", end=' ')
        if not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)):
            print('...', end=' ')
            if mkt.should_resolve():
                print('...', end=' ')
                watch_reply(id_, mkt)

        conn.execute(
            "UPDATE markets SET last_checked = ? WHERE id = ?;",
            (datetime.now(), id_)
        )
        conn.commit()
        print()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-s', '--add-slug', action='store', dest='slug')
    parser.add_argument('-i', '--add-id', action='store', dest='id_')
    parser.add_argument('-u', '--add-url', action='store', dest='url')
    parser.add_argument('-c', '--check-rate', action='store', dest='rate')
    parser.add_argument('-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner-repo-num"')
    parser.add_argument('-rd', '--rel-date', action='store', dest='pr_date', help='Please give as "YEAR-MONTH-DAY"')
    parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

    args = parser.parse_args()

    if any((args.slug, args.id_, args.url)):
        if args.url:
            args.slug = args.url.split('/')[-1]

        if args.slug:
            mkt = market.Market.from_slug(args.slug)
        else:
            mkt = market.Market.from_id(args.id)

        if args.pr_slug:
            pr_ = list(args.pr_slug.split('-'))
            pr_[-1] = int(pr_[-1])
            pr = cast(Tuple[str, str, int], tuple(pr_))
            mkt.do_resolve_rules.append(rule.ResolveWithPR(*pr))
            if args.pr_date:
                date = cast(Tuple[int, int, int], tuple(int(x) for x in args.pr_date.split('-')))
                mkt.resolve_to_rules.append(rule.ResolveToPRDelta(*pr, datetime(*date)))
            elif args.pr_bin:
                mkt.resolve_to_rules.append(rule.ResolveToPR(*pr))
            else:
                raise ValueError("No resolve rule provided")
        else:
            raise ValueError("Cannot add unmanaged market")

        conn = register_db()

        idx = max(conn.execute("SELECT id FROM markets;")) + 1
        conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
        conn.commit()
        ...
        print("Successfully added!")
        exit(0)

    main()
