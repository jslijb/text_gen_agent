"""`app/config/secret_store.py` 测试：只 upsert 目标变量，其它行一律保留。"""
import os

import pytest

from app.config.secret_store import env_file_path, has_secret, set_secret


def test_appends_new_secret_preserving_everything_else(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# 注释\nAGNES_KEY=abc\n\nREDIS_URL=redis://x\n", encoding="utf-8")

    set_secret("SIEVE_API_KEY", "dc_sk_new", env)

    content = env.read_text(encoding="utf-8")
    assert "AGNES_KEY=abc" in content
    assert "# 注释" in content
    assert "REDIS_URL=redis://x" in content
    assert "SIEVE_API_KEY=dc_sk_new" in content
    assert content.endswith("\n")


def test_replaces_in_place_without_duplicating(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SIEVE_API_KEY=old\nAGNES_KEY=abc\n", encoding="utf-8")

    set_secret("SIEVE_API_KEY", "dc_sk_new", env)

    content = env.read_text(encoding="utf-8")
    assert content.count("SIEVE_API_KEY=") == 1
    assert "SIEVE_API_KEY=dc_sk_new" in content
    assert "AGNES_KEY=abc" in content


def test_export_prefix_is_recognised(tmp_path):
    env = tmp_path / ".env"
    env.write_text("export SIEVE_API_KEY=old\n", encoding="utf-8")

    set_secret("SIEVE_API_KEY", "new", env)

    content = env.read_text(encoding="utf-8")
    assert content.count("SIEVE_API_KEY") == 1
    assert "new" in content and "old" not in content


def test_rejects_multiline_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        set_secret("SIEVE_API_KEY", "line1\nline2", env)


def test_has_secret_checks_env_and_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    assert has_secret("SIEVE_API_KEY", env) is False
    env.write_text("SIEVE_API_KEY=\n", encoding="utf-8")
    assert has_secret("SIEVE_API_KEY", env) is False  # 空值不算已配置
    env.write_text("SIEVE_API_KEY=dc_sk_x\n", encoding="utf-8")
    assert has_secret("SIEVE_API_KEY", env) is True

    monkeypatch.setenv("SIEVE_API_KEY", "from-env")
    assert has_secret("SIEVE_API_KEY", tmp_path / "missing") is True


def test_no_temp_files_left_behind(tmp_path):
    env = tmp_path / ".env"
    set_secret("SIEVE_API_KEY", "x", env)
    assert [p.name for p in tmp_path.iterdir()] == [env.name]


def test_default_path_is_backend_env():
    path = env_file_path()
    assert path.name == ".env"
    assert path.parent.name == "backend"
    # 绝不把密钥写到别处
    assert os.path.isabs(str(path))
