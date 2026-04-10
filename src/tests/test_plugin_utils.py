import unittest

from src.plugin import plugin_downloader
from src.utils import utilities


class TestCases(unittest.TestCase):
    def test_handle_regex_plugin_name(self):
        # Cropped name -> 'SUPERBPlugin'
        plugin_name = "[1.13-5.49 ❤] >|> SUPERB Plugin <<💥| Now 150% OFF IN WINTER SALE IN SUMMER???"
        plugin_name_cropped = "SUPERBPlugin"
        result = plugin_downloader.handle_regex_plugin_name(plugin_name)
        self.assertEqual(result, plugin_name_cropped)


    def test_get_version_id_spiget(self):
        # 28140 -> "Luckperms" in Version 5.4.30
        result = plugin_downloader.get_version_id_spiget("28140", "5.4.30")
        self.assertEqual(result, 455966)


    def test_get_version_name_spiget(self):
        # 455966 -> "5.4.30" from Luckperms
        result = plugin_downloader.get_version_name_spiget("28140", 455966)
        self.assertEqual(result, "5.4.30")


    def test_get_download_path(self):
        # local plugin folder
        class config_values_local:
            connection = "local"
            local_seperate_download_path = True
            local_path_to_seperate_download_path = "/local/path/plugins"
        result = plugin_downloader.get_download_path(config_values_local)
        self.assertEqual(result, config_values_local.local_path_to_seperate_download_path)

        # local plugin folder without separate download path
        class config_values_no_separate:
            connection = "local"
            local_seperate_download_path = False
            local_path_to_seperate_download_path = "/local/separate/path"
            path_to_plugin_folder = "/local/path/plugins"
        result = plugin_downloader.get_download_path(config_values_no_separate)
        self.assertEqual(result, config_values_no_separate.path_to_plugin_folder)


    def test_convert_file_size_down(self):
        # 100000 / 1024 = 97.66
        result = utilities.convert_file_size_down(100000)
        self.assertEqual(result, 97.66)


if __name__ == "__main__":
    unittest.main()
