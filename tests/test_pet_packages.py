import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
PETS = {
    "koda": {
        "displayName": "Koda",
        "description": (
            "A calm, curious midnight-blue pixel cat who focuses deeply, helps eagerly, "
            "and stays slightly mischievous."
        ),
    },
    "wall-e": {
        "displayName": "WALL-E",
        "description": (
            "A gentle, touching faithful pixel-art WALL-E cleanup robot with weathered "
            "binocular eyes and heavy caterpillar tracks."
        ),
    },
}


def webp_dimensions(path: Path) -> tuple[int, int]:
    """Return canvas dimensions from a lossless VP8L WebP image."""

    payload = path.read_bytes()
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise ValueError("not a WebP RIFF file")

    position = 12
    while position + 8 <= len(payload):
        chunk_type = payload[position : position + 4]
        chunk_size = int.from_bytes(payload[position + 4 : position + 8], "little")
        chunk = payload[position + 8 : position + 8 + chunk_size]
        if chunk_type == b"VP8L":
            if len(chunk) < 5 or chunk[0] != 0x2F:
                raise ValueError("invalid VP8L image header")
            bits = int.from_bytes(chunk[1:5], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        position += 8 + chunk_size + (chunk_size & 1)

    raise ValueError("missing VP8L image chunk")


class PetPackageTests(unittest.TestCase):
    def test_catalog_pets_are_complete_v2_packages(self):
        for pet_id, expected in PETS.items():
            with self.subTest(pet_id=pet_id):
                package = ROOT / "pets" / pet_id
                manifest_path = package / "pet.json"
                spritesheet_path = package / "spritesheet.webp"

                self.assertTrue(manifest_path.is_file())
                self.assertTrue(spritesheet_path.is_file())
                self.assertEqual(
                    json.loads(manifest_path.read_text(encoding="utf-8")),
                    {
                        "id": pet_id,
                        **expected,
                        "spriteVersionNumber": 2,
                        "spritesheetPath": "spritesheet.webp",
                    },
                )
                self.assertEqual(webp_dimensions(spritesheet_path), (1536, 2288))

    def test_readme_exposes_direct_install_links_for_catalog_pets(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\((codex://pets/install\?[^)]+)\)", text)
        parsed_links = [parse_qs(urlparse(link).query) for link in links]

        for pet_id, expected in PETS.items():
            with self.subTest(pet_id=pet_id):
                expected_image_url = (
                    "https://raw.githubusercontent.com/contixly/codex-marketplace/"
                    f"main/pets/{pet_id}/spritesheet.webp"
                )
                self.assertIn(
                    {
                        "name": [expected["displayName"]],
                        "description": [expected["description"]],
                        "imageUrl": [expected_image_url],
                        "spriteVersionNumber": ["2"],
                    },
                    parsed_links,
                )


if __name__ == "__main__":
    unittest.main()
