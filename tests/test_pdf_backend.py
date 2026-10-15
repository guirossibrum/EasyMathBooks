from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree

from generate import LEVELS, LEVEL_BY_NUM, generate_one, paper_size, preview_sheet


class NativePdfTest(unittest.TestCase):
    def verify_pdf(self, path, paper, pages=1):
        bbox = subprocess.check_output(['pdftotext', '-bbox', str(path), '-'], text=True)
        root = ElementTree.fromstring(bbox)
        rendered_pages = root.findall('.//{*}page')
        self.assertEqual(len(rendered_pages), pages)
        width, height = paper_size(paper)
        for page in rendered_pages:
            self.assertAlmostEqual(float(page.attrib['width']), width, places=2)
            self.assertAlmostEqual(float(page.attrib['height']), height, places=2)
            words = page.findall('.//{*}word')
            self.assertTrue(words, 'PDF must contain extractable vector text')
            for word in words:
                self.assertGreaterEqual(float(word.attrib['xMin']), 0, word.text)
                self.assertGreaterEqual(float(word.attrib['yMin']), 0, word.text)
                self.assertLessEqual(float(word.attrib['xMax']), width, word.text)
                self.assertLessEqual(float(word.attrib['yMax']), height, word.text)
        return ''.join(root.itertext())

    def test_all_levels_paper_sizes_and_example_modes(self):
        with TemporaryDirectory() as tmp:
            for paper in ('letter', 'a4'):
                for examples in (True, False):
                    for level in LEVELS:
                        with self.subTest(paper=paper, examples=examples, level=level.num):
                            sheet = generate_one(level, 1, Path(tmp)/paper/str(examples),
                                                 paper_size(paper), examples=examples)
                            expected = preview_sheet(level, 1, paper_size(paper), examples)
                            self.assertEqual(sheet.problem_count, expected['problem_count'])
                            self.verify_pdf(sheet.pdf_path, paper)
                            self.verify_pdf(sheet.answers_path, paper)

    def test_multiple_pages_and_unicode_name(self):
        with TemporaryDirectory() as tmp:
            sheet = generate_one(LEVEL_BY_NUM[1], 1, tmp, paper_size('letter'),
                                 pages=2, student_name='Zoë María 李')
            text = self.verify_pdf(sheet.pdf_path, 'letter', pages=2)
            self.assertIn('Zoë', text)
            self.assertIn('María', text)
            self.assertIn('李', text)
