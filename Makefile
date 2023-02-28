BRANCH_NAME = $(shell git rev-parse --abbrev-ref HEAD)

APP_NAME := envars
PYTHON_VERSION := 3.10

.DEFAULT_GOAL := help
.PHONY: help python python-deps-upgrade test clean

confirm:
	@( read -p "$(RED)Are you sure? [y/N]$(RESET): " sure && case "$$sure" in [yY]) true;; *) false;; esac )

python: ## setup python env and pre-commit
	pyenv install -s $(PYTHON_VERSION)
	pyenv virtualenv $(PYTHON_VERSION) $(APP_NAME)_$(BRANCH_NAME)
	echo $(APP_NAME)_$(BRANCH_NAME) > .python-version
	eval "$$(pyenv init -)" && \
		pyenv activate $(APP_NAME)_$(BRANCH_NAME) && \
		pip install --upgrade pip && \
		pip install wheel && \
		pip install -r requirements.txt
	pre-commit install

python-deps-upgrade: ## Run pip-complie upgrade
	pip-compile --resolver=backtracking -U

test: ## Run tests
	pytest -v

clean: confirm ## Clean python
	rm .python-version
	eval "$$(pyenv init -)" && pyenv virtualenv-delete -f $(APP_NAME)_$(BRANCH_NAME)

help: ## This message
	@grep -E '(^[a-zA-Z_-]+:.*?## .*$$)|(^##)' $(MAKEFILE_LIST) \
	| awk 'BEGIN{FS=":.*?## "}; {printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' \
	| sed -e 's/\[32m##/[33m/'
