.venv sync:
	uv sync --all-extras

check: sync
	uv run ruff format --diff
	uv run ruff check
	$(MAKE) check-type

check-autofix: sync
	uv run ruff format
	uv run ruff check --fix
	$(MAKE) check-type

check-type: sync
	uv run ty check

build: sync
	uv run python -m ai_dev_ctn.build

remove-image:
	docker rmi $(shell docker images --format '{{.Repository}}:{{.Tag}}' | grep '^ctn-stack/')

.PHONY: sync check check-autofix check-type build remove-image
