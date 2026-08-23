import os
import shutil
import subprocess
import sys

MAX_OUTPUT_CHARS = 4000


def run_python_snippet(code: str, timeout: int = 10) -> dict:
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[:MAX_OUTPUT_CHARS],
            "stderr": result.stderr[:MAX_OUTPUT_CHARS],
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Code timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def run_tests(path: str = ".", command: str = None, timeout: int = 60) -> dict:
    if not command:
        if os.path.exists(os.path.join(path, "pytest.ini")) or os.path.exists(os.path.join(path, "pyproject.toml")):
            command = "pytest"
        elif os.path.exists(os.path.join(path, "package.json")):
            command = "npm test"
        else:
            return {"error": "Could not auto-detect a test command for this path — specify one explicitly"}

    try:
        result = subprocess.run(
            command, shell=True, cwd=path, capture_output=True, text=True, timeout=timeout,
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[:MAX_OUTPUT_CHARS],
            "stderr": result.stderr[:MAX_OUTPUT_CHARS],
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Tests timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def lint_code(path: str = ".") -> dict:
    if shutil.which("ruff"):
        cmd = ["ruff", "check", path]
    elif shutil.which("eslint"):
        cmd = ["eslint", path]
    elif shutil.which("flake8"):
        cmd = ["flake8", path]
    else:
        return {"error": "No supported linter found on this system (tried ruff, eslint, flake8)"}

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "linter": cmd[0],
            "returncode": result.returncode,
            "output": (result.stdout or result.stderr)[:MAX_OUTPUT_CHARS],
        }
    except Exception as e:
        return {"error": str(e)}
