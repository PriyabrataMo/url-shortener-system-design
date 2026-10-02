.PHONY: up down logs load load-public scale public reset

VUS ?= 10
DURATION ?= 30s

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f gateway backend analytics-worker postgres redis

load:
	docker compose up -d --scale backend=3 gateway
	docker compose --profile loadtest run --rm --no-deps -e VUS=$(VUS) -e DURATION=$(DURATION) k6

load-public:
	docker compose --profile public up -d --scale frontend=1 --scale backend=3
	docker compose --profile public-loadtest run --rm --no-deps -e VUS=$(VUS) -e DURATION=$(DURATION) k6-public

scale:
	docker compose up --build --scale frontend=1 --scale backend=3

public:
	docker compose --profile public up --build --scale frontend=1 --scale backend=3

reset:
	docker compose down -v
