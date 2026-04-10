"""Holds the utility code for pluGET and web request functions.

This module provides helper functions for API requests, file system management,
and version checking.
"""

import os
import sys
import shutil
import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import requests
from rich.console import Console
from rich.table import Table

from src.utils.console_output import rich_print_error

_WINDOWS_RESERVED_RE = re.compile(
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$',
    re.IGNORECASE | re.ASCII
)
# Assuming circular import management is handled by Python's import system or
# ConfigValue is imported inside functions where needed if circular dep exists.
# For this refactor, we import ConfigValue for type hints.
from src.handlers.handle_config import ConfigValue
from src.settings import PLUGETVERSION


def get_command_help(command: str) -> None:
    """Prints the help page for commands.

    Args:
        command (str): The console command to show help for (e.g., 'all', 'get').

    Returns:
        None
    """
    rich_console = Console()
    rich_table = Table(box=None)
    rich_table.add_column(
        "Command", justify="left", style="bright_blue", no_wrap=True
    )
    rich_table.add_column("Object", style="bright_magenta")
    rich_table.add_column("Params", justify="left", style="cyan")
    rich_table.add_column("Description", justify="left", style="white")

    # Simplified logic for readability and maintenance
    rows: List[Tuple[str, str, Optional[str], str]] = []

    if command in ["all", "check"]:
        rows.extend([
            ("check", "Name/all", None, "Check for an update of an installed plugin"),
            ("check", "serverjar", None, "Check for an update for the installed serverjar"),
        ])
    
    if command in ["all", "exit"]:
        rows.append(("exit", "./anything", None, "Exit pluGET"))

    if command in ["all", "get"]:
        rows.append(("get", "Name/ID", None, "Downloads the latest version of a plugin"))

    if command in ["all", "get-paper"]:
        rows.append(("get-paper", "PaperVersion", "McVersion", "Downloads a specific PaperMc version"))
    
    if command in ["all", "get-purpur"]:
        rows.append(("get-purpur", "PurpurVersion", "McVersion", "Downloads a specific Purpur version"))

    if command in ["all", "get-velocity"]:
        rows.append(("get-velocity", "VelocityVersion", "McVersion", "Downloads a specific Velocity version"))
        
    if command in ["all", "get-waterfall"]:
        rows.append(("get-waterfall", "WaterfallVersion", "McVersion", "Downloads a specific Waterfall version"))
        
    if command in ["all", "get-github"]:
        rows.append(("get-github", "owner/repo", "plugin-name", "Downloads latest plugin from GitHub releases"))
        
    if command in ["all", "get-modrinth"]:
        rows.append(("get-modrinth", "project-id", "featured", "Downloads latest plugin from Modrinth"))

    if command in ["all", "help"]:
        rows.append(("help", "./anything", None, "Get specific help to the commands of pluGET"))
        
    if command in ["all", "remove"]:
        rows.append(("remove", "Name", None, "Delete an installed plugin from the plugin folder"))

    if command in ["all", "search"]:
        rows.append(("search", "Name/all", None, "Search for a plugin and download the latest version"))
        
    if command in ["all", "search-github"]:
        rows.append(("search-github", "Name", None, "Search GitHub for plugins and download"))
        
    if command in ["all", "search-modrinth"]:
        rows.append(("search-modrinth", "Name", None, "Search Modrinth for plugins and download"))

    if command in ["all", "update"]:
        rows.extend([
            ("update", "Name/all", None, "Update installed plugins to the latest version"),
            ("update", "serverjar", None, "Update the installed serverjar to the latest version"),
        ])

    if not rows:
        rich_print_error(f"[not bold]Error: Help for command [bright_magenta]'{command}' [bright_red]not found!")
        rich_print_error("Use [bright_blue]'help all' [bright_red]to get a list of all commands.")
        return

    for row in rows:
        rich_table.add_row(row[0], row[1], row[2], row[3])

    rich_console.print(rich_table)


def check_for_pluGET_update() -> None:
    """Checks for a new version of pluGET via GitHub API.

    If a new version is available, prints a download link to the console.
    
    Returns:
        None
    """
    # Type assertion or proper handling required for API return
    response_data = api_do_request("https://api.github.com/repos/Neocky/pluGET/releases/latest")
    
    if not isinstance(response_data, dict):
        # Assuming error was handled in api_do_request or it returned None
        return None

    name: str = str(response_data.get("name", ""))
    # Get '.1.6.10' as output
    full_version_match = re.search(r"[\.?\d]*$", name)
    
    if not full_version_match:
        return None

    # Remove '.' to get '1.6.10' as output
    version_str = re.sub(r"^\.*", "", full_version_match.group())
    
    console = Console()
    try:
        pluget_installed_version_tuple = tuple(map(int, (PLUGETVERSION.split("."))))
        plugin_latest_version_tuple = tuple(map(int, (version_str.split("."))))
    except ValueError:
        console.print("Couldn't check if new version of pluGET is available")
        return None

    if pluget_installed_version_tuple < plugin_latest_version_tuple:
        print(f"A new version of pluGET is available: {version_str}")
        console.print("Download it here: ", end="")
        console.print(
            "https://github.com/Neocky/pluGET",
            style="link https://github.com/Neocky/pluGET",
        )
    return None


def api_do_request(url: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """Performs a GET request to the specified URL and returns parsed JSON.

    Args:
        url (str): The URL to request.

    Returns:
        Optional[Union[Dict[str, Any], List[Any]]]: Parsed JSON data (list or dict)
        or None if the request failed.
    """
    webrequest_header = {"user-agent": "pluGET/1.0"}
    try:
        response = requests.get(url, headers=webrequest_header, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        rich_print_error(f"Error: Couldn't create webrequest: {e}")
        return None

    try:
        api_json_data: Union[Dict[str, Any], List[Any]] = response.json()
    except ValueError:
        rich_print_error("Error: Couldn't parse json of webrequest")
        return None
        
    return api_json_data


def api_test_spiget() -> None:
    """Tests connectivity to the Spiget API.
    
    Exits the program if the API is unreachable or returns a non-200 status.
    """
    try:
        r = requests.get("https://api.spiget.org/v2/status", timeout=10)
        if r.status_code != 200:
            rich_print_error(
                "Error: Problems with the API detected. Please try it again later!"
            )
            sys.exit(1)
    except requests.exceptions.RequestException:
        rich_print_error(
            "Error: Couldn't make a connection to the API. Check your connection to the internet!"
        )
        sys.exit(1)
    return None


def create_temp_plugin_folder() -> Path:
    """Creates a temporary folder to store plugins.

    Returns:
        Path: The full path of the temporary folder.
    """
    path_temp_plugin_folder = Path("./TempSFTPFolder")
    if path_temp_plugin_folder.is_dir():
        return path_temp_plugin_folder

    try:
        path_temp_plugin_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        rich_print_error(
            f"Error: Creation of directory {path_temp_plugin_folder} failed"
        )
        rich_print_error(
            "       Please check for missing permissions in folder tree!"
        )
        sys.exit(1)
    return path_temp_plugin_folder


def remove_temp_plugin_folder() -> None:
    """Removes the temporary plugin folder and all its content."""
    try:
        shutil.rmtree(Path("./TempSFTPFolder"))
    except OSError as e:
        rich_print_error(f"Error: {e.filename} - {e.strerror}")
    return None


def sanitize_filename(filename: str) -> str:
    """Sanitizes a filename to prevent path traversal and shell injection attacks.

    Handles filenames received from external sources (APIs, user input) by:
    - Stripping directory components in a platform-independent way
    - Recursively removing path traversal sequences
    - Filtering characters via an allow-list (alphanumeric, dot, hyphen, underscore)
    - Guarding against Windows reserved device names

    Args:
        filename (str): The raw filename to sanitize.

    Returns:
        str: A safe filename containing only permitted characters.
    """
    # Strip directory components using PurePosixPath after normalising Windows
    # separators, so both /unix/style and C:\windows\style paths are handled
    # regardless of the host OS
    filename = PurePosixPath(filename.replace('\\', '/')).name
    # Recursively remove path traversal sequences to defeat nested payloads (e.g. '....//') 
    previous = None
    while previous != filename:
        previous = filename
        filename = filename.replace('..', '')
    # Allow-list: keep only ASCII alphanumeric characters, dots, hyphens, and underscores
    filename = re.sub(r'[^a-zA-Z0-9_.\-]', '', filename)
    # Strip trailing dots and spaces that Windows silently strips (e.g. 'CON.' -> 'CON')
    filename = filename.rstrip('. ')
    # Guard against Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    if _WINDOWS_RESERVED_RE.match(filename):
        filename = f"_{filename}"
    # Truncate to 255 characters (common filesystem limit), preserving the extension
    max_length = 255
    max_ext_length = 16
    if len(filename) > max_length:
        path_obj = Path(filename)
        # suffix includes the dot (e.g., '.jar')
        suffix = path_obj.suffix[:max_ext_length + 1] if path_obj.suffix else ""
        stem = path_obj.stem
        # max(0, ...) prevents negative slicing if max_length is very small
        stem_limit = max(0, max_length - len(suffix))
        # If there's no stem (e.g. filename was just an extension),
        # fallback to simple truncation of the original string
        if not stem and suffix:
            filename = filename[:max_length]
        else:
            filename = f"{stem[:stem_limit]}{suffix}"
    # Ensure the filename isn't empty after sanitization
    if not filename:
        filename = f"downloaded_{uuid.uuid4().hex[:8]}.jar"
    return filename


def convert_file_size_down(file_size: Union[int, float]) -> float:
    """Converts bytes to Kilobytes (or KB to MB) by dividing by 1024.

    Args:
        file_size (Union[int, float]): The size to convert.

    Returns:
        float: Converted size rounded to 2 decimal places.
    """
    converted_file_size = float(file_size) / 1024
    converted_file_size = round(converted_file_size, 2)
    return converted_file_size


def check_local_plugin_folder(config_values: 'ConfigValue') -> None:
    """Checks if the local plugin folder exists.

    Args:
        config_values (ConfigValue): The configuration object.
        
    Raises:
        SystemExit: If the folder does not exist.
    """
    if config_values.local_seperate_download_path:
        plugin_folder_path = config_values.local_path_to_seperate_download_path
    else:
        plugin_folder_path = config_values.path_to_plugin_folder
    
    if not plugin_folder_path.is_dir():
        rich_print_error(
            f"Error: Local plugin folder '{plugin_folder_path}' couldn't be found! \n"
            "       Check the config and try again!"
        )
        sys.exit(1)
    return None


def check_requirements() -> None:
    """Checks if the local plugin folder exists.

    Ensures the local filesystem prerequisites are met.
    """
    config_values = ConfigValue()
    check_local_plugin_folder(config_values)
    return None
