dev:
	../venv/bin/uvicorn main:app --reload \
		--reload-dir agents \
		--reload-dir api \
		--reload-dir crews \
		--reload-dir db \
		--reload-dir scripts \
		--reload-include main.py \
		--reload-include config.py

db-upgrade:
	../venv/bin/alembic upgrade head

db-downgrade:
	../venv/bin/alembic downgrade -1

db-revision:
	../venv/bin/alembic revision --autogenerate -m "$(m)"

.PHONY: dev db-upgrade db-downgrade db-revision
