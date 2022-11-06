"""Runner script for ManifoldMarketManager.

Includes a variety of command line options which can be explored by invoking with the `--help` flag.

Note that the behavior of this runner script is not yet stable. Many changes are going to occur between its current
state and the desired production behavior. These changes include:

- [ ] Multiple Account Support
- [ ] Create markets using JSON
- [ ] Import markets using JSON
- [ ] Queue markets to be created in the future
- [ ] Run hooks on various Markets, ex: when they are
  - [ ] queued
  - [ ] created
  - [ ] resolved
  - [ ] cancelled
- [ ] Use an event loop (maybe asyncio) rather that a sleep loop
- [ ] Allow rules to store data in the db (and clean up after them)
"""

from __future__ import annotations

from logging import DEBUG, INFO, basicConfig, getLogger
from os import getenv

from .application import parse_args

args = parse_args()

if args.logging:
    # Enable logging
    basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=(INFO if not getenv("DEBUG") else DEBUG),
        filename=getenv("LogFile"),
    )
    logger = getLogger(__name__)

exit(args.func(**vars(args)))
