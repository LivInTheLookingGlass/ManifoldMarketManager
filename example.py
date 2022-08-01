from argparse import ArgumentParser
from datetime import datetime, timedelta
from pathlib import Path
from os import getenv
from sqlite3 import connect, PARSE_COLNAMES, PARSE_DECLTYPES
from typing import cast, Tuple

from src import (market, rule)


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
            f"\tHey, we need to resolve {id_} to {mkt.resolve_to()}. It currently has a value of "
            f"{mkt.current_answer()}. (y/N)?"
    ).lower().startswith('y'):
        mkt.resolve()
        conn.execute(
            "DELETE FROM markets WHERE id = ?;",
            (id_, )
        )
        conn.commit()


@require_env
def main(refresh: bool = False):
    conn = register_db()
    mkt: market.Market
    for id_, mkt, check_rate, last_checked in conn.execute("SELECT * FROM markets"):
        print(f"Currently checking ID {id_}: {mkt.market.question}")
        check = (refresh or not last_checked or (datetime.now() > last_checked + timedelta(hours=check_rate)))
        print(f'  - [{"x" if check else " "}] Should I check?')
        if check:
            check = mkt.should_resolve()
            print(f'  - [{"x" if check else " "}] Is elligible to resolve (to {mkt.resolve_to()})?')
            if check:
                watch_reply(id_, mkt)

            if mkt.market.isResolved:
                print("  - [x] Market resolved, removing from db")
                conn.execute(
                    "DELETE FROM markets WHERE id = ?;",
                    (id_, )
                )
                conn.commit()

        conn.execute(
            "UPDATE markets SET last_checked = ?, market = ? WHERE id = ?;",
            (datetime.now(), mkt, id_)
        )
        conn.commit()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-s', '--add-slug', action='store', dest='slug')
    parser.add_argument('-i', '--add-id', action='store', dest='id_')
    parser.add_argument('-u', '--add-url', action='store', dest='url')
    parser.add_argument('-c', '--check-rate', action='store', dest='rate', help='Check rate in hours')

    parser.add_argument('-mi', '--min', action='store', dest='max')
    parser.add_argument('-ma', '--max', action='store', dest='min')
    parser.add_argument('-ls', '--log_scale', action='store_true', dest='isLogScale')

    parser.add_argument('-r', '--refresh', action='store_true', dest='refresh')

    parser.add_argument('-rm', '--remove-id', action='append', dest='rm_id', default=[])

    parser.add_argument('-pl', '--poll', action='store_true', dest='poll')
    parser.add_argument('-rd', '--rel-date', action='store', dest='rel_date',
                        help='Please give as "year/month/day". Used in: poll, git PR')

    parser.add_argument('-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner/repo/num"')
    parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

    parser.add_argument('-sk', '--skip', action='store_true')

    args = parser.parse_args()

    for id_ in args.rm_id:
        conn = register_db()
        ((mkt, ), ) = conn.execute(
            "SELECT market FROM markets WHERE id = ?;",
            (id_, )
        )
        if input(f'Are you sure you want to remove {id_}: "{mkt.market.question}" (y/N)?').lower().startswith('y'):
            conn.execute(
                "DELETE FROM markets WHERE id = ?;",
                (id_, )
            )
            conn.commit()

    if any((args.slug, args.id_, args.url)):
        if args.url:
            args.slug = args.url.split('/')[-1]

        if args.slug:
            mkt = market.Market.from_slug(args.slug, min=args.min, max=args.max, isLogScale=args.isLogScale)
        else:
            mkt = market.Market.from_id(args.id, min=args.min, max=args.max, isLogScale=args.isLogScale)
        if mkt.market.outcomeType == "PSEUDO_NUMERIC" and not all((args.min, args.max)):
            raise ValueError("Until Manifold returns these values, record them yourself")

        if args.pr_slug:
            pr_ = list(args.pr_slug.split('/'))
            pr_[-1] = int(pr_[-1])
            pr = cast(Tuple[str, str, int], tuple(pr_))
            mkt.do_resolve_rules.append(rule.ResolveWithPR(*pr))
            if args.rel_date:
                date = cast(Tuple[int, int, int], tuple(int(x) for x in args.rel_date.split('/')))
                mkt.resolve_to_rules.append(rule.ResolveToPRDelta(*pr, datetime(*date)))
            elif args.pr_bin:
                mkt.resolve_to_rules.append(rule.ResolveToPR(*pr))
            else:
                raise ValueError("No resolve rule provided")

        if args.poll:
            if not args.rel_date:
                raise ValueError("No resolve date provided")
            date = cast(Tuple[int, int, int], tuple(int(x) for x in args.rel_date.split('/')))
            mkt.do_resolve_rules.append(rule.ResolveAtTime(datetime(*date)))

        if not all(((mkt.resolve_to_rules or args.poll), mkt.do_resolve_rules)):
            raise ValueError("Cannot add unmanaged market")

        conn = register_db()

        idx = max(conn.execute("SELECT id FROM markets;"))[0] + 1
        conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
        conn.commit()

        print(f"Successfully added as ID {idx}!")

    if not args.skip:
        main(args.refresh)
