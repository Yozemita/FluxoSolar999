"""Build in Codex with temporary CA trust, without changing the production recipe."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="fluxosolar:test")
    parser.add_argument("--backend", action="store_true", help="Build the standalone backend context used by existing Railway services.")
    parser.add_argument("--ca-bundle", type=Path, default=Path("/etc/ssl/certs/ca-certificates.crt"))
    args = parser.parse_args()
    if not args.ca_bundle.is_file():
        parser.error("Provide the Codex proxy/system CA bundle with --ca-bundle.")
    root = Path(__file__).resolve().parent.parent
    context = root / "backend" if args.backend else root
    recipe = (context / "Dockerfile").read_text()
    install = "RUN python -m pip install --no-cache-dir -r " + ("/app/backend/requirements.txt" if args.backend else "backend/requirements.txt")
    if recipe.count(install) != 1:
        raise SystemExit("Production install step changed; update this cloud helper before building.")
    cloud_install = install.replace("RUN ", "RUN --mount=type=secret,id=proxy_ca,required=true PIP_CERT=/run/secrets/proxy_ca ", 1)
    env = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)
    docker = ["docker", "--host=unix:///var/run/docker.sock"]
    subprocess.run(docker + ["info", "--format", "{{.ServerVersion}}"], env=env, check=True)
    with tempfile.TemporaryDirectory(prefix="fluxosolar-build-") as tmp:
        path = Path(tmp) / "Dockerfile"
        path.write_text("# syntax=docker/dockerfile:1\n" + recipe.replace("# syntax=docker/dockerfile:1\n", "").replace(install, cloud_install))
        subprocess.run(docker + ["build", "--file", str(path), "--secret", f"id=proxy_ca,src={args.ca_bundle.resolve()}",
                                "--tag", args.tag, str(context)], env=env, check=True)


if __name__ == "__main__":
    main()
