"""Validate publication readiness with isolated input files, never live entries."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import validate_gallery_publish as validator


class PublicationContractTests(unittest.TestCase):
    def validate(self, entries, assets):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = {"entries": entries}
            html = ('<script>const EMBEDDED_INDEX={};\nconst EMBEDDED_REGISTRY='+
                    json.dumps(registry)+';\nconst EMBEDDED_ASSETS='+json.dumps(assets)+';\nlet idx=null;</script>')
            (root/'index.html').write_text(html,encoding='utf-8')
            (root/'gallery.json').write_text(json.dumps(registry),encoding='utf-8')
            old = validator.INDEX,validator.GALLERY
            validator.INDEX,validator.GALLERY = root/'index.html',root/'gallery.json'
            try:
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    validator.main()
            finally:
                validator.INDEX,validator.GALLERY = old

    def test_class_ready_does_not_require_invented_assets(self):
        self.validate([{"class_id":"test.pending","status":"CLASS_READY"}],{})

    def test_ready_requires_manifest_and_assets(self):
        for status in ("READY","PRODUCTION_READY","PUBLISHED_PUBLIC"):
            with self.subTest(status=status),self.assertRaises(SystemExit):
                self.validate([{"class_id":"test.ready","status":status}],{})

    def test_declared_manifest_must_be_embedded(self):
        with self.assertRaises(SystemExit):
            self.validate([{"class_id":"test.pending","status":"CLASS_READY","asset_manifest":"test.json"}],{})

    def test_unregistered_manifest_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.validate([],{"test.orphan":{"class_id":"test.orphan","assets":[]}})

    def test_ready_empty_assets_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.validate([{"class_id":"test.ready","status":"PRODUCTION_READY","asset_manifest":"test.json"}],
                          {"test.ready":{"class_id":"test.ready","assets":[]}})

    def test_ready_real_asset_payload_is_accepted(self):
        self.validate([{"class_id":"test.ready","status":"PUBLISHED_PUBLIC","asset_manifest":"test.json"}],
                      {"test.ready":{"class_id":"test.ready","assets":[{"role":"hero","secure_url":"https://example.invalid/test.png"}]}})


if __name__ == '__main__':
    unittest.main()
