"""
Handles the plugin checking and updating
"""

import os
import re
import io
from pathlib import Path
import zipfile
from typing import Tuple, Optional
from rich.progress import track
from rich.table import Table
from rich.console import Console
from urllib.error import HTTPError
from zipfile import ZipFile

from src.handlers.handle_config import config_value
from src.plugin.plugin_downloader import get_specific_plugin_spiget, get_download_path
from src.utils.console_output import rich_print_error
from src.utils.utilities import api_do_request
from src.platforms.github_handler import get_github_plugin_version, download_github_plugin, get_latest_github_release
from src.platforms.modrinth_handler import get_modrinth_plugin_version, download_modrinth_plugin, get_modrinth_project_from_plugin_hash, get_modrinth_versions


class Plugin():
    """
    Create plugin class to store installed plugins inside it
    """
    def __init__(
        self,
        plugin_file_name : str,
        plugin_name : str,
        plugin_file_version : str,
        plugin_latest_version : str,
        plugin_is_outdated : bool,
        plugin_repository : str,
        plugin_repository_data : list
        ) -> None:

        self.plugin_file_name = plugin_file_name
        self.plugin_name = plugin_name
        self.plugin_file_version = plugin_file_version
        self.plugin_latest_version = plugin_latest_version
        self.plugin_is_outdated = plugin_is_outdated
        self.plugin_repository = plugin_repository
        self.plugin_repository_data = plugin_repository_data


    @staticmethod
    def create_plugin_list() -> list:
        """
        Creates a global array list to store plugins
        """
        global INSTALLEDPLUGINLIST
        INSTALLEDPLUGINLIST = []
        return INSTALLEDPLUGINLIST


    @staticmethod
    def add_to_plugin_list(
        plugin_file_name: str,
        plugin_name : str,
        plugin_file_version : str,
        plugin_latest_version : str,
        plugin_is_outdated : bool,
        plugin_repository : str,
        plugin_repository_data : list
        ) -> None:
        """
        Adds a plugin to global installed plugin lists
        """
        INSTALLEDPLUGINLIST.append(Plugin(
            plugin_file_name, 
            plugin_name, 
            plugin_file_version, 
            plugin_latest_version, 
            plugin_is_outdated, 
            plugin_repository, 
            plugin_repository_data
            ))
        return None


def get_plugin_file_name(plugin_full_name: str) -> str:
    """
    Finds the full plugin name of the given string
    """
    plugin_full_name2 = plugin_full_name
    plugin_file_version = re.search(r'([\d.]+[.jar]+)', plugin_full_name2)
    try:
        plugin_file_version_full = plugin_file_version.group()
    except AttributeError:
        plugin_file_version_full = plugin_file_version
    plugin_name_only = plugin_full_name2.replace(plugin_file_version_full, '')
    plugin_name_only = re.sub(r'(\-$)', '', plugin_name_only)
    plugin_name_only = re.sub(r'(\-v$)', '', plugin_name_only)
    return plugin_name_only


def get_plugin_file_version(plugin_full_name: str) -> str:
    """
    Gets the version of the plugin
    """
    plugin_file_version = re.search(r'([\d.]+[.jar]+)', plugin_full_name)
    plugin_file_version = plugin_file_version.group()
    plugin_file_version = plugin_file_version.replace('.jar', '')
    if plugin_file_version.endswith('.'):
        plugin_file_name, plugin_file_version = egg_cracking_jar(plugin_full_name)
    return plugin_file_version


def get_plugin_name_version_from_strict_regex(plugin_full_name: str) -> str:
    """
    Finds the full plugin name and version with strict regex
    """
    plugin_full_name2 = plugin_full_name
    plugin_name_only = re.search(r'(^[\w]+)', plugin_full_name2)
    try:
        plugin_name_only = plugin_name_only.group()
    except AttributeError:
        plugin_name_only = plugin_name_only

    plugin_version = plugin_full_name2.replace(plugin_name_only, '')
    plugin_version = re.sub(r'^[\-]*', '', plugin_version)
    plugin_version = plugin_version.replace('.jar', '')
    return plugin_name_only, plugin_version


def get_latest_plugin_version_spiget(plugin_id: str) -> Tuple[str, Optional[str]]:
    """
    Gets the latest spigot plugin version and its hash if available
    """
    url = f"https://api.spiget.org/v2/resources/{plugin_id}/versions/latest"
    latest_update_search = api_do_request(url)
    if not latest_update_search:
        return "N/A", None
    
    version_name = str(latest_update_search.get("name", "N/A"))
    # Spiget sometimes provides a hash in the metadata for some resources
    latest_hash = latest_update_search.get("hash") 
    return version_name, latest_hash


def create_plugin_version_tuple(plugin_version_string : str) -> tuple:
    """
    Create a tuple of all version numbers
    """
    return tuple(map(int, (plugin_version_string.split("."))))


def get_plugin_version_without_letters(plugin_version_string : str) -> str:
    """
    Returns the version without letters
    """
    return re.sub(r'([A-Za-z]*)', '', plugin_version_string)


def compare_plugin_version(plugin_latest_version : str, plugin_file_version : str) -> bool:
    """
    Check if plugin version is outdated
    """
    try:
        plugin_version_tuple = create_plugin_version_tuple(
            get_plugin_version_without_letters(plugin_file_version))
        plugin_latest_version_tuple = create_plugin_version_tuple(
            get_plugin_version_without_letters(plugin_latest_version))
    except ValueError:
        raise Exception("Versions can't be matched!")
    return plugin_version_tuple < plugin_latest_version_tuple


def ask_update_confirmation(input_selected_object : str) -> bool:
    """
    Asks for confirmation before updating
    """
    rich_console = Console()
    rich_console.print("Selected plugins with available Updates:")
    for plugin_file in INSTALLEDPLUGINLIST:
        if not plugin_file.plugin_is_outdated:
            continue
        if input_selected_object != "all" and input_selected_object != "*":
            if re.search(re.escape(input_selected_object), plugin_file.plugin_file_name, re.IGNORECASE):
                rich_console.print(f"[not bold][bright_magenta]{plugin_file.plugin_name}", end=' ')
                break
        rich_console.print(f"[not bold][bright_magenta]{plugin_file.plugin_name}", end=' ')

    rich_console.print()
    update_confirmation = input("Update these plugins [y/n] ? ")
    if str.lower(update_confirmation) != "y":
        rich_print_error("Aborting the update process")
        return False
    return True


def egg_cracking_jar(plugin_file_name: str) -> str:
    """
    Opens the plugin file as an archive to find name and version
    """
    config_values = config_value()
    path_plugin_folder = config_values.path_to_plugin_folder
    path_plugin_jar = Path(f"{path_plugin_folder}/{plugin_file_name}")

    plugin_name = plugin_version = ""
    try:
        with ZipFile(path_plugin_jar, "r") as plugin_jar:
            with io.TextIOWrapper(plugin_jar.open("plugin.yml", "r"), encoding="utf-8") as plugin_yml:
                for line in plugin_yml:
                    if plugin_name != "" and plugin_version != "":
                        break
                    if re.match(r"^\s*?name: ", line):
                        plugin_name = re.sub(r'^\s*?name: ', '', line).replace("\n", "").replace("'", "").replace('"', "")
                    if re.match(r"^\s*?version: ", line):
                        plugin_version = re.sub(r'^\s*?version: ', "", line).replace("\n", "").replace("'", "").replace('"', "")
    except Exception:
        plugin_name = plugin_version = ""
    return plugin_name, plugin_version


def check_update_available_installed_plugins(input_selected_object: str, config_values: config_value) -> str:
    """
    Checks for available updates across all platforms
    """
    Plugin.create_plugin_list()
    plugin_folder_path = config_values.path_to_plugin_folder
    plugin_list = os.listdir(plugin_folder_path)

    plugin_count = plugins_with_udpates = 0
    for plugin_file in track(plugin_list, description="[cyan]Checking...", transient=True, style="bright_yellow"):
        if not os.path.isfile(Path(f"{plugin_folder_path}/{plugin_file}")) or not re.search(r'\.jar$', plugin_file):
            continue

        plugin_file_name = get_plugin_file_name(plugin_file)
        if input_selected_object != "all" and input_selected_object != "*":
            if not re.search(re.escape(input_selected_object), plugin_file_name, re.IGNORECASE):
                continue

        plugin_file_version = get_plugin_file_version(plugin_file)
        plugin_spigot_id = search_plugin_spiget(plugin_file, plugin_file_name, plugin_file_version)
        
        if plugin_spigot_id is None:
            try:
                if plugin_file not in [p.plugin_file_name for p in INSTALLEDPLUGINLIST]:
                    search_plugin_modrinth(plugin_file, plugin_file_name, plugin_file_version)
                    if plugin_file not in [p.plugin_file_name for p in INSTALLEDPLUGINLIST]:
                        search_plugin_github(plugin_file, plugin_file_name, plugin_file_version)
            except (IndexError, AttributeError):
                pass

        try:
            if plugin_file not in [p.plugin_file_name for p in INSTALLEDPLUGINLIST]:
                Plugin.add_to_plugin_list(plugin_file, plugin_file_name, plugin_file_version, 'N/A', False, 'N/A', ())
        except (IndexError, AttributeError):
            pass

        if INSTALLEDPLUGINLIST and INSTALLEDPLUGINLIST[-1].plugin_is_outdated:
            plugins_with_udpates += 1
        plugin_count += 1
    return plugin_count, plugins_with_udpates


def check_installed_plugins(input_selected_object : str="all", input_parameter : str=None) -> None:
    """
    Prints table overview of installed plugins
    """
    config_values = config_value()
    plugin_count, plugins_with_udpates = check_update_available_installed_plugins(input_selected_object, config_values)

    rich_table = Table(box=None)
    rich_table.add_column("No.", justify="right", style="cyan", no_wrap=True)
    rich_table.add_column("Name", style="bright_magenta")
    rich_table.add_column("Installed V.", justify="right", style="green")
    rich_table.add_column("Latest V.", justify="right", style="bright_green")
    rich_table.add_column("Update available", justify="left", style="white")
    rich_table.add_column("Repository", justify="left", style="white")
    
    for i, plugin in enumerate(INSTALLEDPLUGINLIST, 1):
        rich_table.add_row(
            str(i), plugin.plugin_name, plugin.plugin_file_version, 
            plugin.plugin_latest_version, str(plugin.plugin_is_outdated), plugin.plugin_repository
        )

    rich_console = Console()
    rich_console.print(rich_table)
    rich_console.print()
    if plugins_with_udpates != 0:
        rich_console.print(f"[not bold][bright_yellow]Plugins with available updates: [bright_green]{plugins_with_udpates}[bright_yellow]/[green]{plugin_count}")
        rich_console.print(f"[not bold][white]Use '[cyan]update all[white]' to update [green]{plugins_with_udpates} [white]plugins!")
    else:
        rich_console.print(f"[bright_green]All found plugins are on the newest version!")


def update_installed_plugins(input_selected_object : str="all", no_confirmation : bool=False) -> None:
    """
    Updates outdated plugins with hash verification
    """
    rich_console = Console()
    config_values = config_value()

    try:
        if not INSTALLEDPLUGINLIST:
            check_update_available_installed_plugins(input_selected_object, config_values)
    except NameError:
        check_update_available_installed_plugins(input_selected_object, config_values)

    if input_selected_object in ["all", "*"]:
        check_update_available_installed_plugins(input_selected_object, config_values)

    if not no_confirmation and not ask_update_confirmation(input_selected_object):
        return

    plugins_updated = plugins_skipped = 0
    for plugin in INSTALLEDPLUGINLIST:
        if input_selected_object not in ["all", "*"] and not re.search(re.escape(input_selected_object), plugin.plugin_file_name, re.IGNORECASE):
            plugins_skipped += 1
            continue

        if not plugin.plugin_is_outdated:
            plugins_skipped += 1
            continue

        rich_console.print(f"\n [not bold][bright_white]● [bright_magenta]{plugin.plugin_name} [green]{plugin.plugin_file_version} [cyan]→ [bright_green]{plugin.plugin_latest_version}")
        plugins_updated += 1
        plugin_path = get_download_path(config_values)

        try:
            match plugin.plugin_repository:
                case "spigot":
                    # Pass the captured hash to the downloader
                    expected_hash = plugin.plugin_repository_data[1] if len(plugin.plugin_repository_data) > 1 else None
                    get_specific_plugin_spiget(plugin.plugin_repository_data[0], expected_hash=expected_hash)
                case "github":
                    # Pass expected hash for verification
                    expected_hash = plugin.plugin_repository_data[1] if len(plugin.plugin_repository_data) > 1 else None
                    download_github_plugin(plugin.plugin_repository_data[0], plugin.plugin_name, expected_hash=expected_hash)
                case "modrinth":
                    # Modrinth provides SHA-512 hashes natively
                    project_id = plugin.plugin_repository_data[0]
                    featured_only = plugin.plugin_repository_data[1] if len(plugin.plugin_repository_data) > 1 else True
                    expected_hash = plugin.plugin_repository_data[2] if len(plugin.plugin_repository_data) > 2 else None
                    download_modrinth_plugin(project_id, featured_only, expected_hash=expected_hash)
                case _:
                    rich_print_error(f"Error: Plugin repository '{plugin.plugin_repository}' wasn't recognized")
                    plugins_updated -= 1
                    continue
        except Exception as err:
            rich_print_error(f"Update Error: {err}")
            plugins_updated -= 1
            continue

        if not config_values.local_seperate_download_path:
            try:
                os.remove(Path(f"{plugin_path}/{plugin.plugin_file_name}"))
                rich_console.print(f"    [not bold][bright_green]Deleted old plugin file [cyan]→ [white]{plugin.plugin_file_name}")
            except Exception:
                rich_print_error("Error: Old plugin file couldn't be deleted")

    rich_console.print(f"\n[not bold][bright_green]Plugins updated: {plugins_updated}/{(len(INSTALLEDPLUGINLIST) - plugins_skipped)}")


def search_plugin_spiget(plugin_file: str, plugin_file_name: str, plugin_file_version: str) -> int:
    """
    Search Spiget and capture metadata
    """
    url = f"https://api.spiget.org/v2/search/resources/{plugin_file_name}?field=name&sort=-downloads"
    plugin_list = api_do_request(url)
    if not plugin_list or "error" in plugin_list:
        return None

    plugin_file_version2 = plugin_file_version
    for i in range(5):
        if i == 1: plugin_file_version2 = re.sub(r'(\-\w*)', '', plugin_file_version)
        if i == 2:
            plugin_name_in_yml, _ = egg_cracking_jar(plugin_file)
            url = f"https://api.spiget.org/v2/search/resources/{plugin_name_in_yml}?field=name&sort=-downloads"
            plugin_list = api_do_request(url)
        if i == 4:
            plugin_name_from_regex, plugin_file_version2 = get_plugin_name_version_from_strict_regex(plugin_file)
            url = f"https://api.spiget.org/v2/search/resources/{plugin_name_from_regex}?field=name&sort=-downloads"
            plugin_list = api_do_request(url)

        if not plugin_list: continue

        for plugin_res in plugin_list:
            plugin_id = plugin_res["id"]
            url2 = f"https://api.spiget.org/v2/resources/{plugin_id}/versions?size=100&sort=+name"
            plugin_versions = api_do_request(url2)
            if not plugin_versions: continue

            for k, updates in enumerate(plugin_versions, 1):
                if plugin_file_version2 in updates["name"]:
                    # Capture the latest version name and potential hash
                    plugin_latest_version, latest_hash = get_latest_plugin_version_spiget(plugin_id)
                    plugin_is_outdated = False
                    try:
                        plugin_is_outdated = compare_plugin_version(plugin_latest_version, updates["name"])
                    except Exception:
                        if not plugin_is_outdated and 1 < k < 100:
                            plugin_is_outdated = True

                    Plugin.add_to_plugin_list(
                        plugin_file, plugin_file_name, plugin_file_version, 
                        plugin_latest_version, plugin_is_outdated, "spigot", [plugin_id, latest_hash]
                    )
                    return plugin_id
    return None


def search_plugin_modrinth(plugin_file: str, plugin_file_name: str, plugin_file_version: str) -> str:
    """
    Search Modrinth and capture SHA-512 hashes for verification
    """
    config_values = config_value()
    plugin_path = Path(f"{config_values.path_to_plugin_folder}/{plugin_file}")
    project_id = get_modrinth_project_from_plugin_hash(str(plugin_path))

    if project_id:
        try:
            # Fetch version metadata to get the official hash
            versions = get_modrinth_versions(project_id, featured_only=True)
            if versions:
                latest_version_obj = versions[0]
                plugin_latest_version = latest_version_obj.get("version_number", "")
                
                # Extract SHA-512 hash
                latest_hash = None
                files = latest_version_obj.get("files", [])
                for f in files:
                    if f.get("primary", False):
                        latest_hash = f.get("hashes", {}).get("sha512")
                        break
                if not latest_hash and files:
                    latest_hash = files[0].get("hashes", {}).get("sha512")

                plugin_is_outdated = False
                try:
                    plugin_is_outdated = compare_plugin_version(plugin_latest_version, plugin_file_version)
                except Exception:
                    if plugin_latest_version != plugin_file_version:
                        plugin_is_outdated = True

                Plugin.add_to_plugin_list(
                    plugin_file, plugin_file_name, plugin_file_version, 
                    plugin_latest_version, plugin_is_outdated, "modrinth", [project_id, True, latest_hash]
                )
                return project_id
        except Exception:
            pass
    return None


def search_plugin_github(plugin_file: str, plugin_file_name: str, plugin_file_version: str) -> str:
    """
    Search GitHub and capture release metadata
    """
    url = f"https://api.github.com/search/repositories?q={plugin_file_name}+language:java+spigot&sort=stars&order=desc"
    search_results = api_do_request(url)
    if not search_results or search_results.get("total_count", 0) == 0:
        return None
    
    for repo in search_results.get("items", [])[:5]:
        if plugin_file_name.lower() in repo["name"].lower() or repo["name"].lower() in plugin_file_name.lower():
            try:
                # Capture release data to potentially find hashes
                release_data = get_latest_github_release(repo["full_name"])
                if release_data:
                    plugin_latest_version = release_data.get("tag_name", "").replace('v', '')
                    # Future: GitHub lacks standard hashes; search for .sha256 assets here
                    latest_hash = None 
                    
                    plugin_is_outdated = False
                    try:
                        plugin_is_outdated = compare_plugin_version(plugin_latest_version, plugin_file_version)
                    except Exception:
                        if plugin_latest_version != plugin_file_version:
                            plugin_is_outdated = True
                    
                    Plugin.add_to_plugin_list(
                        plugin_file, plugin_file_name, plugin_file_version, 
                        plugin_latest_version, plugin_is_outdated, "github", [repo["full_name"], latest_hash]
                    )
                    return repo["full_name"]
            except Exception:
                continue
    return None