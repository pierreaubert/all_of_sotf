HOST_PYTHON := /usr/bin/python3
VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
BUILDBOT := $(VENV)/bin/buildbot
WORKER := $(VENV)/bin/buildbot-worker

.PHONY: install master worker start stop check

install:
	$(HOST_PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt

master:
	$(BUILDBOT) create-master master

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
