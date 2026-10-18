"""Local startup: apply migrations, then insert missing approved sources."""

from alembic import command
from alembic.config import Config

from medguide.sources import build_service


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    created = build_service().bootstrap()
    print("Fontes cadastradas: " + (", ".join(created) if created else "todas já cadastradas"))


if __name__ == "__main__":
    main()
