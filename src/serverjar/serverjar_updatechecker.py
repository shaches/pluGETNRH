"""
Checks the installed serverjar for updates
"""

import os
from pathlib import Path
from rich.console import Console

from src.handlers.handle_config import config_value
from src.utils.console_output import rich_print_error
from src.serverjar.serverjar_paper_velocity_waterfall import serverjar_papermc_check_update, serverjar_papermc_update
from src.serverjar.serverjar_purpur import serverjar_purpur_check_update, serverjar_purpur_update


def get_installed_server_jar_file(config_values) -> str:
    """
    Gets the file name of the installed server jar

    :param config_values: Configuration values from pluGET config

    :returns: Full file name of installed server jar
    """
    file_list_server_root = os.path.dirname(config_values.path_to_plugin_folder)
    file_list_server_root = os.listdir(file_list_server_root)

    file_server_jar_full_name = None
    try:
        for file in file_list_server_root:
            try:
                if ".jar" in file:
                    file_server_jar_full_name = file
                    break
            except TypeError:
                continue
    except TypeError:
        rich_print_error("Error: Serverjar couldn't be found")
        return None
    return file_server_jar_full_name


def check_update_available_installed_server_jar() -> None:
    """
    Handles the checking of available updates of the installed server jar

    :returns: None
    """
    config_values = config_value()
    file_server_jar_full_name = get_installed_server_jar_file(config_values)
    if file_server_jar_full_name is None:
        # print error and exit function
        rich_print_error("Error: Serverjar couldn't be found")
        return None

    # TODO: Add other serverjars here
    # Paper / Velocity / Waterfall
    if "paper" in file_server_jar_full_name or \
        "waterfall" in file_server_jar_full_name or \
        "velocity" in file_server_jar_full_name:
        serverjar_papermc_check_update(file_server_jar_full_name)

    # Purpur
    elif "purpur" in file_server_jar_full_name:
        serverjar_purpur_check_update(file_server_jar_full_name)

    else:
        rich_print_error(f"[not bold]Error: [bright_magenta]{file_server_jar_full_name} [bright_red]isn't supported")

    return None


def update_installed_server_jar(server_jar_version: str="latest") -> None:
    """
    Handles the updating of the installed server jar

    :returns: None
    """
    config_values = config_value()
    file_server_jar_full_name = get_installed_server_jar_file(config_values)
    if file_server_jar_full_name is None:
        # print error and exit function
        rich_print_error("Error: Serverjar couldn't be found")
        return None

    # finding path which is used for deleting old server jar
    path_server_root = config_values.path_to_plugin_folder
    # need help_path or else TypeError will be thrown
    help_path = Path('/plugins')
    help_path_str = str(help_path)
    path_server_root = Path(str(path_server_root).replace(help_path_str, ''))

    server_jar_path = f"{path_server_root}/{file_server_jar_full_name}"
    rich_console = Console()
    download_successful = False
    # TODO: Add other serverjars here
    # Paper / Velocity / Waterfall
    if "paper" in file_server_jar_full_name or \
        "waterfall" in file_server_jar_full_name or \
        "velocity" in file_server_jar_full_name:
        download_successful = serverjar_papermc_update(server_jar_version, None, file_server_jar_full_name, None)

    # Purpur
    elif "purpur" in file_server_jar_full_name:
        download_successful = serverjar_purpur_update(server_jar_version, None, file_server_jar_full_name)

    else:
        rich_print_error(f"[not bold]Error: [bright_magenta]{file_server_jar_full_name} [bright_red]isn't supported")

    # remove old serverjar when the serverjar was successfully updated
    if download_successful is True:
        os.remove(Path(server_jar_path))
        rich_console.print(
            "    [not bold][bright_green]Deleted old server file [cyan]→ [white]" +
            f"{file_server_jar_full_name}"
        )

    return None
