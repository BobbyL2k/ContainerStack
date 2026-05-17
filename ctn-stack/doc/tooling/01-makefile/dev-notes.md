Incorporate this Makefile pattern

```Makefile
.venv sync:
	uv sync --all-extras

check: sync
	uv run ruff format --diff
	uv run ruff check
	$(MAKE) check-type
	$(MAKE) test

check-autofix: sync
	uv run ruff format
	uv run ruff check --fix
	$(MAKE) check-type
	$(MAKE) test

check-type: sync
	uv run ty check

test: sync
	uv run pytest

.PHONY: sync check check-autofix check-type test
```
