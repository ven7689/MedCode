"""
Live end-to-end test — calls the VLM directly on real medical images.
Usage:  python live_test.py
"""
import django
import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Medcode.settings")
django.setup()

from coder_app.services import call_vlm

IMAGES = [
    "media/documents/test_image_2.jpg",
    "media/documents/test_image_3.jpg",
    "media/documents/test_image_7.jpg",
]

for img in IMAGES:
    print(f"\n{'='*60}")
    print(f"Image: {img}")
    print("="*60)
    try:
        results = call_vlm(img)
        if results:
            for item in results:
                print(f"  [{item.get('code', '?')}] {item.get('description', '?')}")
        else:
            print("  (no codes returned)")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nDone.")
