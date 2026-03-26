PROJECT_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: frontend-install frontend-lint frontend-build backend-compile backend-test-docker check

frontend-install:
	cd $(PROJECT_ROOT)frontend && npm install

frontend-lint:
	cd $(PROJECT_ROOT)frontend && npm run lint

frontend-build:
	cd $(PROJECT_ROOT)frontend && npm run build

backend-compile:
	cd $(PROJECT_ROOT)backend && python3 -m compileall app

backend-test-docker:
	docker run --rm \
		-v $(PROJECT_ROOT):/workspace \
		-w /workspace/backend \
		python:3.12-slim \
		bash -lc "python -m pip install -q -r requirements.txt && python -m pytest -q tests"

check: frontend-lint frontend-build backend-compile backend-test-docker
