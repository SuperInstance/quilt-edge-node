"""Tests for quilt_node_identity."""
import unittest

from src.quilt_node_identity import (
    bond,
    derive_network_salt,
    derive_node_id,
    read_board_serial,
    short_id,
)


class TestNetworkSalt(unittest.TestCase):
    def test_deterministic(self):
        s1 = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff", joined_at_unix=1700000000.0)
        s2 = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff", joined_at_unix=1700000000.0)
        self.assertEqual(s1, s2)

    def test_different_ssid(self):
        s1 = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff")
        s2 = derive_network_salt("home-lan", "aa:bb:cc:dd:ee:ff")
        self.assertNotEqual(s1, s2)

    def test_different_bssid(self):
        s1 = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff")
        s2 = derive_network_salt("boat-lan", "11:22:33:44:55:66")
        self.assertNotEqual(s1, s2)


class TestNodeId(unittest.TestCase):
    def test_deterministic(self):
        salt = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff", joined_at_unix=1700000000.0)
        n1 = derive_node_id(salt, "ABX00173-serial-001")
        n2 = derive_node_id(salt, "ABX00173-serial-001")
        self.assertEqual(n1, n2)

    def test_different_serial(self):
        salt = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff")
        n1 = derive_node_id(salt, "serial-001")
        n2 = derive_node_id(salt, "serial-002")
        self.assertNotEqual(n1, n2)

    def test_different_salt(self):
        s1 = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff")
        s2 = derive_network_salt("home-lan", "aa:bb:cc:dd:ee:ff")
        n1 = derive_node_id(s1, "serial-001")
        n2 = derive_node_id(s2, "serial-001")
        self.assertNotEqual(n1, n2)

    def test_id_is_64_hex(self):
        salt = derive_network_salt("boat-lan", "aa:bb:cc:dd:ee:ff")
        nid = derive_node_id(salt, "serial-001")
        self.assertEqual(len(nid), 64)
        int(nid, 16)  # should parse as hex


class TestShortId(unittest.TestCase):
    def test_default_length(self):
        nid = "f22021af788cfabd905f121854cbce4323f38ebaa96ce9718229f40b35a884d4"
        self.assertEqual(short_id(nid), "f22021af")

    def test_custom_length(self):
        nid = "f22021af788cfabd905f121854cbce4323f38ebaa96ce9718229f40b35a884d4"
        self.assertEqual(short_id(nid, n=4), "f220")
        self.assertEqual(short_id(nid, n=16), "f22021af788cfabd")


class TestBond(unittest.TestCase):
    def test_bond_returns_record(self):
        ts = 1700000000.0
        r = bond("serial-001", "boat-lan", "aa:bb:cc:dd:ee:ff", joined_at_unix=ts)
        self.assertEqual(r.network_ssid, "boat-lan")
        self.assertEqual(r.board_serial, "serial-001")
        self.assertEqual(len(r.network_salt), 64)
        self.assertEqual(len(r.node_id), 64)
        # The first_seen_unix is "now" (when bonded); the *salt* is
        # content-addressed from the joined_at_unix passed in.
        self.assertGreater(r.first_seen_unix, 0)


class TestReadBoardSerial(unittest.TestCase):
    def test_returns_nonempty(self):
        serial = read_board_serial()
        self.assertTrue(serial)
        self.assertIsInstance(serial, str)


if __name__ == "__main__":
    unittest.main()
