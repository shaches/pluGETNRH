"""
File and functions which handle the download of the specific plugins
"""

import os
import re
import hashlib
from pathlib import Path
import requests
import zipfile
from zipfile import ZipFile

from rich.table import Table
from rich.console import Console
from rich.progress import Progress

from src.utils.utilities import convert_file_size_down, api_do_request, sanitize_filename
from src.utils.console_output import rich_print_error
from src.handlers.handle_config import config_value


def handle_regex_plugin_name(full_plugin_name) -> str:
    """
    Return the plugin name after trimming clutter from name with regex operations
    """
    unwanted_plugin_name = re.search(r'(^\[+[a-zA-Z0-9\s\W*\.*\-*\+*\%*\,]*\]+)', full_plugin_name)
    if bool(unwanted_plugin_name):
        unwanted_plugin_name_string = unwanted_plugin_name.group()
        full_plugin_name = full_plugin_name.replace(unwanted_plugin_name_string, '')

    plugin_name = re.search(r'([a-zA-Z]\d*)+(\s?\-*\_*[a-zA-Z]\d*\+*\-*\'*)+', full_plugin_name)
    try:
        plugin_name_full_string = plugin_name.group()
        found_plugin_name = plugin_name_full_string.replace(' ', '')
    except AttributeError:
        found_plugin_name = unwanted_plugin_name_string
    return found_plugin_name


def get_version_id_spiget(plugin_id, plugin_version) -> str:
    """
    Returns the version id of the plugin
    """
    if plugin_version == None or plugin_version == 'latest':
        url = f"https://api.spiget.org/v2/resources/{plugin_id}/versions/latest"
        response = api_do_request(url)
        if response == None:
            return None
        version_id = response["id"]
        return version_id

    url = f"https://api.spiget.org/v2/resources/{plugin_id}/versions?size=100&sort=-name"
    version_list = api_do_request(url)
    if version_list == None:
        return None
    for plugins in version_list:
        plugin_update = plugins["name"]
        version_id = plugins["id"]
        if plugin_update == plugin_version:
            return version_id
    return version_list[0]["id"]


def get_version_name_spiget(plugin_id, plugin_version_id) -> str:
    """
    Returns the name of a specific version
    """
    url = f"https://api.spiget.org/v2/resources/{plugin_id}/versions/{plugin_version_id}"
    response = api_do_request(url)
    if response == None:
        return None
    version_name = response["name"]
    return version_name


def get_download_path(config_values) -> str:
    """
    Reads the config and gets the path of the plugin folder
    """
    if config_values.local_seperate_download_path:
        return config_values.local_path_to_seperate_download_path
    return config_values.path_to_plugin_folder


def download_specific_plugin_version_spiget(plugin_id, download_path, version_id="latest", expected_hash=None, hash_algo="sha256") -> None:
    """
    Download a specific plugin with artifact verification
    """
    config_values = config_value()
    if version_id != "latest" and version_id != None:
        rich_print_error("Sorry but specific version downloads aren't supported because of cloudflare protection. :(")
        rich_print_error("Reverting to latest version.")

    url = f"https://api.spiget.org/v2/resources/{plugin_id}/download"

    with Progress(transient=True) as progress:
        header = {'user-agent': 'pluGET/1.0'}
        r = requests.get(url, headers=header, stream=True, timeout=30)
        try:
            file_size = int(r.headers.get('content-length'))
            download_task = progress.add_task("    [cyan]Downloading...", total=file_size)
        except TypeError:
            file_size = 0
        with open(download_path, 'wb') as f:
            for data in r.iter_content(chunk_size=32768):
                f.write(data)
                if file_size == 0:
                    continue
                progress.update(download_task, advance=len(data))

    console = Console()
    if file_size == 0:
        console.print(
            f"    [not bold][bright_green]Downloaded[bright_magenta]         file [cyan]→ [white]{download_path}"
        )
    elif file_size >= 1000000:
        file_size_data = convert_file_size_down(convert_file_size_down(file_size))
        console.print("    [not bold][bright_green]Downloaded[bright_magenta] " + (str(file_size_data)).rjust(9) + \
             f" MB [cyan]→ [white]{download_path}")
    else:
        file_size_data = convert_file_size_down(file_size)
        console.print("    [not bold][bright_green]Downloaded[bright_magenta] " + (str(file_size_data)).rjust(9) + \
             f" KB [cyan]→ [white]{download_path}")

    # Artifact Verification Step
    if expected_hash:
        console.print(f"    [cyan]Verifying {hash_algo} checksum...")
        h = hashlib.new(hash_algo)
        with open(download_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        
        calculated_hash = h.hexdigest()
        if calculated_hash != expected_hash:
            rich_print_error(f"Error: Artifact verification failed! Hash mismatch.")
            rich_print_error(f"Expected: {expected_hash}")
            rich_print_error(f"Calculated: {calculated_hash}")
            os.remove(download_path)
            return None
        else:
            console.print("    [not bold][bright_green]Artifact signature verified successfully.")

    try:
        with ZipFile(download_path, "r") as plugin_jar:
            plugin_jar.open("plugin.yml", "r")
    except (KeyError, zipfile.BadZipFile, OSError) as err:
        rich_print_error("Error: Downloaded plugin file was not a proper jar-file! Premium plugins are not supported!")
        rich_print_error("Removing file...")
        os.remove(download_path)
        raise

    return None


def get_specific_plugin_spiget(plugin_id: str, plugin_version: str = "latest", expected_hash: str = None) -> None:
    """
    Gets the specific plugin and calls the download function
    """
    config_values = config_value()
    download_path = get_download_path(config_values)

    url = f"https://api.spiget.org/v2/resources/{plugin_id}"
    plugin_details = api_do_request(url)
    if plugin_details is None:
        return None
    if not isinstance(plugin_details, dict):
        return None
    try:
        plugin_name = plugin_details.get("name")
    except KeyError:
        rich_print_error("Error: Plugin ID couldn't be found")
        return None
        
    plugin_name = handle_regex_plugin_name(plugin_name)
    plugin_version_id: str | None = get_version_id_spiget(plugin_id, plugin_version)
    plugin_version_name: str | None = get_version_name_spiget(plugin_id, plugin_version_id)
    plugin_download_name = sanitize_filename(f"{plugin_name}-{plugin_version_name}.jar")
    download_plugin_path = Path(f"{download_path}/{plugin_download_name}")
    
    if not plugin_version_id or not plugin_version_name:
        rich_print_error("Error: Webrequest timed out")
        return None
        
    if plugin_version == "latest":
        plugin_version_id = None
        
    try:
        download_specific_plugin_version_spiget(plugin_id, download_plugin_path, plugin_version_id, expected_hash)
    except Exception:
        raise
    return None


def search_specific_plugin_spiget(plugin_name) -> None:
    """
    Search for a name and return the top 10 results sorted for their download count
    Then ask for input and download that plugin
    """
    url= f"https://api.spiget.org/v2/search/resources/{plugin_name}?field=name&sort=-downloads"
    plugin_search_results = api_do_request(url)
    if plugin_search_results == None:
        rich_print_error("Error: Webrequest wasn't successfull!")
        return None

    print(f"Searching for {plugin_name}...")
    print(f"Found plugins:")
    rich_table = Table(box=None)
    rich_table.add_column("No.", justify="right", style="cyan", no_wrap=True)
    rich_table.add_column("Name", style="bright_magenta")
    rich_table.add_column("Downloads", justify="right", style="bright_green")
    rich_table.add_column("Description", justify="left", style="white")
    i = 1
    for found_plugin in plugin_search_results:
        plugin_name = handle_regex_plugin_name(found_plugin["name"])
        plugin_downloads = found_plugin["downloads"]
        plugin_description = found_plugin["tag"]
        rich_table.add_row(str(i), plugin_name, str(plugin_downloads), plugin_description)
        i += 1

    rich_console = Console()
    rich_console.print(rich_table)

    try:
        plugin_selected = input("Select your wanted resource (No.)(0 to exit): ")
    except KeyboardInterrupt:
        return None
    if plugin_selected == "0":
        return None
    try:
        plugin_selected =  int(plugin_selected) - 1
        plugin_selected_id = plugin_search_results[plugin_selected]["id"]
    except ValueError:
        rich_print_error("Error: Input wasn't a number! Please try again!")
        return None
    except IndexError:
        rich_print_error("Error: Number was out of range! Please try again!")
        return None
    selected_plugin_name = handle_regex_plugin_name(plugin_search_results[plugin_selected]["name"])
    rich_console.print(f"\n [not bold][bright_white]● [bright_magenta]{selected_plugin_name} [bright_green]latest")
    try:
        get_specific_plugin_spiget(plugin_selected_id)
    except Exception:
        pass