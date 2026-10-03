"""本项目的密钥落盘位置：`backend/.env`。

`.env` 是 docker-compose 里 backend / worker / beat 三个服务的 `env_file`，
也是本项目唯一的密钥载体（AGNES_KEY / DASHSCOPE_API_KEY1 都在这里），
`.gitignore` 明确排除（`*.env` + `!.env.example`）。

这个模块只做一件事：**按行 upsert 一个变量，保留其它所有行**。
不读取、不打印、不返回密钥值 —— 指纹信息（长度/前缀）由调用方自己算。
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


def env_file_path(path: str | Path | None = None) -> Path:
    """默认 backend/.env（src 布局：backend/app/config/secret_store.py → backend/）。"""
    if path is not None:
        return Path(path)
    return Path(__file__).resolve().parents[2] / ".env"


def set_secret(name: str, value: str, path: str | Path | None = None) -> Path:
    """把 `NAME=value` 写进 .env：已存在则原地替换，不存在则追加。

    原文件的注释、空行、其它变量全部保持原样（不整文件重写内容）。
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
        raise ValueError(f"非法的环境变量名: {name!r}")
    if value is None or "\n" in value or "\r" in value:
        raise ValueError("密钥值不能为空且不能包含换行")

    target = env_file_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()

    new_line = f"{name}={value}"
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=")
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        lines.append(new_line)

    content = "\n".join(lines).rstrip("\n") + "\n"
    # 原子写：临时文件 + os.replace，避免写到一半被中断把 .env 弄坏
    fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return target


def has_secret(name: str, path: str | Path | None = None) -> bool:
    """是否已存在非空的该变量（环境变量优先，其次 .env）。"""
    if os.getenv(name):
        return True
    target = env_file_path(path)
    if not target.exists():
        return False
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.+)$")
    for line in target.read_text(encoding="utf-8").splitlines():
        if pattern.match(line):
            return True
    return False
