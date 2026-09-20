import subprocess
import sys
import os
import time
import signal
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
try:
    from app.config.logging_config import setup_logging
    setup_logging()
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
COMPOSE_FILE = os.path.join(PROJECT_DIR, "docker-compose.yml")

processes = []


def _check_port(host, port, timeout=2):
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _docker_available():
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def start_infra():
    logger.info("[1/3] 检查基础设施（PostgreSQL + Redis）...")
    pg_ok = _check_port("localhost", 5432)
    redis_ok = _check_port("localhost", 6379)

    if pg_ok and redis_ok:
        logger.info("PostgreSQL 和 Redis 均已运行")
        return True

    if not _docker_available():
        logger.error("Docker 未运行！请先启动 Docker Desktop")
        logger.error("  或手动启动 PostgreSQL(5432) 和 Redis(6379)")
        return False

    logger.info("通过 docker compose 启动 PostgreSQL + Redis...")
    try:
        r = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "postgres", "redis"],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            logger.error(f"docker compose 启动失败:\n{r.stderr.decode(errors='replace')}")
            return False
    except FileNotFoundError:
        logger.error("docker compose 命令不存在，请安装 Docker Desktop")
        return False

    logger.info("等待 PostgreSQL 和 Redis 就绪...")
    for i in range(30):
        if _check_port("localhost", 5432) and _check_port("localhost", 6379):
            logger.info("PostgreSQL 和 Redis 已就绪")
            return True
        time.sleep(1)
    logger.error("等待超时，PostgreSQL/Redis 未就绪")
    return False


def start_api():
    logger.info("[2/3] 启动后端 API 服务...")
    env = os.environ.copy()
    env["PYTHONPATH"] = BACKEND_DIR
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=BACKEND_DIR,
        env=env,
    )
    processes.append(proc)
    return proc


def start_frontend():
    logger.info("[3/3] 启动前端服务...")
    frontend_dir = os.path.join(PROJECT_DIR, "frontend")
    if not os.path.exists(os.path.join(frontend_dir, "package.json")):
        logger.info("前端项目未初始化，跳过（可手动 cd frontend && npm install && npm run dev）")
        return None
    if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
        logger.info("安装前端依赖...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True, timeout=120)
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--turbopack"],
        cwd=frontend_dir,
        shell=True,
    )
    processes.append(proc)
    return proc


def signal_handler(sig, frame):
    logger.info("正在停止所有服务...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    logger.info("所有服务已停止")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("  AI小说生成系统 - 一键启动")
    logger.info("=" * 60)

    if not start_infra():
        logger.error("基础设施启动失败，退出")
        sys.exit(1)

    start_api()
    time.sleep(3)
    start_frontend()

    logger.info("")
    logger.info("=" * 60)
    logger.info("  所有服务已启动！")
    logger.info("  API:     http://localhost:8000")
    logger.info("  API文档: http://localhost:8000/docs")
    logger.info("  前端:    http://localhost:3000")
    logger.info("  按 Ctrl+C 停止所有服务")
    logger.info("=" * 60)

    try:
        while True:
            time.sleep(1)
            for proc in processes:
                if proc.poll() is not None:
                    logger.warning(f"进程 PID={proc.pid} 已退出，返回码: {proc.returncode}")
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
