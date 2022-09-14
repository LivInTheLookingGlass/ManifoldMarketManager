from argparse import ArgumentParser
from datetime import datetime
from logging import basicConfig, getLogger, DEBUG, INFO
from os import getenv
from typing import cast, Optional, Tuple

from .application import register_db, main
from .market import Market
from .rule.generic import ResolveAtTime, ResolveRandomIndex
from .rule.github.time import ResolveWithPR
from .rule.github.value import ResolveToPR, ResolveToPRDelta
from .rule.manifold.value import CurrentValueRule, RoundValueRule

# Enable logging
basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=(INFO if not getenv("DEBUG") else DEBUG),
    filename=getenv("LogFile"),
)
logger = getLogger(__name__)

parser = ArgumentParser()
parser.add_argument('-s', '--add-slug', action='store', dest='slug')
parser.add_argument('-i', '--add-id', action='store', dest='id_')
parser.add_argument('-u', '--add-url', action='store', dest='url')
parser.add_argument('-c', '--check-rate', action='store', dest='rate', help='Check rate in hours')

parser.add_argument('-r', '--refresh', action='store_true', dest='refresh',
                    help="Ignore time last checked and look at all markets immediately")

parser.add_argument('-rm', '--remove-id', action='append', dest='rm_id', default=[],
                    help="Remove a specific market from management. May be repeated.")

parser.add_argument('-rnd', '--round', action='store_true')
parser.add_argument('-cur', '--current', action='store_true')
parser.add_argument('-rd', '--rel-date', action='store', dest='rel_date',
                    help='Please give as "year/month/day" or "year-month-day". Used in: poll, git PR')

parser.add_argument('-pr', '--pull-request', action='store', dest='pr_slug', help='Please give as "owner/repo/num"')
parser.add_argument('-pb', '--pull-binary', action='store_true', dest='pr_bin')

parser.add_argument('-sk', '--skip', action='store_true')
parser.add_argument('-co', '--console-only', action='store_true')

parser.add_argument('-rs', '--random-seed', action='store')
parser.add_argument('-rr', '--random-rounds', action='store', type=int, default=1)
parser.add_argument('-ri', '--random-index', action='store_true')
parser.add_argument('-is', '--index-size', action='store', type=int)

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
        logger.info(f"{id_} removed from db")
    conn.close()

if any((args.slug, args.id_, args.url)):
    if args.url:
        args.slug = args.url.split('/')[-1]

    if args.slug:
        mkt = Market.from_slug(args.slug)
    else:
        mkt = Market.from_id(args.id)

    if args.rel_date:
        sections = args.rel_date.split('/')
        if len(sections) == 1:
            sections = args.rel_date.split('-')
        try:
            date: Optional[Tuple[int, int, int]] = tuple(int(x) for x in sections)  # type: ignore[assignment]
        except ValueError:
            raise
    else:
        date = None

    if args.random_index:
        mkt.resolve_to_rules.append(
            ResolveRandomIndex(args.random_seed, size=args.index_size, rounds=args.random_rounds)
        )

    if args.round:
        mkt.resolve_to_rules.append(RoundValueRule())
    if args.current:
        mkt.resolve_to_rules.append(CurrentValueRule())

    if args.pr_slug:
        pr_ = list(args.pr_slug.split('/'))
        pr_[-1] = int(pr_[-1])
        pr = cast(Tuple[str, str, int], tuple(pr_))
        mkt.do_resolve_rules.append(ResolveWithPR(*pr))
        if date:
            mkt.resolve_to_rules.append(ResolveToPRDelta(*pr, datetime(*date)))
        elif args.pr_bin:
            mkt.resolve_to_rules.append(ResolveToPR(*pr))
        else:
            raise ValueError("No resolve rule provided")

    if not mkt.do_resolve_rules:
        if not date:
            raise ValueError("No resolve date provided")
        mkt.do_resolve_rules.append(ResolveAtTime(datetime(*date)))

    conn = register_db()

    idx = max(((0, ), *conn.execute("SELECT id FROM markets;")))[0] + 1
    conn.execute("INSERT INTO markets values (?, ?, ?, ?);", (idx, mkt, 1, None))
    conn.commit()

    print(msg := f"Successfully added as ID {idx}!")
    logger.info(msg)
    conn.close()

if not args.skip:
    main(args.refresh, args.console_only)
