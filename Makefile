SHELL := /bin/bash

# If specified, open pdb on uncaught exception
DEBUG?=
# If specified, run a linter
LINT?=
# If specified, use a different python command
PY?=python3
# Unless specified otherwise, install python modules as user
USER_FLAG?=--user
# If specified, use a different command for pip
PIP?=$(PY) -m pip
# If specified, perform type-checking
MYPY?=true

ifneq ($(MYPY),true)
LINT=less
endif

ifeq ($(LINT),false)
pytest_args?= -vl --benchmark-min-time=0.05 --benchmark-sort=fullname --benchmark-group-by=fullfunc --benchmark-verbose
else
ifeq ($(LINT),true)
pytest_args?= -vl --mypy --mypy-ignore-missing-imports --flake8 --isort -k 'not test_problem and not test_is_prime and not test_groupwise'
else
ifeq ($(LINT),less)
pytest_args?= -vl --flake8 --isort --benchmark-min-time=0.05 --benchmark-sort=fullname --benchmark-group-by=fullfunc --benchmark-verbose
else
pytest_args?= -vl --mypy --mypy-ignore-missing-imports --flake8 --isort --benchmark-min-time=0.05 --benchmark-group-by=fullfunc --benchmark-sort=fullname --benchmark-verbose
endif
endif
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

.PHONY: test_%
# Run tests with a given number of parallel runners
test_%:
	@$(MAKE) test pytest_args="$(pytest_args) -n$*" $(MFLAGS)

.PHONY: _test
_test:
	@$(PY) -m pytest src $(pytest_args)

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
	@source env_$*.sh && $(PY) -m src

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
# (TODO) Build a package
build: dependencies clean LICENSE
	@$(PY) setup.py bdist_wheel --universal
	@$(PY) setup.py sdist

.PHONY: clean
# Clean up after a build
clean:
	@mkdir -p build dist
	@rm -r build dist

.PHONY: publish
# (TODO) Publish new version to pypi
publish: build
	@$(PY) -m twine upload -u gappleto97 -s --sign-with gpg2 dist/*

.PHONY: graph
# Build a dependency graph of this package
graph: dependencies
	@$(PIP) install pydeps
	@PYTHONPATH=${PYTHONPATH}:./src/PyManifold $(PY) -m pydeps --noshow --cluster --max-bacon 100 -T png src

.PHONY: import_%
# Create one or more markets from example.json and add them to the specified account
import_%: LICENSE dependencies
	@$(PY) example_json.py

.PHONY: help
# Show this help.
help:
	@echo Variables:
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_]+\??=/{print substr($$1,1,index($$1,"?")),c}1{c=0}' $(MAKEFILE_LIST) | column -s? -t
	@echo
	@echo Commands:
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_%%-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' $(MAKEFILE_LIST) | column -s: -t
