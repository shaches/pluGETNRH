import sys
import os
import hashlib
import base64
from pathlib import Path
import pysftp
import paramiko
import stat
import re

from src.utils.console_output import rich_print_error, rich_print_warning
from src.handlers.handle_config import config_value


def _get_host_key_fingerprint(key: paramiko.PKey) -> str:
    """
    Returns a SHA256 fingerprint of a host key in standard Base64 format,
    matching the output of 'ssh-keygen -l'.

    :param key: Paramiko public key object

    :returns: Fingerprint string in 'SHA256:<base64>' format
    """
    key_bytes = key.asbytes()
    digest = hashlib.sha256(key_bytes).digest()
    b64_fingerprint = base64.b64encode(digest).rstrip(b'=').decode('ascii')
    return f"SHA256:{b64_fingerprint}"


def _fetch_host_key(server: str, port: int) -> paramiko.PKey:
    """
    Connects to the SSH server to retrieve its host key without authenticating.

    :param server: Hostname or IP of the SFTP server
    :param port: SSH port

    :returns: The server's host key or None if retrieval failed
    """
    transport = None
    try:
        transport = paramiko.Transport((server, port))
        transport.connect()
        host_key = transport.get_remote_server_key()
        return host_key
    except Exception:
        return None
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass


def _save_host_key(known_hosts_path: Path, server: str, key: paramiko.PKey) -> None:
    """
    Saves a host key to the known_hosts file, creating the file and parent
    directories if they don't exist.

    :param known_hosts_path: Path to the known_hosts file
    :param server: Hostname or IP to associate with the key
    :param key: Paramiko public key to save
    """
    known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
    host_keys = paramiko.HostKeys()
    if known_hosts_path.exists():
        try:
            host_keys.load(str(known_hosts_path))
        except Exception:
            pass
    host_keys.add(server, key.get_name(), key)
    host_keys.save(str(known_hosts_path))


def sftp_create_connection():
    """
    Creates a sftp connection with the given values in the config file.
    Uses Trust On First Use (TOFU) for host key verification:
    - If the server's key is in known_hosts, it is verified automatically.
    - If not, the key fingerprint is shown and the user must confirm before proceeding.
    - Accepted keys are saved to known_hosts for future verification.

    :returns: SFTP connection type
    """
    config_values = config_value()
    known_hosts_path = Path.home() / ".ssh" / "known_hosts"
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None

    # Try to load existing known_hosts for verification
    host_key_verified = False
    try:
        loaded_cnopts = pysftp.CnOpts(knownhosts=str(known_hosts_path))
        # Check if the target server has a key in the loaded file
        if loaded_cnopts.hostkeys.lookup(config_values.server) is not None:
            cnopts = loaded_cnopts
            host_key_verified = True
    except pysftp.HostKeysException:
        pass

    if not host_key_verified:
        # TOFU: fetch the server's host key and ask the user to verify
        rich_print_warning(
            f"Warning: [SFTP]: Host key for '{config_values.server}' not found in known_hosts."
        )
        host_key = _fetch_host_key(config_values.server, config_values.sftp_port)
        if host_key is None:
            rich_print_error("Error: [SFTP]: Could not retrieve host key from server.")
            rich_print_error("Exiting program...")
            sys.exit()

        fingerprint = _get_host_key_fingerprint(host_key)
        rich_print_warning(
            f"         Server key fingerprint: {fingerprint}"
        )
        rich_print_warning(
            f"         Key type: {host_key.get_name()}"
        )
        try:
            answer = input("Do you want to trust this host key and continue connecting? [y/n] ")
        except (KeyboardInterrupt, EOFError):
            print()
            rich_print_error("Error: [SFTP]: Connection aborted by user.")
            sys.exit()

        if answer.strip().lower() != "y":
            rich_print_error("Error: [SFTP]: Host key rejected. Connection aborted.")
            sys.exit()

        # Save the accepted key to known_hosts
        try:
            _save_host_key(known_hosts_path, config_values.server, host_key)
            rich_print_warning(
                f"         Host key saved to: {known_hosts_path}"
            )
        except OSError as e:
            rich_print_warning(
                f"Warning: [SFTP]: Could not save host key: {e}"
            )

        # Reload cnopts with the newly saved key
        try:
            cnopts = pysftp.CnOpts(knownhosts=str(known_hosts_path))
        except pysftp.HostKeysException:
            rich_print_warning(
                "Warning: [SFTP]: Could not reload known_hosts after saving. "
                "Proceeding with unverified connection."
            )
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None

    try:
        sftp = pysftp.Connection(config_values.server, username=config_values.username, \
               password=config_values.password, port=config_values.sftp_port, cnopts=cnopts)
    except paramiko.ssh_exception.AuthenticationException:
        rich_print_error("Error: [SFTP]: Wrong Username/Password")
    except paramiko.ssh_exception.SSHException:
        rich_print_error("Error: [SFTP]: The SFTP server isn't available.")
    try:
        return sftp
    except UnboundLocalError:
        rich_print_error("Error: [SFTP]: Check your config file!")
        rich_print_error("Exiting program...")
        sys.exit()


def sftp_show_plugins(sftp) -> None:
    """
    Prints all plugins in the sftp folder

    :param sftp: sftp connection

    :returns: None
    """
    config_values = config_value()
    sftp.cd(config_values.remote_plugin_folder_on_server)
    for attr in sftp.listdir_attr():
        print(attr.filename, attr)
    sftp.close()
    return None


def sftp_upload_file(sftp, path_item) -> None:
    """
    Uploads a file to the set folder from the config file

    :param sftp: sftp connection
    :param path_item: The upload path with the item name

    :returns: None
    """
    config_values = config_value()
    if config_values.remote_seperate_download_path is True:
        path_upload_folder = config_values.remote_path_to_seperate_download_path
    else:
        path_upload_folder = config_values.remote_plugin_folder_on_server
    try:
        sftp.chdir(path_upload_folder)
        sftp.put(path_item)
    except FileNotFoundError:
        rich_print_error(f"Error: [SFTP]: The '{path_upload_folder}' folder couldn't be found on the remote host!")
        try:
            sftp.makedirs(path_upload_folder)
            rich_print_warning(f"Warning: [SFTP]: Created '{path_upload_folder}' for you.")
            sftp.chdir(path_upload_folder)
            sftp.put(path_item)
        except Exception:
            rich_print_error(
                f"Error: [SFTP]: The '{path_upload_folder}' folder couldn't be created or the upload failed!"
            )
            rich_print_error("Error: [SFTP]: Aborting uploading.")

    sftp.close()
    return None


def sftp_upload_server_jar(sftp, path_item) -> None:
    """
    Uploads the server jar to the root folder

    :param sftp: sftp connection
    :param path_item: The upload path with the item name

    :returns: None
    """
    try:
        sftp.chdir('.')
        sftp.put(path_item)
    except FileNotFoundError:
        rich_print_error("Error: [SFTP]: The 'root' folder couldn't be found on the remote host!")
        rich_print_error("Error: [SFTP]: Aborting uploading.")
    sftp.close()
    return None


def sftp_list_all(sftp):
    """
    List all plugins in the 'plugins' folder on the sftp host

    :param sftp: sftp connection

    :return: List of plugins in plugin folder
    """
    config_values = config_value()
    try:
        sftp.chdir(config_values.remote_plugin_folder_on_server)
        installed_plugins = sftp.listdir()
    except FileNotFoundError:
        rich_print_error("Error: [SFTP]: The 'plugins' folder couldn't be found on the remote host!")

    try:
        return installed_plugins
    except UnboundLocalError:
        rich_print_error("Error: [SFTP]: No plugins were found.")


def sftp_list_files_in_server_root(sftp):
    """
    List all files in the root folder on the sftp host

    :param sftp: sftp connection

    :returns: List of files in root folder
    """
    try:
        files_in_server_root = sftp.listdir()
    except FileNotFoundError:
        rich_print_error("Error: [SFTP]: The 'root' folder couldn't be found on the remote host!")
    try:
        return files_in_server_root
    except UnboundLocalError:
        rich_print_error("Error: [SFTP]: No Serverjar was found.")


def sftp_download_file(sftp, file) -> None:
    """
    Downloads a plugin file from the sftp host to a temporary folder

    :param sftp: sftp connection
    :param file: Filename of plugin

    :returns: None
    """
    config_values = config_value()
    sftp.cwd(config_values.remote_plugin_folder_on_server)
    local_path = os.path.abspath(os.path.join('TempSFTPFolder', file))
    sftp.get(file, localpath=local_path)
    sftp.close()
    return None


def sftp_validate_file_attributes(sftp, plugin_path) -> bool:
    """
    Check if the file is a legitimate plugin file

    :param sftp: sftp connection
    param plugin_path: Path of the single plugin file

    :returns: If file is a plugin file or not 
    """
    plugin_sftp_attribute = sftp.lstat(plugin_path)
    if stat.S_ISDIR(plugin_sftp_attribute.st_mode):
        return False
    elif re.search(r'\.jar$', plugin_path):
        return True
    else:
        return False
