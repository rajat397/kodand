# Systemd user units (optional, recommended for interactive use)

Copy to `~/.config/systemd/user/`, then:

```sh
systemctl --user daemon-reload
systemctl --user enable --now laya-serve kodand-recalld
```

`Restart=always` self-heals after OOM/kill; daemons survive session deaths. Why this matters
led with evidence: three run-crashes on 2026-10-30/31 were recovered by these units retro-fitted
with `Restart=always`; before that, transient `systemd-run` silent exits cost ~8h of a run.

- `laya-serve.service` — decision-model server, ~830 MB RSS once loaded, warm calls <1.5 s
- `kodand-recalld.service` — per-repo sqlite recall, ~0.3–0.5 s warm, tiny RSS
