import subprocess

MAX_OUTPUT_CHARS = 8000

def run_shell(command: str, timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout[:MAX_OUTPUT_CHARS]
        stderr = result.stderr[:MAX_OUTPUT_CHARS]
        return {
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}
