import unittest
import extract_dialog


class TestQuotationSeparator(unittest.TestCase):
    def check_dqm(self, qs, line, expected_results):
        results = list(qs.determine_quote_marks(line))
        self.assertEqual(expected_results, results)

    def test_determine_quote_marks(self):
        qs = extract_dialog.QuotationSeparator(["‘’"], {"’"}, False)
        START, END, QEND = qs.START, qs.END, qs.QUESTIONABLE_END
        self.check_dqm(qs, "No quoting here", [])
        self.check_dqm(qs, "‘Pure quotation’",
                       [(START, 0, "‘"), (END, 15, "’")])
        self.check_dqm(qs, "‘Beginning quotation’ with narrative.",
                       [(START, 0, "‘"), (END, 20, "’")])
        self.check_dqm(qs, "‘There’s another use for apostrophes’",
                       [(START, 0, "‘"), (END, 36, "’")])
        # trickiest case: a ’. can be a possessive marker at the end of a sentence, or a quotation before the end of the sentence.
        self.check_dqm(qs, "‘End apostrophes could be possessives’. But they don’t end quotations’.",
                       [(START, 0, "‘"), (QEND, 37, "’"), (QEND, 69, "’")])

    def check_sq(self, qs, line, expected_results):
        results = list(qs.split_quotes(line))
        self.assertEqual(expected_results, results)

    def test_split_quotes(self):
        qs = extract_dialog.QuotationSeparator(["‘’"], {"’"}, False)
        Q, N = qs.QUOTATION, qs.NARRATIVE
        self.check_sq(qs, "No quoting here", [(N, 0, "No quoting here")])
        self.check_sq(qs, "‘Pure quotation’", [(Q, 0, "‘Pure quotation’")])
        self.check_sq(qs, "‘Beginning quotation’ with narrative.",
                     [(Q, 0, "‘Beginning quotation’"), (N, 21, " with narrative.")])
        self.check_sq(qs, "‘There’s another use for apostrophes’",
                     [(Q, 0, "‘There’s another use for apostrophes’")])
        # trickiest case: a ’. can be a possessive marker at the end of a sentence, or a quotation before the end of the sentence.
        self.check_sq(qs, "‘End apostrophes could be possessives’. But they don’t end quotations’.",
                      [(Q, 0, "‘End apostrophes could be possessives’. But they don’t end quotations’"),
                       (N, 70, ".")])




if __name__ == '__main__':
    unittest.main()
