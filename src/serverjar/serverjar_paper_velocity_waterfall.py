"""
Handles the update checking and downloading of these serverjars:
Paper, Velocity, Waterfall

All are from the PaperMC Team and use the same api structure which is the reason these are together
"""

import os
import re
import hashlib
import requests
from pathlib import Path
from rich.table import Table
from rich.console import Console
from rich.progress import Progress

from src.handlers.handle_config import config_value
from src.utils.console_output import rich_print_error
from src.utils.utilities import \
    api_do_request, convert_file_size_down, sanitize_filename


def get_installed_serverjar_version(file_server_jar_full_name) -> str:
    """
    Gets the installed version of the installed serverjar
    """
    serverjar_version_full = re.search(r"([\d]*.jar)", file_server_jar_full_name)
    try:
        serverjar_version = serverjar_version_full.group()
    except AttributeError:
        serverjar_version = serverjar_version_full
    serverjar_version = serverjar_version.replace('.jar', '')

    return serverjar_version


def get_version_group(file_server_jar_full_name) -> str:
    """
    Gets the version group which is used for the papermc api
    """
    version_group = re.sub(r"-\d*.jar$", "", file_server_jar_full_name)
    version_group = re.sub(r"^(\w*\-)", "", version_group)
    return version_group


def find_latest_available_version(file_server_jar_full_name, version_group) -> int:
    """
    Gets the latest available version of the installed serverjar version
    """
    if "paper" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/paper/versions/{version_group}/builds"
    elif "waterfall" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/waterfall/versions/{version_group}/builds"
    elif "velocity" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/velocity/versions/{version_group}/builds"

    versions = api_do_request(url)
    if "status" in versions: 
        return None
    latest_version = versions["builds"][-1]["build"]
    return latest_version


def get_versions_behind(serverjar_version, latest_version) -> int:
    """
    Gets the number diffference between the two versions
    """
    versions_behind = int(latest_version) - int(serverjar_version)
    return versions_behind


def get_papermc_download_file_name(mc_version, serverjar_version, file_server_jar_full_name) -> tuple:
    """
    Gets the download name and expected hash from the papermc api
    """
    if "paper" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/paper/versions/{mc_version}/builds/{serverjar_version}"
    elif "waterfall" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/waterfall/versions/{mc_version}/builds/{serverjar_version}"
    elif "velocity" in file_server_jar_full_name:
        url = f"https://api.papermc.io/v2/projects/velocity/versions/{mc_version}/builds/{serverjar_version}"
    build_details = api_do_request(url)
    download_name = sanitize_filename(build_details["downloads"]["application"]["name"])
    expected_hash = build_details["downloads"]["application"].get("sha256")
    return download_name, expected_hash


def serverjar_papermc_check_update(file_server_jar_full_name) -> None:
    """
    Checks the installed paper serverjar if an update is available
    """
    serverjar_version = get_installed_serverjar_version(file_server_jar_full_name)
    if serverjar_version is None:
        rich_print_error("Error: An error occured while checking the installed serverjar version")
        return None
    
    version_group = get_version_group(file_server_jar_full_name)
    if version_group is None:
        rich_print_error("Error: An error occured while checking the installed version group of the installed serverjar")
        return None

    latest_version = find_latest_available_version(file_server_jar_full_name, version_group)
    if latest_version is None:
        rich_print_error("Error: An error occured while checking for the latest available version of the serverjar")
        return None

    versions_behind = get_versions_behind(serverjar_version, latest_version)

    rich_table = Table(box=None)
    rich_table.add_column("Name", style="bright_magenta")
    rich_table.add_column("Installed V.", justify="right", style="green")
    rich_table.add_column("Latest V.", justify="right", style="bright_green")
    rich_table.add_column("Versions behind", justify="right", style="cyan")

    rich_table.add_row(
            file_server_jar_full_name, 
            serverjar_version, 
            str(latest_version), 
            str(versions_behind) 
        )
    rich_console = Console()
    rich_console.print(rich_table)
    return None


def serverjar_papermc_update(
    server_jar_version: str="latest",
    mc_version: str=None,
    file_server_jar_full_name: str=None,
    serverjar_to_download: str=None
    ) -> bool:
    """
    Handles the downloading of the papermc serverjar and verifies its artifact signature
    """
    config_values = config_value()
    path_server_root = config_values.path_to_plugin_folder
    help_path = Path('/plugins')
    help_path_str = str(help_path)
    path_server_root = Path(str(path_server_root).replace(help_path_str, ''))

    if file_server_jar_full_name is None and mc_version is None:
        rich_print_error("Error: Please specifiy the minecraft version as third argument!")
        return False

    if file_server_jar_full_name is None and serverjar_to_download is None:
        rich_print_error("Error: Couldn't get serverjar name to download")
        return False

    if mc_version is None:
        mc_version = get_version_group(file_server_jar_full_name)

    if file_server_jar_full_name is None:
        papermc_serverjar = serverjar_to_download
    else:
        papermc_serverjar = file_server_jar_full_name

    if server_jar_version == "latest" or server_jar_version is None:
        server_jar_version = find_latest_available_version(papermc_serverjar, mc_version)

    rich_console = Console()
    rich_console.print(
        f"\n [not bold][bright_white]● [bright_magenta]{papermc_serverjar.capitalize()}" + \
        f" [cyan]→ [bright_green]{server_jar_version}"
    )

    if file_server_jar_full_name is not None:
        serverjar_version = get_installed_serverjar_version(file_server_jar_full_name)
        if get_versions_behind(serverjar_version, server_jar_version) == 0:
            rich_console.print("    [not bold][bright_green]No updates currently available!")
            return False

    try:
        download_file_name, expected_hash = get_papermc_download_file_name(mc_version, server_jar_version, papermc_serverjar)
    except KeyError:
        rich_print_error(f"    Error: This version wasn't found for {mc_version}")
        rich_print_error(f"    Reverting to latest version for {mc_version}")
        try:
            server_jar_version = find_latest_available_version(papermc_serverjar, mc_version)
            download_file_name, expected_hash = get_papermc_download_file_name(mc_version, server_jar_version, papermc_serverjar)
        except KeyError:
            rich_print_error(f"    Error: Version {mc_version} wasn't found for {papermc_serverjar.capitalize()} in the papermc api")
            return False

    if "paper" in papermc_serverjar:
        url = f"https://api.papermc.io/v2/projects/paper/versions/{mc_version}/builds/{server_jar_version}/downloads/{download_file_name}"
    elif "waterfall" in papermc_serverjar:
        url = f"https://api.papermc.io/v2/projects/waterfall/versions/{mc_version}/builds/{server_jar_version}/downloads/{download_file_name}"
    elif "velocity" in papermc_serverjar:
        url = f"https://api.papermc.io/v2/projects/velocity/versions/{mc_version}/builds/{server_jar_version}/downloads/{download_file_name}"
    
    download_path = Path(f"{path_server_root}/{download_file_name}")

    with Progress(transient=True) as progress:
        header = {'user-agent': 'pluGET/1.0'}
        r = requests.get(url, headers=header, stream=True, timeout=30)
        try:
            file_size = int(r.headers.get('Content-Length'))
            download_task = progress.add_task("    [cyan]Downloading...", total=file_size)
        except TypeError:
            file_size = 0
        with open(download_path, 'wb') as f:
            for data in r.iter_content(chunk_size=65536):
                f.write(data)
                if file_size == 0:
                    continue
                progress.update(download_task, advance=len(data))

    
    file_size_data = convert_file_size_down(convert_file_size_down(file_size))
    rich_console.print("    [not bold][bright_green]Downloaded[bright_magenta] " + (str(file_size_data)).rjust(9) + \
        f" MB [cyan]→ [white]{download_path}")

    # Verify Cryptographic Hash
    if expected_hash:
        rich_console.print("    [cyan]Verifying sha256 checksum...")
        h = hashlib.sha256()
        with open(download_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        
        calculated_hash = h.hexdigest()
        if calculated_hash != expected_hash:
            rich_print_error("Error: Artifact verification failed! Hash mismatch.")
            rich_print_error(f"Expected: {expected_hash}")
            rich_print_error(f"Calculated: {calculated_hash}")
            os.remove(download_path)
            return False
        else:
            rich_console.print("    [not bold][bright_green]Artifact signature verified successfully.")

    return True