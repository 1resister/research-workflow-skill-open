"""Render the documented reading-to-figure example using Python 3.10+ stdlib.

This draws original SVGs from saved computations; it does not trace a source image.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

BLUE, SEPTIC, PURPLE = '#2563EB', '#DC2626', '#6D28D9'
INK, MUTED, GRID = '#172033', '#526174', '#DDE4ED'
CASE_IDS = ['move_1mm', 'move_10mm', 'move_100mm', 'move_1000mm']


def label(x, y, text, size=16, fill=INK, anchor='start', weight=400):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{html.escape(text)}</text>')


def line(x1, y1, x2, y2, stroke=GRID, width=1, extra=''):
    return (f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="{stroke}" stroke-width="{width}" {extra}/>')


def svg(title, description, body, height):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" '
            f'height="{height}" viewBox="0 0 1280 {height}" role="img" '
            'aria-labelledby="title description">\n'
            f'<title id="title">{html.escape(title)}</title>\n'
            f'<desc id="description">{html.escape(description)}</desc>\n'
            '<style>text{font-family:Arial,Helvetica,sans-serif} '
            '*{box-sizing:border-box}</style>\n'
            '<rect width="100%" height="100%" fill="#FFFFFF"/>\n' + '\n'.join(body) + '\n</svg>\n')


def read_rows(summary):
    limits = summary['limits']
    if limits != {'velocity': 0.5, 'acceleration': 1.0, 'jerk': 20.0}:
        raise ValueError('This bounded example is labelled for V=0.5, A=1, J=20; use the supplied summary.')
    cases = {case['id']: case for case in summary['cases']}
    if len(cases) != len(summary['cases']):
        raise ValueError('Duplicate case IDs.')
    rows = []
    for case_id in CASE_IDS:
        case = cases[case_id]
        family = case['families']
        distance = abs(case['end_m'] - case['start_m']) * 1000
        q, s = (family[k]['minimum_duration_s'] for k in ('quintic', 'septic'))
        values = (distance, q, s)
        if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in values):
            raise ValueError(f'Invalid values for {case_id}.')
        if not math.isclose(distance, float(case_id[5:-2]), rel_tol=1e-10):
            raise ValueError('Case ID and actual travel distance differ.')
        active = []
        for name, duration in [('quintic', q), ('septic', s)]:
            bounds = family[name]['duration_bounds_s']
            if not math.isclose(max(bounds.values()), duration, rel_tol=1e-10):
                raise ValueError('Saved duration is inconsistent with the saved bound values.')
            active.append(max(bounds, key=bounds.get).removesuffix('_s'))
        rows.append({'case_id': case_id, 'distance_mm': distance,
                     'quintic_duration_s': q, 'septic_duration_s': s,
                     'septic_change_percent': (s / q - 1) * 100,
                     'quintic_active_bound': active[0], 'septic_active_bound': active[1]})
    return rows


def workflow():
    body = [
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#2563EB"/></marker><marker id="planned" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#697586"/></marker></defs>',
        label(48, 50, 'From a motion question to checked evidence', 28, weight=700),
        label(48, 84, 'Single-axis teaching example: implemented computation and explicitly planned validation', 18, MUTED)]
    nodes = [
        (60, 140, '1  Freeze the motion task', ['Rest to rest; one linear axis', 'Travel: 1 / 10 / 100 / 1000 mm', 'V=0.5 m/s; A=1 m/s²; J=20 m/s³']),
        (460, 140, '2  Specify the fixed shapes', ['Quintic and septic time laws', 'Rest joins: C² versus C³', 'State the endpoint jerk policy']),
        (860, 140, '3  Calculate feasible duration', ['T = max(Tv, Ta, Tj)', 'Identical kinematic limits', 'Own minimum / common duration']),
        (60, 355, '4  Save auditable outputs', ['Sample position, velocity, a, jerk', 'CSV trajectories + JSON summary', 'Record input, code and versions']),
        (460, 355, '5  Check the actual evidence', ['Critical points and endpoints', 'Coefficient and sample checks', 'Saved example: 201 checks passed']),
        (860, 355, '6  Interpret and communicate', ['Separate comparison conditions', 'Label units, scales and legends', 'Report the supported claim only'])]
    for x, y, title, details in nodes:
        body.append(f'<rect x="{x}" y="{y}" width="340" height="140" rx="12" fill="#F5F8FF" stroke="#AABFE8" stroke-width="1.5"/>')
        body.append(label(x + 18, y + 31, title, 19, weight=700))
        for i, detail in enumerate(details):
            body.append(label(x + 18, y + 65 + i * 25, detail, 16))
    for y in (210, 425):
        for x in (400, 800):
            body.append(line(x + 7, y, x + 51, y, BLUE, 2.5, 'marker-end="url(#arrow)"'))
    body.append('<path d="M1030 280 V315 H230 V347" fill="none" stroke="#2563EB" stroke-width="2.5" marker-end="url(#arrow)"/>')
    body.append(line(1030, 495, 1030, 553, '#697586', 2.5, 'stroke-dasharray="7 5" marker-end="url(#planned)"'))
    body.append('<rect x="860" y="560" width="340" height="92" rx="12" fill="#FAFBFC" stroke="#697586" stroke-width="1.5" stroke-dasharray="7 5"/>')
    body.extend([label(878, 590, 'Closed-loop / hardware validation', 17, weight=700),
                 label(878, 619, 'Planned; not executed in this example', 15, MUTED),
                 line(60, 584, 110, 584, BLUE, 2.5), label(124, 590, 'Implemented computation', 17),
                 line(60, 621, 110, 621, '#697586', 2.5, 'stroke-dasharray="7 5"'),
                 label(124, 627, 'Planned validation', 17)])
    return svg('Motion research workflow', 'Six implemented stages lead from a defined single-axis task to checked calculations and plots. A dashed arrow leads to hardware validation, which is planned and was not executed.', body, 700)


def tradeoff(rows):
    body = [label(48, 48, 'Endpoint jerk continuity and fixed-shape duration', 28, weight=700),
            label(48, 82, 'Selected rest-to-rest cases; V=0.5 m/s, A=1 m/s², J=20 m/s³', 18, MUTED),
            label(80, 130, 'A  Minimum feasible duration', 21, weight=700),
            label(760, 130, 'B  Septic relative to quintic', 21, weight=700)]
    y0, y1 = 190, 520
    xleft = [120 + 150*i for i in range(4)]
    xright = [800 + 125*i for i in range(4)]
    to_y = lambda t: y1 - math.log10(t / 0.1) / math.log10(5 / 0.1) * (y1 - y0)
    percent_y = lambda p: y1 - (p + 8) / 30 * (y1 - y0)
    body.extend([label(80, 163, 'Time (s; logarithmic scale)', 15, MUTED),
                 label(760, 163, '100 × (Tseptic / Tquintic − 1), %', 15, MUTED)])
    for t in [.1, .2, .5, 1, 2, 5]:
        y = to_y(t);body += [line(80, y, 620, y), label(67, y + 5, f'{t:g}', 14, MUTED, 'end')]
    for percent in [-5, 0, 10, 20]:
        y = percent_y(percent)
        body += [line(760, y, 1210, y, '#7F8B9A' if percent == 0 else GRID, 1.5 if percent == 0 else 1),
                 label(748, y + 5, f'{percent:g}', 14, MUTED, 'end')]
    for i, row in enumerate(rows):
        xa, xb = xleft[i], xright[i]
        for x in [xa, xb]:
            body += [line(x, y1, x, y1 + 6, '#7F8B9A'), label(x, y1 + 28, f"{row['distance_mm']:g}", 15, MUTED, 'middle')]
        yq, ys = to_y(row['quintic_duration_s']), to_y(row['septic_duration_s'])
        body += [f'<circle cx="{xa}" cy="{yq:.3f}" r="6" fill="#FFFFFF" stroke="{BLUE}" stroke-width="2.5"/>',
                 f'<rect x="{xa-5}" y="{ys-5:.3f}" width="10" height="10" fill="none" stroke="{SEPTIC}" stroke-width="2.5"/>']
        p = row['septic_change_percent'];y = percent_y(p)
        body += [line(xb, percent_y(0), xb, y, PURPLE, 3),
                 f'<circle cx="{xb}" cy="{y:.3f}" r="5.5" fill="{PURPLE}"/>',
                 label(xb, y - 14 if p >= 0 else y + 26, f'{p:+.2f}%', 19, PURPLE, 'middle', 700)]
    body.extend([line(80, y1, 620, y1, '#7F8B9A'), line(760, y1, 1210, y1, '#7F8B9A'),
                 label(350, 579, 'Travel distance (mm; log scale)', 17, anchor='middle'),
                 label(985, 579, 'Travel distance (mm; log scale)', 17, anchor='middle'),
                 '<circle cx="130" cy="235" r="6" fill="white" stroke="#2563EB" stroke-width="2.5"/>',
                 label(147, 241, 'Quintic', 16),
                 f'<rect x="124" y="258" width="12" height="12" fill="none" stroke="{SEPTIC}" stroke-width="2.5"/>',
                 label(147, 270, 'Septic', 16),
                 label(985, 605, 'Positive values: septic takes longer', 15, MUTED, 'middle'),
                 '<rect x="48" y="633" width="1184" height="67" rx="8" fill="#F3F6FA"/>',
                 label(66, 660, 'Rest joins: quintic is C² (classical jerk undefined at joins); septic is C³.', 16),
                 label(66, 685, 'Deterministic selected cases; no error bars, global time-optimality claim or hardware result.', 16, MUTED)])
    return svg('Duration and endpoint continuity trade-off', 'Panel A shows log-log duration points for two fixed polynomial families. Panel B shows septic duration changes of about −4.35%, −4.35%, +14.08% and +16.67%. These are selected deterministic computations, not hardware measurements.', body, 730)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.summary.read_bytes();input_hash = hashlib.sha256(raw).hexdigest()
    rows = read_rows(json.loads(raw))
    out = args.output
    names = ['workflow-overview.svg', 'duration-tradeoff.svg', 'plot-data.csv', 'quality-checks.json', 'manifest.json']
    if out.exists() and any(out.iterdir()):
        prior = json.loads((out/'manifest.json').read_text('utf-8')) if (out/'manifest.json').is_file() else {}
        if prior.get('generator') != 'figure-reading-and-design-v1' or prior.get('input_sha256') != input_hash:
            raise ValueError('Use an empty output directory or a previous run of this example with the same input.')
    out.mkdir(parents=True, exist_ok=True)
    payloads = {'workflow-overview.svg': workflow(), 'duration-tradeoff.svg': tradeoff(rows)}
    for data in payloads.values():
        ET.fromstring(data)
    buffer = io.StringIO(newline='');writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader();writer.writerows(rows);payloads['plot-data.csv'] = buffer.getvalue()
    checks = {'status':'passed', 'case_count':4, 'conditions':'identical saved V/A/J limits; own minimum duration in each fixed shape',
              'checks':{'finite_positive_data':True, 'distance_matches_case_ids':True, 'duration_matches_saved_bounds':True,
                        'relative_change_computed_from_saved_data':True, 'svg_xml_parses':True},
              'unverified':['independent numerical verification is in the original trajectory example, not rerun by this renderer',
                            'hardware or closed-loop performance','target-journal typography and physical print size','formal color-vision simulation']}
    payloads['quality-checks.json'] = json.dumps(checks, ensure_ascii=False, indent=2)+'\n'
    for name, text in payloads.items():(out/name).write_text(text, encoding='utf-8', newline='\n')
    manifest = {'generator':'figure-reading-and-design-v1', 'python':platform.python_version(), 'input_sha256':input_hash,
                'source_kind':'previously computed deterministic trajectory summary; no third-party image or icon copied',
                'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'command_argv':sys.argv[1:],
                'outputs':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in payloads}}
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n','utf-8')
    print(json.dumps({'status':'passed','output_files':names,'cases':len(rows)}))


if __name__ == '__main__':
    main()
