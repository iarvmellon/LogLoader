# LogLoader

LogLoader is a Windows desktop utility for locating, downloading, and opening
Tango log and audit files from a remote Linux server. It connects through the
system OpenSSH client, presents the available log dates in a calendar, downloads
the selected files with SCP, decompresses `.gz` files when necessary, and opens
the results in Notepad++.

The application is configured directly in `main.py`. It does not accept
command-line options.

## Main workflow

When `python main.py` is started, the application performs these steps:

1. Connects to the hardcoded host as the configured SSH user.
2. Runs `whoami` to verify the normal SSH session.
3. Runs `su -c 'whoami'` through `sudo` to verify sudo access.
4. Searches `/opt/tango/MLNPSP01/log` for files named `tango.log*`.
5. Displays a calendar containing the dates for which a supported log file was
   found. Available dates are highlighted in green.
6. Lets the user select a bank/acquirer and optionally enter a TransUID.
7. Downloads the selected Tango log into the local Logs directory.
8. Searches `/opt/tango/MLNPSP01/audit` for the corresponding PTMS and
   bank-specific audit files.
9. Downloads every matching audit file and opens the downloaded files in
   Notepad++.

If a TransUID was entered, Notepad++ opens each file at its first occurrence.
If the value is empty or is not found, the file opens normally.

## Hardcoded configuration

The server-wide settings are defined near the middle of `main.py`:

| Setting | Current value | Purpose |
| --- | --- | --- |
| `DEFAULT_HOST` | `10.1.110.84` | Remote SSH server |
| `DEFAULT_USER` | `j.arvanitis` | Remote SSH username |
| `DEFAULT_SUDO_PASSWORD` | `<hidden>` | Password supplied to `sudo -S`; configured in `main.py` |
| `LOCAL_LOG_DIR` | `C:\Users\j.arvanitis\Desktop\Tango\Logs` | Download destination |

The following connection and command settings are local variables at the start
of `main()`:

| Variable | Current value | Purpose |
| --- | --- | --- |
| `port` | `22` | SSH and SCP port |
| `key_file` | `None` | Optional private-key path; `None` uses the SSH agent/default SSH configuration |
| `timeout` | `10` | SSH timeout in seconds |
| `command` | `whoami` | Initial command run as the normal user |
| `sudo_command` | `su -c 'whoami'` | Initial command run through sudo |

Edit these values in `main.py` when the server configuration changes. Since CLI
argument parsing has been removed, options such as `--port`, `--key-file`,
`--timeout`, `--command`, and `--sudo-command` are not supported.

> **Security note:** The sudo password is currently stored as plain text in the
> source code. Keep the repository and copies of the script appropriately
> protected.

## Supported log filenames

The calendar recognizes the following remote filenames:

- `tango.log` — assigned to the current local date.
- `tango.log.YYYY-MM-DD` — assigned to the date in the filename.
- `tango.log.YYYY-MM-DD.<extension>` — also supported, including `.gz`.

Files without a valid `YYYY-MM-DD` date in the expected position are ignored by
the calendar.

## Bank and audit mappings

The selected bank/acquirer determines the bank-specific audit code:

| Bank/acquirer | Audit code |
| --- | --- |
| `CASYS/STOPANSKA` | `OPNBISOCAS01` |
| `CASYS/FIBANK` | `OPNBISOCAS01` |
| `CASYS/RUBICON` | `OPNBISOCAS01` |
| `AKTIF/BKT` | `OPNBISOBKT01` |
| `EURONET/OTP` | `OPNRENOTP01` |
| `NEXI/ALPHA` | `OPNBISOA01` |
| `BORICA/PROCREDIT` | `OPNWAY4B01` |

For the selected date, the application checks both dashed (`YYYY-MM-DD`) and
compact (`YYYYMMDD`) date formats. It looks for:

- PTMS audit files beginning with `audit.PTMSPMLN01.`
- Audit files beginning with `audit.<mapped-audit-code>.`

PTMS audit files are tried first. Duplicate paths are removed, all existing
matching files are downloaded, and unrelated `audit.PPN...` files are not part
of the search.

## Requirements

- Windows with Python 3.
- The Python packages listed in `requirements.txt`.
- The Windows OpenSSH `ssh` and `scp` executables available on `PATH`.
- Network access to the configured server and SSH port.
- SSH authentication through the default key/agent configuration, or a private
  key configured in `key_file`.
- Permission for the configured user to run the required remote commands with
  `sudo`.
- Notepad++ installed in a standard location or available on `PATH`.

Install the Python dependencies from PowerShell or Command Prompt:

```bash
pip install -r requirements.txt
```

No Linux package installation is required by this project.

## Running the application

From the repository directory, run:

```bash
python main.py
```

There are no required or optional command-line arguments.

In the selection window:

1. Choose one of the green highlighted dates.
2. Select a bank/acquirer from the dropdown.
3. Optionally enter a TransUID.
4. Select **Select** to begin downloading and opening the files.

Selecting a date that is not highlighted displays a warning and clears the
selection.

## Download and decompression behavior

Remote files are copied to `LOCAL_LOG_DIR` using SCP. The destination directory
is created automatically if it does not exist.

When a downloaded filename ends in `.gz`, LogLoader decompresses it beside the
original download and opens the decompressed file. For example,
`tango.log.2026-06-19.gz` produces `tango.log.2026-06-19`. The downloaded `.gz`
file is retained.

## Notepad++ detection and TransUID navigation

LogLoader searches for Notepad++ in this order:

1. `notepad++.exe` or `notepad++` on `PATH`.
2. `%ProgramFiles%\Notepad++\notepad++.exe`.
3. `%ProgramFiles(x86)%\Notepad++\notepad++.exe`.
4. `%USERPROFILE%\AppData\Local\Programs\Notepad++\notepad++.exe`.

The first TransUID match is found locally with a case-sensitive text search.
LogLoader passes Notepad++ its supported `-n<line>` and `-c<column>` arguments
to position the cursor. It does not use the unsupported `-search` argument.

## Error handling

- A failed normal-user or sudo check stops the workflow and prints the SSH
  error.
- A timeout reports the configured timeout value.
- If no matching Tango logs exist, the application displays an information
  dialog.
- If an audit mapping or audit file cannot be found, the application reports it
  in the console and continues safely.
- If Notepad++ cannot be located, the application displays an error dialog.
- Pressing `Ctrl+C` interrupts the operation, closes the active SSH process, and
  exits with status code `130`.

Successful execution exits with status code `0`; other handled failures exit
with status code `1`.

## Project files

| File | Description |
| --- | --- |
| `main.py` | SSH/SCP workflow, GUI, file handling, and Notepad++ integration |
| `requirements.txt` | Python dependency versions |
| `README.md` | Project configuration and usage documentation |
| `AGENTS.md` | Repository-specific development instructions |
