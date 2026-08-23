import subprocess

MAX_OUTPUT_CHARS = 4000


def git_status(path: str = ".") -> dict:
    try:
        result = subprocess.run(
            ["git", "-C", path, "status", "--short", "--branch"],
            capture_output=True, text=True, timeout=15,
        )
        return {"returncode": result.returncode, "output": (result.stdout or result.stderr)[:MAX_OUTPUT_CHARS]}
    except Exception as e:
        return {"error": str(e)}


def git_diff(path: str = ".", staged: bool = False) -> dict:
    try:
        cmd = ["git", "-C", path, "diff"]
        if staged:
            cmd.append("--staged")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {"returncode": result.returncode, "diff": (result.stdout or result.stderr)[:MAX_OUTPUT_CHARS]}
    except Exception as e:
        return {"error": str(e)}
