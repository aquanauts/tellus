SHELL := $(shell which bash) -o pipefail
MINICONDA := $(HOME)/miniconda3
CONDA := $(shell which conda || echo $(MINICONDA)/bin/conda)
VENV := $(PWD)/.venv
PROJECT_NAME=$(shell basename $(PWD))
DEPS := $(VENV)/.deps
DOCKER := $(shell which docker || echo ".docker_is_missing")
DOCKER_IMAGE = github.com/aquanauts/$(PROJECT_NAME)
PYTHON := $(VENV)/bin/python
PYTHON_CMD := PYTHONPATH=$(shell pwd) $(PYTHON)
PYLINT_CMD := $(PYTHON_CMD) -m pylint $(PROJECT_NAME) test
COVERAGE_CMD := $(VENV)/bin/coverage
COVERAGE_REPORTS := $(PWD)/web/public/tests/coverage
GIT_VERSION := $(shell git rev-list --count HEAD)
REVISION := $(GIT_VERSION)
TELLUS_VERSION := $(REVISION)
TELLUS_PERSISTENCE_DIR := '/tmp/tellus'
TELLUS_CMD := $(PYTHON_CMD) tellus --persistence-root=$(TELLUS_PERSISTENCE_DIR)

ifndef VERBOSE
.SILENT:
endif

.phony: help
help:
	grep -E '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

$(CONDA):
	echo "Installing Miniconda3 to $(MINICONDA)"
	wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
	bash /tmp/miniconda.sh -u -b -p "$(HOME)/miniconda3"
	rm /tmp/miniconda.sh
	$(CONDA) update -y conda

$(PYTHON): | $(CONDA)
	$(CONDA) env create -p $(VENV)

$(DEPS): environment.yml $(PYTHON)
	$(CONDA) env update -p $(VENV) -f environment.yml
	cp environment.yml $(DEPS)

clean:
	find . -name __pycache__ | xargs rm -rf
	rm -rf $(VENV)

.phony: test
test: $(DEPS) todo tasks ## Run linting, todos, unit, and integration tests
	#$(PYLINT_CMD)
	# Ignores smoketests, see below
	$(PYTHON_CMD) -m pytest --ignore test/smoketests

.phony: coverage
coverage: $(DEPS) todo tasks ## Run tests with coverage.py
	$(COVERAGE_CMD) run -m pytest --ignore test/smoketests; $(COVERAGE_CMD) report

.phony: cov-html
cov-html: $(DEPS) todo tasks ## Run tests with coverage.py and dump the html report into Tellus (yes, cheating)
	$(COVERAGE_CMD) run -m pytest --ignore test/smoketests; $(COVERAGE_CMD) html --directory=$(COVERAGE_REPORTS)

smoketest: $(DEPS) ## Run the smoketests (which have environmental dependencies)
	$(PYTHON_CMD) -m pytest test/smoketests

watch: $(DEPS) ## Run unit tests and lint continuously
	$(PYTHON_CMD) -m pytest_watch --runner $(VENV)/bin/pytest -n --onpass '$(PYLINT_CMD)' --ignore $(VENV) --ignore test/smoketests

run: $(DEPS)  ## run a local server - will try to persist in $(TELLUS_PERSISTENCE_DIR)
	$(TELLUS_CMD)

rundebug: $(DEPS)  ## run a local server in debug mode - very chatty
	$(TELLUS_CMD) --debug

repl: $(DEPS) ## Runs a REPL
	$(VENV)/bin/ipython

todo: ## Find technical debt
	-(find tellus test web/public -name '*.py' -o -name '*.js' | grep -Ev '(web/public/tests/lib/jasmine|web/public/vendor/moment)' | xargs grep -i --color TODO)

tasks: ## Find tasks (comments for intended future work)
	-(find tellus test web/public/js -name '*.py' -o -name '*.js' | xargs grep -i --color 'tellus-task')

.phony: git-version
git-version: ## Print the current git revision of Tellus
	echo $(GIT_VERSION)

.phony: version
version: ## Print the current full version of Tellus
	echo "Overall version:  $(TELLUS_VERSION)"
	echo "version contains:"
	cat tellus/version.py

update-version: ## update the version in version.py - run in various places in the Makefile to ensure up to date
	echo "__version__ = '$(TELLUS_VERSION)'" > tellus/version.py
	echo "version.py:"
	cat tellus/version.py

docker: $(DOCKER) ## build our docker image
	$(DOCKER) build . -t $(DOCKER_IMAGE):latest

docker-run: $(DEPS) $(DOCKER) docker ## run locally in Docker
	docker run -it -p 8080:8080/tcp $(DOCKER_IMAGE)

release: update-version docker ## Push a release to artifactory
	docker push $(DOCKER_IMAGE):latest

shell: docker fastshell ## Open a new shell inside Docker container for development

fastshell:  ## Open a new shell WITHOUT building docker - here be dragons
	docker run -v $(CURDIR):/src/$(PROJECT_NAME) -w /src/$(PROJECT_NAME) --entrypoint /bin/bash -it $(DOCKER_IMAGE)

runshell:  ## Open a new shell WITHOUT building docker (see fastshell), grabbing port 8080 for running locally
	docker run -v $(CURDIR):/src/$(PROJECT_NAME) -w /src/$(PROJECT_NAME) -p 8080:8080/tcp --entrypoint /bin/bash -it $(DOCKER_IMAGE)

blacken:  ## blacken code
	black ./
