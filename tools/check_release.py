#!/usr/bin/env python3
"""Check the recorded original-only release boundary; this does not grant rights."""
import argparse,json
from pathlib import Path
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'PUBLICATION.json').read_text('utf-8'))
    failures=[k for k,v in data['required_checks'].items() if v is not True]
    if data.get('release_kind')!='original_materials_only':failures.append('original_only_release_kind')
    if data.get('third_party_fulltext_or_assets_included') is not False:failures.append('third_party_materials_excluded')
    if not (root/'LICENSE').is_file() or not (root/'ATTRIBUTION.md').is_file():failures.append('license_and_attribution_present')
    forbidden=['SOURCE_AUDIT.md','READING_COVERAGE.md','skills/research-workflow/references/source-register.json','skills/research-workflow/references/browser-access-review.json','skills/research-workflow/references/expanded-source-review.json','skills/research-workflow/references/guide-workflow-map.md']
    failures += ['excluded:'+p for p in forbidden if (root/p).exists()]
    passed=data.get('public_release_allowed') is True and not failures
    print(json.dumps({'public_gate_passed':passed,'unmet_checks':failures,'reason':data['reason']},ensure_ascii=False,indent=2))
    return 2 if args.public and not passed else 0
if __name__=='__main__':raise SystemExit(main())
