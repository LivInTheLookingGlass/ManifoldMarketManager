SHELL := /bin/bash

# If specified, open pdb on uncaught exception
DEBUG?=
# If specified, use a different python command
PY?=python3
# Unless specified otherwise, install python modules as user
USER_FLAG?=--user
# If specified, use a different command for pip
PIP?=$(PY) -m pip
# Unless specified otherwise, perform code coverage analysis
COV?=true
# Unless specified otherwise, run a linter. Also accepts only to run only linting and type-checking, disable code coverage
LINT?=true
# Unless specified otherwise, perform type-checking
MYPY?=true
# If specified, perform benchmarking (WARNING: silently disables code coverage)
BENCHMARK?=false

pytest_args?= -vl

ifeq ($(BENCHMARK),true)
pytest_args += --benchmark-min-time=0.05 --benchmark-sort=fullname --benchmark-group-by=fullfunc --benchmark-verbose
COV=false
endif

ifneq ($(LINT),false)
pytest_args += --flake8 --isort --pydocstyle
endif

ifeq ($(LINT),only)
pytest_args += --ignore=./src/test --ignore=./src/PyManifold/tests
COV=false
endif

ifneq ($(MYPY),false)
pytest_args += --mypy --mypy-ignore-missing-imports
endif

ifneq ($(COV),false)
pytest_args += --cov=src --cov-branch --cov-report=term
endif

ifneq ($(https_proxy), )
PROXY_ARG=--proxy=$(https_proxy)
else
ifneq ($(http_proxy), )
PROXY_ARG=--proxy=$(http_proxy)
else
PROXY_ARG=
endif
endif

.PHONY: test
# Run tests sequentially
test: dependencies _test

.PHONY: test_all_%
# Run tests in parallel in all supported python versions
test_all_%:
	@$(MAKE) test LINT=only $(MFLAGS)
	@if command -v python3.8 &> /dev/null; then $(MAKE) test_$* PY=python3.8 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.8 is not installed - skipping"; fi
	@if command -v python3.9 &> /dev/null; then $(MAKE) test_$* PY=python3.9 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.9 is not installed - skipping"; fi
	@if command -v python3.10 &> /dev/null; then $(MAKE) test_$* PY=python3.10 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.10 is not installed - skipping"; fi
	@if command -v python3.11 &> /dev/null; then $(MAKE) test_$* PY=python3.11 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.11 is not installed - skipping"; fi

.PHONY: test_all
# Run tests sequentially in all supported python versions
test_all:
	@$(MAKE) test LINT=only $(MFLAGS)
	@if command -v python3.8 &> /dev/null; then $(MAKE) test PY=python3.8 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.8 is not installed - skipping"; fi
	@if command -v python3.9 &> /dev/null; then $(MAKE) test PY=python3.9 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.9 is not installed - skipping"; fi
	@if command -v python3.10 &> /dev/null; then $(MAKE) test PY=python3.10 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.10 is not installed - skipping"; fi
	@if command -v python3.11 &> /dev/null; then $(MAKE) test PY=python3.11 LINT=false MYPY=false $(MFLAGS); else echo "Python 3.11 is not installed - skipping"; fi

.PHONY: test_%
# Run tests with a given number of parallel runners
test_%:
	@$(MAKE) test pytest_args="$(pytest_args) -n$*" $(MFLAGS)

.PHONY: _test
_test:
	@source env_personal.sh && ManifoldMarketManager_NO_CACHE=1 PYTHONPATH=${PYTHONPATH}:./src/PyManifold $(PY) -m pytest src $(pytest_args) -k 'not mypy-status' --ignore=./src/test/manifold

.PHONY: dependencies
ifeq ($(MYPY),true)
# Load dependencies from pypi
dependencies:
	@$(PIP) install -r requirements.txt $(USER_FLAG) $(PROXY_ARG)
else
dependencies:
	@cat requirements.txt | grep -v "mypy" > .requirements.txt
	@$(PIP) install -r .requirements.txt $(USER_FLAG) $(PROXY_ARG)
endif

.PHONY: run_%
# Run a specific account
run_%: LICENSE dependencies
	@source env_$*.sh && $(PY) -O -m src

.PHONY: run
# Run all known accounts
run:
	@$(MAKE) run_bot run_personal $(MFLAGS)

.PHONY: daemon
# Run all known accounts in a loop
daemon:
	@./daemon.sh

.PHONY: quiet_daemon
# Run all known accounts in a loop (quietly)
quiet_daemon:
	@while [ 1 ]; do\
		$(MAKE) run $(MFLAGS);\
		sleep 1800;\
	done;

.PHONY: build
# Build a package
build: dependencies clean LICENSE
	@$(PIP) install build
	@$(PY) -m build

.PHONY: clean
# Clean up after a build
clean:
	@rm -rf build dist logs .benchmarks .pytest_cache src/*.egg-info test-reporter-latest-linux-amd64 .coverage .requirements.txt coverage.xml
	@mkdir logs

.PHONY: publish
# Publish new version to pypi
publish: build test_all upload_coverage
	@$(PY) -m twine upload -u gappleto97 -s --sign-with gpg2 dist/*
	@$(MAKE) clean $(MFLAGS)

.PHONY: graph
# Build a dependency graph of this package
graph: dependencies
	@$(PIP) install pydeps $(USER_FLAG)
	@PYTHONPATH=${PYTHONPATH}:./src/PyManifold $(PY) -m pydeps --noshow --cluster -x src.test pytest --max-bacon 100 -T png src

.PHONY: import_%
# Create one or more markets from example.json and add them to the specified account
import_%: LICENSE dependencies
	@source env_$*.sh && $(PY) example_json.py

.PHONY: upload_coverage
# Upload coverage reports to codeclimate
upload_coverage: .coverage
	@coverage xml
	@python -m coverage xml
	@if [ ! -f ./test-reporter-latest-linux-amd64 ]; then wget https://codeclimate.com/downloads/test-reporter/test-reporter-latest-linux-amd64; chmod +x ./test-reporter-latest-linux-amd64; fi
	@./test-reporter-latest-linux-amd64 after-build -t coverage.py -r eb0fb76d1b07b8f58d16c2ccd2ef6f9d2483faa25650522e6313f6564a6d0351

.PHONY: help
# Show this help.
help:
	@echo Variables:
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_]+\??=/{print substr($$1,1,index($$1,"?")),c}1{c=0}' $(MAKEFILE_LIST) | column -s? -t
	@echo
	@echo Commands:
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_%%-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' $(MAKEFILE_LIST) | column -s: -t
