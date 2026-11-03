"""Foldknife unit tests. Run: python -m unittest discover tests"""
import datetime as dt
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("FOLDKNIFE_HOME", tempfile.mkdtemp(prefix="foldknife-test-"))

from foldknife.core import ui  # noqa: E402
from foldknife.core.utils import parse_date, parse_duration  # noqa: E402
from foldknife.tools import load_all, LOAD_ERRORS  # noqa: E402

ui.init_terminal(color=False)
load_all()

from foldknife.core.registry import all_tools, search  # noqa: E402
from foldknife.tools import (arcade, boardgames, convert, crypto, data, dev, finnish, fun, games, mathtools,  # noqa: E402
                          media, qr, text)


class TestCore(unittest.TestCase):
    def test_all_modules_load(self):
        self.assertEqual(LOAD_ERRORS, {})
        self.assertGreater(len(all_tools()), 200)

    def test_search(self):
        ids = [t.id for t in search("salasana")]
        self.assertIn("crypto-password-generator", ids)

    def test_parse_duration(self):
        self.assertEqual(parse_duration("1h 30min"), 5400)
        self.assertEqual(parse_duration("25"), 1500)
        self.assertEqual(parse_duration("90s"), 90)

    def test_parse_date(self):
        today = dt.date(2026, 11, 3)
        self.assertEqual(parse_date("24.12.2026"), dt.date(2026, 12, 24))
        self.assertEqual(parse_date("huomenna", today), dt.date(2026, 11, 4))
        self.assertEqual(parse_date("+7", today), dt.date(2026, 11, 10))

    def test_fi_num(self):
        self.assertEqual(ui.fi_num(1234567.891), "1,234,567.89")


class TestMath(unittest.TestCase):
    def ev(self, expr):
        return mathtools.evaluate(expr)

    def test_calculator(self):
        self.assertEqual(self.ev("2^10"), 1024)
        self.assertEqual(self.ev("2(3+4)"), 14)
        self.assertEqual(self.ev("log10(1000)"), 3)
        self.assertEqual(self.ev("15% * 200"), 30)
        self.assertEqual(self.ev("5!"), 120)
        self.assertAlmostEqual(self.ev("3,5+1"), 4.5)
        self.assertEqual(mathtools.evaluate("1/3+1/6", exact=True), mathtools.Fraction(1, 2))
        with self.assertRaises(mathtools.CalcError):
            self.ev("__import__('os')")
        with self.assertRaises(mathtools.CalcError):
            self.ev("9**9**9")

    def test_primes(self):
        self.assertTrue(mathtools.is_prime(2 ** 61 - 1))
        self.assertEqual(mathtools.factorize(600851475143), {71: 1, 839: 1, 1471: 1, 6857: 1})
        self.assertEqual(mathtools.sieve(30), [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])

    def test_matrix(self):
        m = mathtools.parse_matrix("1 2; 3 4")
        self.assertEqual(mathtools.determinant(m), -2)
        inv = mathtools.inverse(m)
        self.assertEqual(mathtools.mat_mul(m, inv), [[1, 0], [0, 1]])

    def test_quadratic_and_roots(self):
        self.assertEqual(mathtools.solve_quadratic(1, 0, -4), [-2.0, 2.0])
        roots = mathtools.find_roots(mathtools.make_func("x^2 - 2"), -3, 3)
        self.assertEqual(len(roots), 2)
        self.assertAlmostEqual(roots[1], 2 ** 0.5, places=6)

    def test_grades(self):
        self.assertEqual(mathtools.parse_grade("8+"), 8.25)
        self.assertEqual(mathtools.parse_grade("9-"), 8.75)
        self.assertEqual(mathtools.parse_grade("7½"), 7.5)


class TestConvert(unittest.TestCase):
    def test_units(self):
        self.assertAlmostEqual(convert.convert_units(10, "km", "mi"), 6.2137119, places=5)
        self.assertAlmostEqual(convert.convert_units(100, "C", "F"), 212)
        self.assertAlmostEqual(convert.convert_units(1, "cup", "dl"), 2.365882365, places=6)

    def test_bases_and_roman(self):
        self.assertEqual(convert.to_base(255, 16), "ff")
        self.assertEqual(convert.parse_int_auto("0b1010"), 10)
        self.assertEqual(convert.roman_to_int("MMXXVI"), 2026)
        self.assertEqual(mathtools.roman(1994), "MCMXCIV")

    def test_colors(self):
        self.assertEqual(convert.parse_color("#f80"), (255, 136, 0))
        self.assertAlmostEqual(convert.contrast_ratio((0, 0, 0), (255, 255, 255)), 21, places=1)

    def test_months_between(self):
        self.assertEqual(convert.months_between(dt.date(2024, 1, 31), dt.date(2024, 3, 1)), (0, 1, 1))


class TestFinnish(unittest.TestCase):
    def test_hetu(self):
        info = finnish.hetu_info("131052-308T", today=dt.date(2026, 1, 1))
        self.assertIn("1952-10-13", info["Date of birth"])
        with self.assertRaises(ValueError):
            finnish.hetu_info("131052-308X")

    def test_business_id_and_iban(self):
        self.assertEqual(finnish.validate_ytunnus("0112038-9"), "0112038-9")
        self.assertEqual(finnish.validate_iban("FI21 1234 5600 0007 85"), "FI2112345600000785")
        with self.assertRaises(ValueError):
            finnish.validate_iban("FI21 1234 5600 0007 86")

    def test_reference_numbers(self):
        self.assertEqual(finnish.make_reference("1234"), "12344")
        rf = finnish.to_rf("12344")
        self.assertEqual(finnish.validate_rf(rf), rf)

    def test_barcode(self):
        code = finnish.make_barcode("FI79 4405 2020 0360 82", 4883.15, "868516259619897", dt.date(2010, 6, 12))
        self.assertEqual(code, "479440520200360820048831500000000868516259619897100612")

    def test_words(self):
        self.assertEqual(finnish.number_to_words(2026), "kaksituhattakaksikymmentäkuusi")
        self.assertEqual(finnish.ordinal_words(21), "kahdeskymmenesensimmäinen")

    def test_holidays(self):
        self.assertEqual(finnish.easter(2026), dt.date(2026, 4, 5))
        h = finnish.holidays(2026)
        self.assertEqual(h[dt.date(2026, 6, 20)][0].split(",")[0], "Midsummer Day")

    def test_hyphenation(self):
        self.assertEqual(finnish.hyphenate("kalakukko maailma radio"), "ka-la-kuk-ko maa-il-ma ra-di-o")


class TestTextAndCrypto(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(text.convert_case("hello world fooBar", "snake"), "hello_world_foo_bar")
        self.assertEqual(text.slugify("Äitienpäivä on kiva!"), "aitienpaiva-on-kiva")

    def test_morse(self):
        self.assertEqual(text.morse_decode(text.morse_encode("SOS ÄÖ")), "SOS ÄÖ")

    def test_mojibake(self):
        self.assertEqual(text.fix_mojibake("pÃ¤ivÃ¤Ã¤"), "päivää")

    def test_encrypt_roundtrip(self):
        token = crypto.encrypt_text("salainen äö", "pw")
        self.assertEqual(crypto.decrypt_text(token, "pw"), "salainen äö")
        with self.assertRaises(ValueError):
            crypto.decrypt_text(token, "väärä")

    def test_file_encrypt(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "a.bin")
            src.write_bytes(os.urandom(300_000))
            crypto.encrypt_file(src, Path(tmp, "a.enc"), "pw")
            crypto.decrypt_file(Path(tmp, "a.enc"), Path(tmp, "a.out"), "pw")
            self.assertEqual(src.read_bytes(), Path(tmp, "a.out").read_bytes())

    def test_ciphers(self):
        self.assertEqual(crypto.vigenere(crypto.vigenere("Hello", "key"), "key", True), "Hello")
        self.assertEqual(crypto.rail_fence(crypto.rail_fence("WEAREDISCOVERED", 3), 3, True), "WEAREDISCOVERED")
        self.assertEqual(crypto.zw_reveal(crypto.zw_hide("Moi", "salaisuus")), "salaisuus")

    def test_password(self):
        pw = crypto.gen_password(20)
        self.assertEqual(len(pw), 20)
        self.assertEqual(crypto.password_strength("salasana1")["score"], 0)


class TestDevAndData(unittest.TestCase):
    def test_cron(self):
        c = dev.Cron("30 7 * * 1-5")
        runs = c.next_runs(dt.datetime(2026, 11, 6, 8, 0), 2)
        self.assertEqual(runs[0], dt.datetime(2026, 11, 9, 7, 30))

    def test_semver(self):
        self.assertEqual(sorted(["1.10.0", "1.2.0", "1.2.0-beta"], key=dev.semver_key), ["1.2.0-beta", "1.2.0", "1.10.0"])

    def test_json_query(self):
        obj = {"users": [{"name": "Aino"}, {"name": "Eetu"}]}
        self.assertEqual(data.json_query(obj, "users[*].name"), ["Aino", "Eetu"])

    def test_xlsx_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "t.xlsx")
            data.write_xlsx(p, [["a", "b"], ["1", "x"]])
            self.assertEqual(data.read_xlsx(p), [["a", "b"], ["1", "x"]])


class TestMediaAndQr(unittest.TestCase):
    def test_png_roundtrip(self):
        img = media.plasma(20, 10, 1)
        with tempfile.TemporaryDirectory() as tmp:
            p = media.save_image(img, Path(tmp, "a.png"))
            back = media.read_png(p)
        self.assertEqual(back.rows, img.rows)

    def test_steganography(self):
        img = media.plasma(40, 30, 2)
        self.assertEqual(media.steg_reveal(media.steg_hide(img, "moi")), "moi")

    def test_qr_structure(self):
        m = qr.encode_text("https://example.com")
        self.assertEqual(len(m), 25)  # version 2
        self.assertTrue(all(m[r][c] for r, c in ((0, 0), (0, 6), (6, 0), (6, 6))))  # alignment pattern

    def test_note(self):
        self.assertAlmostEqual(media.note_freq("A4"), 440)


class TestGames(unittest.TestCase):
    def test_2048(self):
        self.assertEqual(arcade.merge_line([2, 2, 2, 2]), ([4, 4, 0, 0], 8))

    def test_sanuli(self):
        self.assertEqual(games.sanuli_feedback("kissa", "kassi"), ["oikea", "wrong place", "oikea", "oikea", "wrong place"])

    def test_blackjack(self):
        self.assertEqual(games.hand_value([("A", "♠"), ("A", "♥"), ("9", "♦")]), (21, True))

    def test_sudoku_unique(self):
        puzzle, solution = boardgames.sudoku_generate(32, random.Random(1))
        n, sol = boardgames.sudoku_solve(puzzle, 2)
        self.assertEqual((n, sol), (1, solution))

    def test_yatzy(self):
        self.assertEqual(boardgames.yatzy_score("Full house", [2, 2, 3, 3, 3]), 13)

    def test_dice(self):
        total, rolls, mod = fun.roll_dice("3d6+2", random.Random(1))
        self.assertEqual(total, sum(rolls) + 2)


if __name__ == "__main__":
    unittest.main()
