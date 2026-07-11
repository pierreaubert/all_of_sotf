HOST_PYTHON ?= /usr/bin/python3
VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
BUILDBOT := $(VENV)/bin/buildbot
WORKER := $(VENV)/bin/buildbot-worker

.PHONY: install master worker start stop check logs-master logs-worker restart rebuild-linux

install:
	$(HOST_PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt

master:
	$(BUILDBOT) create-master --force master

worker:
	$(WORKER) create-worker worker-macos localhost macos-local macos-password

start:
	$(BUILDBOT) start master
	$(WORKER) start worker-macos

stop:
	$(WORKER) stop worker-macos
	$(BUILDBOT) stop master

check:
	$(BUILDBOT) checkconfig master/master.cfg

logs-master:
	tail -f master/twistd.log

logs-worker:
	tail -f worker-macos/twistd.log

restart: stop start

rebuild-linux:
	docker build --no-cache -t sotf/buildbot-linux-worker:latest docker/linux-worker
