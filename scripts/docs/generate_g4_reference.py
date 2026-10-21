"""Generate source-verified API contract reference from the runtime declaration audit.

G4 uses exactly the G1 introspection and registry contract; no guessed
signatures, default values, or backend compatibility.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.docs.full_api_audit import collect

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "docs/public/reference/generated-contracts.mdx"


def generate() -> str:
    audit = collect()
    lines = [
        '---',
        'title: "Source-derived API contracts"',
        'description: "Verified signatures, defaults, component events and child policies extracted from the PSX code."',
        '---',
        '',
        '# Source-derived API contracts',
        '',
        'This reference is generated from the checked-out source using the G1 API auditor.',
        'Signatures and defaults are declarations, not proof of runtime/native compatibility.',
        'A candidate test is only a search match and **not** proof the behavior was tested.',
        '',
        '## Public and declared symbols',
        '',
    ]
    for qualified, item in sorted(audit["symbols"].items()):
        lines.extend([
            f'### `{qualified}`',
            '',
            f'- Kind: `{item["kind"]}`',
            f'- Signature: `{(item["signature"] or "not inspectable").replace(chr(96), chr(39))}`',
            f'- Implementation: `{item["implementation"] or "not traceable"}`' + (f', line {item["line"]}' if item["line"] else ''),
            f'- First docstring line: {(" ".join(item["docstring"]) or "No inline docstring.")}',
            '- Candidate tests (not behavioral certification): ' +
            (', '.join(f'`{p}`' for p in item["candidate_test_files"][:12]) if item["candidate_test_files"] else 'none located by name match'),
            '',
        ])
    lines.extend(['## Registered components', ''])
    for name, item in sorted(audit["registered_components"].items()):
        lines.extend([f'### `{name}`', '',f'- Exported from the package root: `{item["public_root_export"]}`'])
        contract = item["contract"]
        if contract is None:
            lines.extend(['- No portable component contract defined.', ''])
            continue
        lines.extend([
            f'- Child policy: `{contract["child_policy"]}`',
            '- Properties: ' + (', '.join(f'`{x}`' for x in contract["properties"]) or 'none'),
            '- Events: ' + (', '.join(f'`{x}`' for x in contract["events"]) or 'none'),
            f'- Text/content property: `{contract["content_property"]}`',
            '- Actual defaults (Python repr):',
            '',
            '```python',
            *[f'{key} = {value}' for key, value in sorted(contract["defaults"].items())],
            '```',
            '',
        ])
    lines.extend([
        '## Support and reproducibility boundaries', '',
        '- Use native backend-specific tests to assert backend support; registry membership is insufficient.',
        '- Do not treat headless behavior as a Qt, Tkinter or Kivy guarantee.',
        '- Some callable introspection signatures are not available; consult source in that case.',
        '- Full reproducible applications and platform-specific evidence are delivered in G5/G6.',
        '',
    ])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.write == args.check:
        parser.error('Exactly one of --write or --check must be provided')
    output = generate()
    if args.write:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(output, encoding='utf-8')
    elif not TARGET.is_file() or TARGET.read_text(encoding='utf-8') != output:
        import base64
        encoded = base64.b64encode(output.encode('utf-8')).decode('ascii')
        for offset in range(0, len(encoded), 1024):
            print('GENERATED_CONTRACT_CHUNK ' + encoded[offset:offset + 1024], flush=True)
        raise SystemExit('Generated API contract reference is stale; regenerate and review')
    print('Source-derived component and API contract reference: PASS')


if __name__ == '__main__':
    main()
