.PHONY: help seed seed-sqlite seed-clean test run up down

help:
	@echo "AICTE FinTrust Backend Commands:"
	@echo "  make up           - Start Docker containers (PostgreSQL, MinIO, Redis)"
	@echo "  make down         - Stop Docker containers"
	@echo "  make seed         - Seed PostgreSQL database with sample institutions & FDRs"
	@echo "  make seed-sqlite  - Seed local SQLite database for offline development"
	@echo "  make seed-clean   - Clean and re-seed the database"
	@echo "  make test         - Run full pytest test suite"
	@echo "  make run          - Run FastAPI backend development server"

up:
	docker compose up -d

down:
	docker compose down

seed:
	cd backend && python -m scripts.seed_database

seed-sqlite:
	cd backend && python -m scripts.seed_database --sqlite

seed-clean:
	cd backend && python -m scripts.seed_database --clean

test:
	pytest backend/tests -v

run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
