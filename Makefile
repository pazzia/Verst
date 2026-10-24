.PHONY: test-planner lint-planner typecheck-planner golden-update coverage-planner check

test-planner:
	cd backend/planner && python3 -m unittest discover -v

lint-planner:
	ruff check backend/planner

typecheck-planner:
	mypy --strict backend/planner/verst_planner

golden-update:
	cd backend/planner && VERST_GOLDEN_UPDATE=1 python3 -m unittest tests.golden.test_golden

coverage-planner:
	cd backend/planner && python3 tools/stdlib_coverage.py --fail-under 95

check: lint-planner typecheck-planner test-planner
