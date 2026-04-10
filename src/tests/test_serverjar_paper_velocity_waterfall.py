import unittest

from src.serverjar import serverjar_paper_velocity_waterfall

class TestCases(unittest.TestCase):
    def test_get_installed_serverjar_version(self):
        # paper-1.19-40.jar -> 40
        serverjar_file_name = "paper-1.19-40.jar"
        serverjar_version = "40"
        result = serverjar_paper_velocity_waterfall.get_installed_serverjar_version(serverjar_file_name)
        self.assertEqual(result, serverjar_version)


    def test_get_version_group(self):
        # 1.18.2 -> 1.18
        mc_version = "1.18.2"
        mc_version_group = "1.18.2"
        result = serverjar_paper_velocity_waterfall.get_version_group(mc_version)
        self.assertEqual(result, mc_version_group)


    def test_find_latest_available_version(self):
        # Get latest available paper version for 1.15.2 which should be 393
        file_server_jar_full_name = "paper-1.15.2-40.jar"
        version_group = "1.15.2"
        result = serverjar_paper_velocity_waterfall.find_latest_available_version(
            file_server_jar_full_name,
            version_group
        )
        self.assertEqual(result, 393)


    def test_get_versions_behind(self):
        # 161 - 157 = 4
        serverjar_version = 157
        latest_version = 161
        result = serverjar_paper_velocity_waterfall.get_versions_behind(serverjar_version, latest_version)
        self.assertEqual(result, 4)


    def test_get_papermc_download_file_name(self):
        # Verifies that the API returns the correct filename and a sha256 hash
        mc_version = "1.15.2"
        serverjar_version = "393"
        file_server_jar_full_name = "paper-1.15.2-40.jar"
        download_name, expected_hash = serverjar_paper_velocity_waterfall.get_papermc_download_file_name(
            mc_version, serverjar_version, file_server_jar_full_name
        )
        self.assertEqual(download_name, "paper-1.15.2-393.jar")
        self.assertIsNotNone(expected_hash)


if __name__ == "__main__":
    unittest.main()