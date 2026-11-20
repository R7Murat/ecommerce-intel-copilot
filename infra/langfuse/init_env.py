"""Generate secrets for the local Langfuse stack. Prints variable names only, never values.

Writes infra/langfuse/.env (compose interpolation) and appends the project keys
to the repo .env so the app can export traces. Refuses to overwrite: the data
volumes keep the old passwords, so regenerating would lock the stack out.
"""
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent
STACK_ENV = HERE / ".env"
APP_ENV = HERE.parents[1] / ".env"
APP_KEYS = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def tok(n: int = 24) -> str:
    return secrets.token_urlsafe(n)


def main() -> None:
    if STACK_ENV.exists():
        raise SystemExit(f"{STACK_ENV} exists; delete it and the docker volumes to regenerate")
    pg, pk, sk = tok(), f"pk-lf-{secrets.token_hex(16)}", f"sk-lf-{secrets.token_hex(16)}"
    stack = {
        "POSTGRES_PASSWORD": pg,
        "DATABASE_URL": f"postgresql://postgres:{pg}@postgres:5432/postgres",
        "SALT": tok(),
        "ENCRYPTION_KEY": secrets.token_hex(32),
        "NEXTAUTH_SECRET": tok(32),
        "CLICKHOUSE_PASSWORD": tok(),
        "REDIS_AUTH": tok(),
        "MINIO_ROOT_PASSWORD": tok(),
        "LANGFUSE_INIT_ORG_ID": "copilot-org",
        "LANGFUSE_INIT_ORG_NAME": "copilot",
        "LANGFUSE_INIT_PROJECT_ID": "copilot-dev",
        "LANGFUSE_INIT_PROJECT_NAME": "copilot-dev",
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": pk,
        "LANGFUSE_INIT_PROJECT_SECRET_KEY": sk,
        "LANGFUSE_INIT_USER_EMAIL": "admin@example.com",
        "LANGFUSE_INIT_USER_NAME": "admin",
        "LANGFUSE_INIT_USER_PASSWORD": tok(),
    }
    # minio password is reused by every S3 client in the compose file
    for k in ("EVENT_UPLOAD", "MEDIA_UPLOAD", "BATCH_EXPORT"):
        stack[f"LANGFUSE_S3_{k}_SECRET_ACCESS_KEY"] = stack["MINIO_ROOT_PASSWORD"]
    STACK_ENV.write_text("".join(f"{k}={v}\n" for k, v in stack.items()), encoding="utf-8")

    existing = APP_ENV.read_text(encoding="utf-8") if APP_ENV.exists() else ""
    present = {line.split("=", 1)[0].strip() for line in existing.splitlines() if "=" in line}
    if present & set(APP_KEYS):
        print(f"{APP_ENV.name}: Langfuse keys already present, left unchanged")
    else:
        app = {"LANGFUSE_HOST": "http://localhost:3000", "LANGFUSE_PUBLIC_KEY": pk,
               "LANGFUSE_SECRET_KEY": sk}
        sep = "" if existing.endswith("\n") or not existing else "\n"
        with APP_ENV.open("a", encoding="utf-8") as f:
            f.write(sep + "".join(f"{k}={v}\n" for k, v in app.items()))
        print(f"{APP_ENV.name}: appended {', '.join(APP_KEYS)}")
    print(f"{STACK_ENV.name}: wrote {len(stack)} variables")


if __name__ == "__main__":
    main()
