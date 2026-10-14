#!/usr/bin/env python3
"""Capture local demo reports with Chromium, including PDFs and a TV preview."""
from pathlib import Path
import argparse
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/ui-review'
MOTIFS = ('flowers', 'unicorns', 'butterflies', 'sports', 'cars', 'airplanes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--showcase', action='store_true',
                        help='Refresh the public showcase assets from the fictional previews.')
    args = parser.parse_args()
    chromium = shutil.which('chromium')
    if not chromium:
        raise SystemExit('Chromium is required to capture the demo reports.')
    with TemporaryDirectory(prefix='easymath-browser-') as tmp:
        common = [chromium, '--headless', '--no-sandbox', '--disable-gpu',
                  '--disable-dev-shm-usage', '--no-first-run', '--no-default-browser-check',
                  '--hide-scrollbars', '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw',
                  f'--user-data-dir={tmp}']
        for motif in (*MOTIFS, 'flowers-timed', 'flowers-archived'):
            html = OUT / f'report-{motif}.html'
            screen = OUT / f'report-{motif}-screen.png'
            pdf = OUT / f'report-{motif}.pdf'
            result = subprocess.run(common + [f'--screenshot={screen}', f'--print-to-pdf={pdf}',
                                             '--window-size=1200,1150', html.as_uri()],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode or not screen.exists() or not pdf.exists():
                raise RuntimeError(result.stderr)
            info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
            pages = next(line for line in info.splitlines() if line.startswith('Pages:'))
            if int(pages.split(':')[1]) != 1:
                raise RuntimeError(f'{motif} keepsake must fit one page: {pages}')
            subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '1300', '-png',
                            str(pdf), str(OUT / f'report-{motif}-print')], check=True,
                           capture_output=True)
            print(f'PASS {motif}: screen preview + one-page PDF + print preview', flush=True)
        for motif in MOTIFS:
            subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '1300', '-png',
                            str(OUT/f'worksheet-{motif}.pdf'), str(OUT/f'worksheet-{motif}')],
                           check=True, capture_output=True)
        print('PASS six themed worksheet print previews')
        tv = OUT / 'report-airplanes-tv.png'
        result = subprocess.run(common + [f'--screenshot={tv}', '--window-size=1920,1080',
                                         (OUT / 'report-airplanes.html').as_uri() + '?tv'],
                                capture_output=True, text=True, timeout=30)
        if result.returncode or not tv.exists():
            raise RuntimeError(result.stderr)
        print('PASS TV preview at 1920 × 1080')
    if args.showcase:
        showcase = ROOT / 'docs/showcase'
        assets = list(showcase.iterdir())
        for asset in assets:
            source = OUT / asset.name
            if not source.is_file():
                raise RuntimeError(f'Generate the latest demo/widget preview first: {source}')
        for asset in assets:
            shutil.copy2(OUT / asset.name, asset)
        print(f'PASS refreshed {len(assets)} public showcase assets from fictional data')


if __name__ == '__main__':
    main()
