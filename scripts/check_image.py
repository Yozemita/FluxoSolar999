"""Exercise a Docker image with an isolated local database and temporary owner."""
import argparse
import os
import secrets
import subprocess
import time
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--legacy-start", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)
    env.update(ADMIN_PASSWORD=secrets.token_urlsafe(32), ADMIN_USERNAME="image-check", COOKIE_SECURE="false", PORT="18881")
    docker = ["docker", "--host=unix:///var/run/docker.sock"]
    name = "fluxosolar-image-check-" + uuid.uuid4().hex[:10]
    command = ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "18881"] if args.legacy_start else []
    try:
        subprocess.run(docker + ["run", "-d", "--name", name, "-p", "127.0.0.1::18881",
            "-e", "ADMIN_PASSWORD", "-e", "ADMIN_USERNAME", "-e", "COOKIE_SECURE", "-e", "PORT", args.image] + command,
            env=env, check=True, stdout=subprocess.DEVNULL)
        port = subprocess.check_output(docker + ["port", name, "18881/tcp"], env=env, text=True).strip().rsplit(":", 1)[1]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"X-FluxoSolar-CSRF": "1"}, timeout=2) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.2)
            else:
                raise RuntimeError("Image health never became ready; inspect its sanitized startup output.")
            assert client.get("/").status_code == 200
            assert client.get("/static/app.js").status_code == 200
            assert client.get("/api/products").status_code == 401
            assert client.post("/api/auth/login", json={"username": "image-check", "password": env["ADMIN_PASSWORD"]}).status_code == 200
            assert "insights" in client.get("/api/dashboard").json()
            assert "video_generation" not in client.get("/api/status").json()
            assert client.post("/api/media/uploads", json={"content_type": "video/mp4"}).status_code == 422
            assert client.post("/api/agents/Analytics/run", json={}).status_code == 201
            assert client.post("/api/auth/logout", json={}).status_code == 200
            assert client.get("/api/auth/me").status_code == 401
        print(f"PASS: {args.image}, {'legacy main:app' if args.legacy_start else 'default startup'}, health/assets/login/dashboard/agent/logout.")
    finally:
        subprocess.run(docker + ["rm", "-f", "-v", name], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
