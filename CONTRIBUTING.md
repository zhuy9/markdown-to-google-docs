# Contributing

Read [AGENTS.md](AGENTS.md), the [architecture](docs/ARCHITECTURE.md), and the
[roadmap](docs/ROADMAP.md) before changing code. Keep the IR independent of
Google Docs and implement one milestone at a time.

Follow the setup commands in [README.md](README.md). Verify packaging with
`python -m build` and skill archives with `python tools/build_skill.py`. Install
`.[dev,google]` for tests. Run the offline tests with
`python -m unittest discover -s tests -v`; keep these tests offline and use
synthetic fixtures. After `npm ci`, run real Mermaid checks with
`python -m unittest discover -s tests/integration -v`.
Document live integration results separately.

Before sharing changes, run `git diff --check`, review `git status --short`,
and inspect new files as well as diffs. Keep private documents, credentials,
generated output, and `.temp/` out of Git and package archives.

`CLAUDE.md` must remain a relative symlink to `AGENTS.md`. On Windows, enable
Developer Mode or use an account permitted to create symbolic links. Ensure
Git is configured with `core.symlinks=true` when checking out this repository;
otherwise it may check out link contents as a regular file.

To create the link when it is missing, run this from the repository root in
a shell with the required privilege:

```bash
python -c "import os; os.symlink('AGENTS.md', 'CLAUDE.md')"
```

Use a relative target so the link works on other machines. Some PowerShell
versions expand `New-Item` targets into absolute paths; verify with
`python -c "import os; print(os.readlink('CLAUDE.md'))"`.
