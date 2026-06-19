#!/usr/bin/env python3
"""SSH login script: connect as a normal user, then run commands with sudo."""

import gzip
import os
import shutil
import signal
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, date
from tkcalendar import Calendar


def parse_log_date(name):
    """Return the log date from a filename, or None if the name is not a supported log file."""
    if name == "tango.log":
        return datetime.now().strftime("%Y-%m-%d")

    if name.startswith("tango.log."):
        suffix = name[len("tango.log."):]
        date_part = suffix.split(".")[0]
        if len(date_part) == 10 and date_part[4] == "-" and date_part[7] == "-":
            return date_part

    return None


def install_interrupt_handler():
    """Ensure Ctrl+C interrupts the script even during blocking SSH I/O."""

    def _handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handler)


def run_command(host, port, username, command, sudo=False, sudo_password=None, timeout=10, key_file=None):
    if sudo and sudo_password is None:
        raise ValueError("sudo_password is required for sudo commands")

    if shutil.which("ssh") is None:
        raise RuntimeError("The 'ssh' executable was not found on PATH.")

    remote_command = f"sudo -S -p '' {command}" if sudo else command
    ssh_args = [
        "ssh",
        "-o",
        "ConnectTimeout=%s" % timeout,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(port),
        f"{username}@{host}",
        remote_command,
    ]

    if key_file:
        ssh_args[1:1] = ["-i", key_file]

    process = subprocess.Popen(
        ssh_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    try:
        if sudo:
            process.stdin.write(sudo_password + "\n")
            process.stdin.flush()
        out, err = process.communicate(timeout=timeout)
        return process.returncode, out, err
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
        raise RuntimeError(f"SSH command timed out after {timeout} seconds") from None
    finally:
        if process.stdin is not None:
            process.stdin.close()


def find_notepadpp_executable():
    """Locate Notepad++ in PATH or in common Windows install folders."""
    candidates = [
        "notepad++.exe",
        "notepad++",
    ]

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    common_paths = [
        os.path.join(os.environ.get("ProgramFiles", ""), "Notepad++", "notepad++.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Notepad++", "notepad++.exe"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Notepad++", "notepad++.exe"),
    ]

    for path in common_paths:
        if os.path.isfile(path):
            return path

    return None


def find_text_position(path, search_text):
    """Return the one-based line and column of the first text match."""
    if not search_text:
        return None

    with open(path, "r", encoding="utf-8", errors="replace") as source:
        for line_number, line in enumerate(source, start=1):
            column = line.find(search_text)
            if column != -1:
                return line_number, column + 1

    return None


def open_with_notepadpp(path, search_text=None):
    """Open a file in Notepad++, jumping to the first supplied-text match."""
    exe = find_notepadpp_executable()
    if not exe:
        messagebox.showerror(
            "Notepad++ not found",
            "Could not find Notepad++ in PATH or in common install locations.",
        )
        return False

    command = [exe]
    if search_text and search_text.strip():
        normalized_search_text = search_text.strip()
        command.extend(["-search", normalized_search_text])
        match_position = find_text_position(path, normalized_search_text)
        if match_position:
            line_number, column = match_position
            command.extend([f"-n{line_number}", f"-c{column}"])
    command.append(path)

    subprocess.Popen(command, shell=False)
    return True


def download_remote_file(host, port, username, remote_path, local_dir, timeout=10, key_file=None):
    """Download a remote file using SCP into the local Logs directory."""
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, os.path.basename(remote_path))

    scp_args = [
        "scp",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-P",
        str(port),
        f"{username}@{host}:{remote_path}",
        local_path,
    ]

    if key_file:
        scp_args[1:1] = ["-i", key_file]

    completed = subprocess.run(
        scp_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or f"Failed to download {remote_path}"
        )

    return local_path


def decompress_file(path):
    """If the file is gzipped, decompress it next to the original file and return the new path."""
    if not path.lower().endswith(".gz"):
        return path

    output_path = path[:-3]
    with gzip.open(path, "rb") as src, open(output_path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return output_path


def choose_log_file(paths):
    if not paths:
        return None

    root = tk.Tk()
    root.title("Select date and TransUID")
    root.geometry("520x420")

    selected = {"date": None, "text": "", "bank": ""}
    valid_dates = {}
    for path in paths:
        name = path.split("/")[-1]
        date_part = parse_log_date(name)
        if date_part:
            valid_dates[date_part] = path

    if not valid_dates:
        root.destroy()
        return None

    sorted_dates = sorted(valid_dates)
    default_date = sorted_dates[0]
    year = int(default_date[:4]) if len(default_date) >= 4 else datetime.now().year
    month = int(default_date[5:7]) if len(default_date) >= 7 else datetime.now().month
    day = int(default_date[8:10]) if len(default_date) >= 10 else datetime.now().day

    tk.Label(root, text="Select a date:").pack(pady=(10, 5))

    cal = Calendar(
        root,
        selectmode="day",
        year=year,
        month=month,
        day=day,
    )
    valid_date_objects = {}
    for date_value in valid_dates:
        try:
            event_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            valid_date_objects[event_date] = valid_dates[date_value]
            cal.calevent_create(
                date=event_date,
                text="",
                tags=["valid"],
            )
        except ValueError:
            continue
    cal.tag_config("valid", background="#c8f7c5", foreground="black")
    cal.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    def validate_selection(event=None):
        try:
            chosen = cal.get_date()
            if chosen is None:
                return
            chosen_date = datetime.strptime(chosen, "%m/%d/%y").date()
            if chosen_date not in valid_date_objects:
                cal.selection_clear()
                messagebox.showwarning(
                    "Invalid date",
                    "Please select one of the highlighted dates.",
                )
        except (ValueError, TypeError):
            cal.selection_clear()

    cal.bind("<<CalendarSelected>>", validate_selection)

    input_frame = tk.Frame(root)
    input_frame.pack(pady=(5, 5), fill=tk.X)

    tk.Label(input_frame, text="Bank/Acquirer:").pack(side=tk.LEFT, padx=(0, 5))
    bank_options = [
        "CASYS/STOPANSKA",
        "CASYS/FIBANK",
        "CASYS/RUBICON",
        "AKTIF/BKT",
        "EURONET/OTP",
        "NEXI/ALPHA",
        "BORICA/PROCREDIT",
    ]
    bank_var = tk.StringVar(root)
    bank_var.set("")
    bank_menu = tk.OptionMenu(input_frame, bank_var, *bank_options)
    bank_menu.config(width=22)
    bank_menu.pack(side=tk.LEFT)

    tk.Label(input_frame, text="TransUID:").pack(side=tk.LEFT, padx=(10, 5))
    text_entry = tk.Entry(input_frame, width=28)
    text_entry.pack(side=tk.LEFT)

    def on_select():
        try:
            chosen = cal.get_date()
            if chosen is None:
                return
            chosen_date = datetime.strptime(chosen, "%m/%d/%y").date()
            if chosen_date not in valid_date_objects:
                messagebox.showwarning(
                    "Invalid date",
                    "Please select one of the highlighted dates.",
                )
                return
            selected_text = text_entry.get().strip()
            selected["date"] = chosen_date.strftime("%Y-%m-%d")
            selected["text"] = selected_text
            selected["bank"] = bank_var.get()
            selected["path"] = valid_date_objects.get(chosen_date)
            root.destroy()
        except (ValueError, TypeError):
            messagebox.showwarning(
                "Invalid date",
                "Please select one of the highlighted dates.",
            )

    tk.Button(root, text="Select", command=on_select).pack(pady=(10, 10))
    root.mainloop()

    return selected["date"], selected["text"], selected["bank"], selected["path"]


DEFAULT_HOST = "10.1.110.84"
DEFAULT_USER = "j.arvanitis"
DEFAULT_SUDO_PASSWORD = "12345ja!@#$%"
LOCAL_LOG_DIR = r"C:\Users\j.arvanitis\Desktop\Tango\Logs"


def open_selected_remote_file(
    host,
    port,
    username,
    remote_path,
    timeout,
    key_file,
    local_dir=LOCAL_LOG_DIR,
    search_text=None,
):
    """Download and optionally decompress a remote file, then open it in Notepad++."""
    local_file = download_remote_file(
        host,
        port,
        username,
        remote_path,
        local_dir,
        timeout=timeout,
        key_file=key_file,
    )
    decompressed_file = decompress_file(local_file)
    if decompressed_file != local_file:
        print(f"Decompressed to: {decompressed_file}")
    open_with_notepadpp(decompressed_file, search_text=search_text)


def map_bank_to_audit_code(bank):
    """Map the selected bank/acquirer name to the expected audit code."""
    mapping = {
        "CASYS/STOPANSKA": "OPNBISOCAS01",
        "CASYS/FIBANK": "OPNBISOCAS01",
        "CASYS/RUBICON": "OPNBISOCAS01",
        "AKTIF/BKT": "OPNBISOBKT01",
        "EURONET/OTP": "OPNRENOTP01",
        "NEXI/ALPHA": "OPNBISOA01",
        "BORICA/PROCREDIT": "OPNWAY4B01",
        "NBG": "OPNWAY4N01",
        "EUROBANK": "OPNBISOE01",
        "COSMOTE/NEXI": "OPNBISOC01",
    }
    return mapping.get(bank)


def main():
    install_interrupt_handler()

    port = 22
    key_file = None
    timeout = 10
    command = "whoami"
    sudo_command = "su -c 'whoami'"

    try:
        sudo_password = DEFAULT_SUDO_PASSWORD

        code, out, err = run_command(
            DEFAULT_HOST,
            port,
            DEFAULT_USER,
            command,
            timeout=timeout,
            key_file=key_file,
        )
        if code != 0:
            raise RuntimeError(err.strip() or out.strip() or "SSH login failed")

        code, out, err = run_command(
            DEFAULT_HOST,
            port,
            DEFAULT_USER,
            sudo_command,
            sudo=True,
            sudo_password=sudo_password,
            timeout=timeout,
            key_file=key_file,
        )
        if code != 0:
            raise RuntimeError(err.strip() or out.strip() or "Sudo authentication failed")

        code, out, err = run_command(
            DEFAULT_HOST,
            port,
            DEFAULT_USER,
            "find /opt/tango/MLNPSP01/log -maxdepth 1 -name 'tango.log*' -print | sort",
            sudo=True,
            sudo_password=sudo_password,
            timeout=timeout,
            key_file=key_file,
        )

        file_list = [line.strip() for line in out.splitlines() if line.strip()]
        if file_list:
            selected = choose_log_file(file_list)
            if selected:
                selected_date, selected_text, selected_bank, selected_path = selected
                print(f"\nSelected date: {selected_date}")
                print(f"Selected bank/acquirer: {selected_bank}")
                if selected_text:
                    print(f"Entered text: {selected_text}")
                if selected_path:
                    print(f"Downloading log file from {selected_path}...")
                    print(f"Downloaded to: {selected_path}")
                    open_selected_remote_file(
                        DEFAULT_HOST,
                        port,
                        DEFAULT_USER,
                        selected_path,
                        timeout,
                        key_file,
                        search_text=selected_text,
                    )
            else:
                print("\nNo date selected.")
        else:
            messagebox.showinfo(
                "No log files",
                "No matching log files were found under /opt/tango/MLNPSP01/log.",
            )

        if selected_bank:
            audit_code = map_bank_to_audit_code(selected_bank)
            if audit_code:
                audit_date = selected_date.replace("-", "")
                special_audit_prefixes = [
                    "audit.PTMSPMLN01.",
                ]
                ptms_audit_path = f"/opt/tango/MLNPSP01/audit/audit.PTMSPMLN01.{selected_date}"
                ptms_audit_path_nodash = f"/opt/tango/MLNPSP01/audit/audit.PTMSPMLN01.{audit_date}"
                mapped_audit_path = f"/opt/tango/MLNPSP01/audit/audit.{audit_code}.{selected_date}"
                mapped_audit_path_nodash = f"/opt/tango/MLNPSP01/audit/audit.{audit_code}.{audit_date}"

                audit_candidates = [
                    ptms_audit_path,
                    ptms_audit_path_nodash,
                    mapped_audit_path,
                    mapped_audit_path_nodash,
                ]

                audit_list_code, audit_list_out, audit_list_err = run_command(
                    DEFAULT_HOST,
                    port,
                    DEFAULT_USER,
                    (
                        "find /opt/tango/MLNPSP01/audit -maxdepth 1 -type f \\( "
                        f"-name 'audit.PTMSPMLN01.*{selected_date}*' -o "
                        f"-name 'audit.PTMSPMLN01.*{audit_date}*' -o "
                        f"-name 'audit.{audit_code}.*{selected_date}*' -o "
                        f"-name 'audit.{audit_code}.*{audit_date}*' \\) -print | sort"
                    ),
                    sudo=True,
                    sudo_password=sudo_password,
                    timeout=timeout,
                    key_file=key_file,
                )
                if audit_list_code == 0:
                    for line in audit_list_out.splitlines():
                        candidate = line.strip()
                        if candidate and candidate not in audit_candidates:
                            audit_candidates.append(candidate)

                # Reorder candidates so special audit files are tried first.
                special_candidates = [
                    candidate
                    for candidate in audit_candidates
                    if any(
                        os.path.basename(candidate).startswith(prefix)
                        for prefix in special_audit_prefixes
                    )
                ]
                other_candidates = [
                    candidate
                    for candidate in audit_candidates
                    if not any(
                        os.path.basename(candidate).startswith(prefix)
                        for prefix in special_audit_prefixes
                    )
                ]
                audit_candidates = list(dict.fromkeys(special_candidates + other_candidates))

                downloaded_audits = 0
                for audit_remote_path in audit_candidates:
                    print(f"Checking audit file: {audit_remote_path}")
                    audit_check_code, audit_out, audit_err = run_command(
                        DEFAULT_HOST,
                        port,
                        DEFAULT_USER,
                        f"test -f '{audit_remote_path}' && echo EXISTS || echo MISSING",
                        sudo=True,
                        sudo_password=sudo_password,
                        timeout=timeout,
                        key_file=key_file,
                    )
                    if audit_out.strip() == "EXISTS":
                        print(f"Opening audit file: {audit_remote_path}")
                        open_selected_remote_file(
                            DEFAULT_HOST,
                            port,
                            DEFAULT_USER,
                            audit_remote_path,
                            timeout,
                            key_file,
                            search_text=selected_text,
                        )
                        downloaded_audits += 1

                if not downloaded_audits:
                    print(
                        f"No audit file found for bank/acquirer: {selected_bank} on {selected_date}"
                    )
                else:
                    print(f"Downloaded {downloaded_audits} audit file(s).")
            else:
                print(f"No audit mapping found for bank/acquirer: {selected_bank}")
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Closing SSH connection...")
        return 130
    except Exception as exc:
        message = str(exc)
        if "timeout" in message.lower() or "timed out" in message.lower():
            print(f"SSH connection timed out after {timeout} seconds: {message}")
        else:
            print(f"SSH connection failed: {message}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
