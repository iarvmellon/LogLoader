# LogAnalyzer SSH Sudo Login Script

A small Python utility that connects to a hardcoded remote host over the system `ssh` client, runs a normal user command, and then executes a second command with `sudo`.

## Hardcoded Settings

- Host: `10.1.110.84`
- SSH user: `j.arvanitis`
- Sudo password: `12345ja!@#$%`

## Requirements

- Python 3
- The Python packages listed in `requirements.txt`, including `tkcalendar`

Install the dependency with:

```bash
pip install -r requirements.txt
```

## Usage

The host, SSH username, and sudo password are hardcoded. You only need to provide the SSH password if you do not want to type it interactively.

```bash
python main.py --password "<SSH_PASSWORD>"
```

The script supports:

- `--port`: SSH port (default: 22)
- `--key-file`: path to a private key file to use for authentication
- `--timeout`: SSH timeout in seconds (default: 10)
- `--command`: command to run as the normal user (default: `whoami`)
- `--sudo-command`: command to run with sudo (default: `su -c 'whoami'`)

The initial SSH and sudo checks are silent when successful. Connection details,
command output, usernames, and working directories are not printed; an error is
shown only when SSH login or the sudo check fails.

After a log date and bank/acquirer are selected, the script downloads and opens
all matching audit files for that date. This includes `audit.PTMSPMLN01...`,
and the bank-specific mapped `audit.OPN...` file. Files beginning with
`audit.PPN...` are ignored.

When a TransUID is entered, the script finds its first occurrence in every
downloaded log and audit file. Notepad++ opens directly at the matching line and
column using its supported `-n` and `-c` arguments. If the TransUID is empty or
is not found in a file, that file opens normally. The unsupported `-search`
argument is not used, so Notepad++ does not interpret the TransUID as a filename.

If you press Ctrl+C while the script is running, it now prints a message and closes the SSH session and command channels cleanly before exiting.

## Example

```bash
python main.py --password "YourSSHPassword"
```

This will connect to `10.1.110.84` as `j.arvanitis` by using the system SSH client, which matches the behavior of running `ssh j.arvanitis@10.1.110.84` manually. If your key is not in the default SSH agent location, you can also pass `--key-file`.
