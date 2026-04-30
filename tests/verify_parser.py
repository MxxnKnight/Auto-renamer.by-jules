from media_parser import parse_media_info

def test_rich_parser():
    test_cases = [
        {
            "filename": "TN 2026 (2026) [Tamil 1080p WEBRip HEVC x265 DD5.1].mkv",
            "caption": "Tamil Movie 2026",
            "type": "movie",
            "expected": "TN.2026.2026.Tamil.1080p.WEBRip.HEVC.X265"
        },
        {
            "filename": "Inception.2010.1080p.BluRay.x264.DDP5.1.mkv",
            "caption": "Inception 2010",
            "type": "movie",
            "expected": "Inception.2010.1080p.BLURAY.X264"
        }
    ]

    print("Running Rich Parser Tests...\n")
    for case in test_cases:
        info = parse_media_info(case["filename"], case["caption"], search_type=case["type"])
        result = str(info)
        print(f"Input: {case['filename']}")
        print(f"Output: {result}")
        print("-" * 20)

if __name__ == "__main__":
    test_rich_parser()
