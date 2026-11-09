.PHONY: help
help:
	@grep -F -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | perl -pe 's/^(\w+):(.+?)##/"  $$1:" . " " x (20 - length($$1))/e' | perl -pe 's/^## ?//'

## Makefile to perform all tasks for development.
##
## Install commands:
##

.PHONY: install
install:                               ## Perform all install steps
	if ! command -v uv >/dev/null 2>&1; \
		then echo "uv not found, installing..." \
		&& curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	uv sync
	uv run pre-commit install

##
## Package management:
##

.PHONY: upgrade
upgrade:                               ## Tool to upgrade the backend dependencies.
	uv sync --upgrade

##
## Testing:
##

.PHONY: test
test:                                  ## Run the test-suite.
	uv run pytest --reuse-db --nomigrations -vs .

.PHONY: test
retest:                                ## Run the failed tests again.
	uv run pytest --reuse-db --nomigrations -vvs --lf .

.PHONY: coverage
coverage:
	uv run pytest --reuse-db --nomigrations --cov --cov-report=term-missing

##
## Development tools:
##

format:                                ## Fix code-formatting of all files.
	uv run ruff check --fix-only .
#	uv run pre-commit run -a

lint:                                  ## Report linting errors for all files
	uv run ruff check .

##
## Fixtures:
##

migrate:
	uv run src/manage.py migrate

load_fixtures:  migrate                  ## Load initial data into database by django fixtures
	uv run src/manage.py loaddata kennisgevingen.json

##
