from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
worker_entry = (ROOT / "app" / "worker_entry.py").read_text(encoding="utf-8")
task_images = (ROOT / "app" / "services" / "task_images.py").read_text(encoding="utf-8")

assert "def _detach_worker_stdin()" in worker_entry
assert "os.open(os.devnull, os.O_RDONLY)" in worker_entry
assert "os.dup2(devnull_fd, 0)" in worker_entry
assert "[worker] stdin detached: /dev/null" in worker_entry
assert worker_entry.index("_detach_worker_stdin()", worker_entry.index("def main()")) < worker_entry.index("worker_runtime_paths()", worker_entry.index("def main()"))

# Multimodal tasks intentionally provide prompt bytes through their own pipe;
# detaching the parent worker stdin must not remove this explicit input path.
assert "subprocess.run(sys.argv[2:],input=prompt,text=True)" in task_images

print("WORKER_STDIN_V102=OK")
