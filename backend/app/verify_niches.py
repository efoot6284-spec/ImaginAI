"""
Verification Script for ImaginAI Niche Data
Checks that:
1. Total domains == 7
2. Total sub-niches == 20
3. All 5 required fields (title, script_style, sources, music_mood, clip_duration_limit) are non-empty for every sub-niche.
"""

import sys
from app.niches import DOMAINS_DATA, get_all_niches

REQUIRED_FIELDS = ["title", "script_style", "sources", "music_mood", "clip_duration_limit"]

def run_verification():
    domains = get_all_niches()
    domain_count = len(domains)
    print(f"[*] Total Domains Count: {domain_count}")

    if domain_count != 7:
        print(f"[ERROR] Expected 7 domains, found {domain_count}")
        sys.exit(1)

    total_sub_niches = 0
    errors = []

    for d_idx, domain in enumerate(domains, start=1):
        d_title = domain.get("title", "UNNAMED")
        sub_list = domain.get("sub_niches", [])
        print(f"\n[{d_idx}/7] Domain: '{d_title}' ({len(sub_list)} sub-niches)")

        for sn_idx, sub in enumerate(sub_list, start=1):
            total_sub_niches += 1
            sn_title = sub.get("title", f"SubNiche #{sn_idx}")
            print(f"   -> #{total_sub_niches} Sub-niche: '{sn_title}'")

            for field in REQUIRED_FIELDS:
                val = sub.get(field)
                if val is None or str(val).strip() == "":
                    err = f"Domain '{d_title}' -> Sub-niche '{sn_title}' is missing required field '{field}'"
                    errors.append(err)
                    print(f"      [!] MISSING FIELD: {field}")
                else:
                    print(f"      - {field}: {val}")

    print("\n" + "=" * 50)
    print(f"[*] Total Sub-niches Count: {total_sub_niches}")

    if total_sub_niches != 20:
        print(f"[ERROR] Expected 20 sub-niches, found {total_sub_niches}")
        sys.exit(1)

    if errors:
        print(f"[ERROR] Found {len(errors)} validation errors:")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)

    print("[SUCCESS] All 7 domains and 20 sub-niches are 100% verified with all 5 required fields!")

if __name__ == "__main__":
    run_verification()
