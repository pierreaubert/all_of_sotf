HOST_PYTHON ?= python3
VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
BUILDBOT := $(VENV)/bin/buildbot
WORKER := $(VENV)/bin/buildbot-worker

.PHONY: install master worker start stop check logs-master logs-worker restart rebuild-linux sync-config

install:
	@if [ ! -f "$(PYTHON)" ]; then $(HOST_PYTHON) -m venv $(VENV); fi
	$(PIP) install -r requirements.txt

sync-config:
	@mkdir -p master
	cp master.cfg master/master.cfg

master: sync-config
	$(BUILDBOT) create-master --force master
	$(MAKE) sync-config

worker:
	$(WORKER) create-worker --force worker-macos localhost macos-local macos-password

start: sync-config
	$(BUILDBOT) start master
	@echo "Waiting for master to be ready..."
	@ready=0; for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -sf http://localhost:8010 >/dev/null 2>&1; then echo "Master ready."; ready=1; break; fi; \
		sleep 1; \
	done; \
	if [ "$$ready" -ne 1 ]; then echo "Master HTTP port did not become ready in time." >&2; exit 1; fi
	@echo "Waiting for PB port to be ready..."
	@pb_ready=0; for i in 1 2 3 4 5 6 7 8 9 10; do \
		if nc -z localhost 9989 >/dev/null 2>&1; then echo "PB port ready."; pb_ready=1; break; fi; \
		sleep 1; \
	done; \
	if [ "$$pb_ready" -ne 1 ]; then echo "Master PB port did not become ready in time." >&2; exit 1; fi
	$(WORKER) start worker-macos

stop:
	$(WORKER) stop worker-macos || true
	$(BUILDBOT) stop master || true

check: sync-config
	$(BUILDBOT) checkconfig master/master.cfg

logs-master:
	tail -f master/twistd.log

logs-worker:
	tail -f worker-macos/twistd.log

restart: stop start

rebuild-linux:
	docker build --no-cache -t sotf/buildbot-linux-worker:v4.1.0 docker/linux-worker
