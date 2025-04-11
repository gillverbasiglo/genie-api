# Database Migrations

This directory contains Alembic database migrations for the application. The migrations are used to manage database schema changes in a controlled and versioned way.

## Setup

1. Make sure you have the required environment variables set in your `.env` file or in your environment:
   - `DB_USERNAME`
   - `DB_PASSWORD`
   - `DB_HOST`
   - `DB_PORT`
   - `DB_NAME`
   - `ENVIRONMENT` (development or production)

2. In production, the database credentials will be automatically fetched from AWS Secrets Manager.

## Creating a New Migration

To create a new migration after making changes to your SQLAlchemy models:

```bash
alembic revision --autogenerate -m "Description of changes"
```

## Running Migrations

To upgrade to the latest version:

```bash
alembic upgrade head
```

To upgrade to a specific version:

```bash
alembic upgrade <revision_id>
```

To downgrade to a previous version:

```bash
alembic downgrade <revision_id>
```

## Checking Current Migration Status

To see the current migration status:

```bash
alembic current
```

To see all available migrations:

```bash
alembic history
```

## Important Notes

- Always review the generated migration files before running them
- Make sure to test migrations in a development environment before applying them to production
- In production, the migrations will use credentials from AWS Secrets Manager
- Never commit sensitive information in migration files 