import sys
from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project src directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import application configuration and models
from job_tracker.config.settings import settings
from job_tracker.database.base import Base
from job_tracker.models import Application, StatusHistory  # Ensure models are loaded for autogenerate

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from Pydantic Settings
config.set_main_option("sqlalchemy.url", settings.db.url)

# Ensure directory for SQLite DB exists before connecting
if settings.db.url.startswith("sqlite:///"):
    db_path_str = settings.db.url.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    # If using absolute path in Windows (e.g., C:/...) we need to resolve it
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

# Set target metadata for autogenerate detection
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
