import argparse
import json
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from medguide.infrastructure.errors import PipelineError
from medguide.sources import build_service

ERRORS = {
    "UNKNOWN_SOURCE": "Fonte desconhecida. Consulte: python -m medguide sources list",
    "SOURCE_NOT_REGISTERED": (
        "Fonte disponível, mas ainda não cadastrada. Execute sources bootstrap."
    ),
    "SOURCE_DISABLED": "Fonte desabilitada. Use sources enable CODIGO antes de executar.",
    "UNKNOWN_CONNECTOR": "O conector desta fonte não está registrado na aplicação.",
}


def date_label(value: datetime | None) -> str:
    if value is None:
        return "—"
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return aware.astimezone(UTC).isoformat()


def render(action: str, result: Any) -> None:
    if action == "bootstrap":
        print("Fontes cadastradas: " + (", ".join(result) if result else "todas já cadastradas"))
    elif action == "list":
        for source in result:
            state = (
                ("habilitada" if source["enabled"] else "desabilitada")
                if source["registered"]
                else "não cadastrada"
            )
            print(
                f"{source['code']} | {source['name']} | {state} | próxima: "
                f"{date_label(source['next_due_at'])}"
            )
    elif action in ("enable", "disable"):
        print(f"Fonte {result['code']}: {'habilitada' if result['enabled'] else 'desabilitada'}.")
    elif action == "run":
        print(f"Fonte: {result['code']}")
        print(
            f"Descoberta {'já em andamento' if result['reused'] else 'criada'}: {result['run_id']}"
        )
        print(
            "Publicação: enviada para a fila."
            if result["published"]
            else "Publicação pendente. Pedido salvo; o reconciliador tentará enviar novamente."
        )
        print(f"Acompanhe: python -m medguide sources status {result['code']}")
    else:
        print(f"Fonte: {result['name']} ({result['code']})")
        print(f"Agendamento: {'habilitado' if result['enabled'] else 'desabilitado'}")
        print(f"Próxima descoberta: {date_label(result['next_due_at'])}")
        run = result["latest_run"]
        if run:
            print(f"Última descoberta: {run['status']} ({run['id']})")
            print(
                f"Diretrizes encontradas: {run['found_count']} | "
                f"Jobs criados: {run['queued_count']}"
            )
            if run["error"]:
                print(f"Erro da descoberta: {run['error']}")
        else:
            print("Última descoberta: nenhuma execução.")
        print("Ingestão — totais históricos da fonte (incluem tentativas manuais anteriores):")
        labels = {
            "COMPLETED": "Concluídos",
            "PENDING": "Pendentes",
            "PROCESSING": "Em processamento",
            "FAILED": "Com falha",
            "NEEDS_REVIEW": "Para revisão",
        }
        for status, label in labels.items():
            print(f"  {label}: {result['jobs_by_status'][status]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m medguide", description="Operação local do MedGuide"
    )
    groups = parser.add_subparsers(dest="group", required=True)
    commands = groups.add_parser("sources", help="Gerenciar fontes pelo código").add_subparsers(
        dest="action", required=True
    )
    for action in ("list", "bootstrap", "run", "status", "enable", "disable"):
        command = commands.add_parser(action)
        if action not in ("list", "bootstrap"):
            command.add_argument("code", help="Código da fonte, por exemplo conitec_pcdt")
        command.add_argument("--json", action="store_true", help="Exibir resultado em JSON")
    args = parser.parse_args(argv)
    try:
        service = build_service()
        if args.action == "bootstrap":
            result: Any = service.bootstrap()
        elif args.action == "list":
            result = service.list()
        elif args.action == "run":
            result = service.run(args.code)
        elif args.action == "status":
            result = service.status(args.code)
        else:
            result = service.set_enabled(args.code, args.action == "enable")
    except PipelineError as exc:
        print(ERRORS.get(exc.code, exc.code), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(
            "Não foi possível acessar o banco. Verifique os serviços e as migrações com "
            "docker compose up --build -d.",
            file=sys.stderr,
        )
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=lambda value: date_label(value)))
    else:
        render(args.action, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
