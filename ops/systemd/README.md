# Compliance systemd timers

These units are production examples for running local backups, pruning old local
backup files, and smoke-testing the latest backup artifacts.

Install them on the server:

```bash
cd /opt/compliance/app
sudo cp ops/systemd/compliance-backup.service /etc/systemd/system/
sudo cp ops/systemd/compliance-backup.timer /etc/systemd/system/
sudo cp ops/systemd/compliance-restore-test.service /etc/systemd/system/
sudo cp ops/systemd/compliance-restore-test.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now compliance-backup.timer
sudo systemctl enable --now compliance-restore-test.timer
systemctl list-timers 'compliance-*'
```

The backup timer runs daily and keeps local backup files for 30 days by default.
Change `BACKUP_RETENTION_DAYS` in `compliance-backup.service` if the local
retention window needs to be longer or shorter.

The restore-test timer runs weekly. It validates that the newest PostgreSQL dump
and attachment archive are readable; it does not overwrite any production data.
A full restore into staging or a temporary environment should still be done on a
regular schedule.
