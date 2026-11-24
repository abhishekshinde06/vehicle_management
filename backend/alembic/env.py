"""
Alembic Migration Environment
------------------------------
Configures the runtime environment for both 'offline' (SQL script generation)
and 'online' (live database connection) migration modes.

Key design decisions:
- DATABASE_URL is pulled from app.core.config.settings — the single source of
  truth — so .env changes automatically apply to migrations.
- All models are imported via app.models so Alembic's autogenerate can detect
  schema changes by comparing the SQLAlchemy metadata with the live database.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# 1. Load application settings & expose metadata to Alembic
# ---------------------------------------------------------------------------
# Import settings BEFORE anything else touches the engine
from app.core.config import settings  # noqa: E402

# Import ALL models so their Table objects are registered on Base.metadata.
# Without this, autogenerate won't see any tables.
from app.core.database import Base  # noqa: E402
import app.models  # noqa: F401, E402  — registers User, Vehicle, PetrolPump, FuelEntry, EntryPhoto, AuditLog

# ---------------------------------------------------------------------------
# 2. Standard Alembic boilerplate
# ---------------------------------------------------------------------------
config = context.config

# Inject the DATABASE_URL from settings so it overrides alembic.ini's placeholder
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# 3. Offline migration mode (generates a .sql script without connecting)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (useful for DBA review)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # detect column-type changes
        compare_server_default=True,  # detect default-value changes
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# 4. Online migration mode (connects and applies migrations directly)
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations against a live PostgreSQL database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # one connection per migration run, then dispose
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
