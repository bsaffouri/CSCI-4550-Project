import unittest

from src.packet import PacketError, decode_packet, encode_packet


def valid_packet(**overrides):
    packet = {
        "src": "H1",
        "dst": "H2",
        "hop_limit": 8,
        "type": "PROBE",
        "msg_id": 17,
        "payload": "hello",
    }
    packet.update(overrides)
    return packet


class PacketTests(unittest.TestCase):
    def test_round_trip(self):
        packet = valid_packet()
        self.assertEqual(decode_packet(encode_packet(packet)), packet)

    def test_garbage_bytes(self):
        with self.assertRaises(PacketError):
            decode_packet(b"not json")

    def test_missing_field(self):
        packet = valid_packet()
        del packet["payload"]
        with self.assertRaisesRegex(PacketError, "payload"):
            encode_packet(packet)

    def test_wrong_field_type(self):
        with self.assertRaisesRegex(PacketError, "hop_limit"):
            encode_packet(valid_packet(hop_limit=True))

    def test_unknown_message_type(self):
        with self.assertRaisesRegex(PacketError, "unknown packet type"):
            encode_packet(valid_packet(type="DATA"))

    def test_packet_too_large(self):
        with self.assertRaisesRegex(PacketError, "maximum is 1200"):
            encode_packet(valid_packet(payload="x" * 1200))

    def test_empty_bytes(self):
        with self.assertRaisesRegex(PacketError, "empty"):
            decode_packet(b"")

    def test_decoded_non_object(self):
        with self.assertRaisesRegex(PacketError, "JSON object"):
            decode_packet(b"[]")

    def test_extra_field(self):
        with self.assertRaisesRegex(PacketError, "unknown field"):
            encode_packet(valid_packet(extra="not allowed"))


if __name__ == "__main__":
    unittest.main()
