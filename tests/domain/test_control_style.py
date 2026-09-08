import unittest

from src.csharp.checks import check_csharp


def brace_issues(source, original=None):
    return [issue for issue in check_csharp(source, original=original).issues
            if issue.code == 'control_body_braces']


class ControlStyleTests(unittest.TestCase):
    def test_each_unbraced_control_body_is_reported(self):
        for source, keyword in [
            ('if (ready) return;', 'if'),
            ('for (int i = 0; i < 3; i++) Run(i);', 'for'),
            ('foreach (DataRow row in rows) Add(row);', 'foreach'),
            ('while (Read()) Run();', 'while'),
            ('do Run(); while (Read());', 'do'),
            ('if (ready) { Run(); } else Stop();', 'else'),
        ]:
            with self.subTest(source=source):
                found = brace_issues(source)
                self.assertEqual([keyword], [issue.details['keyword'] for issue in found])
                self.assertEqual('warning', found[0].severity)
                self.assertTrue(check_csharp(source).success)

    def test_braced_bodies_else_if_chains_and_do_tails_are_accepted(self):
        source = '''
if (ready) { Run(); } else if (other) { Stop(); } else { Reset(); }
for (int i = 0; i < 3; i++) { Run(i); }
foreach (DataRow row in rows) { Add(row); }
while (Read()) { Run(); }
do { if (ready) { Run(); } } while (Read());
'''
        self.assertEqual([], brace_issues(source))

    def test_nested_unbraced_controls_and_dangling_else(self):
        found = brace_issues('if (a) if (b) Run(); else Stop();')
        self.assertEqual(['if', 'if', 'else'], [issue.details['keyword'] for issue in found])

    def test_nested_do_bodies_do_not_turn_tails_into_while_bodies(self):
        for source, expected in [
            ('do do Run(); while (a); while (b);', ['do', 'do']),
            ('do if (a) Run(); else Stop(); while (b);', ['do', 'if', 'else']),
            ('do while (a) Run(); while (b);', ['do', 'while']),
            ('do try { Run(); } catch (Exception e) { Stop(); } while (b);', ['do']),
            ('do using (Resource r = Open()) { Run(); } while (b);', ['do']),
        ]:
            with self.subTest(source=source):
                self.assertEqual(expected, [issue.details['keyword'] for issue in brace_issues(source)])

    def test_literals_comments_directives_and_escaped_identifiers_are_not_controls(self):
        source = '''
// if (a) Run();
string a = "if (a) Run();";
string b = @"while (b) Run();";
string c = """do Run(); while (b);""";
string keyword = "if"; Action next = (x) => Run();
service.@if(a); @while(b); obj?.@foreach(c);
#if (DEBUG)
Run();
#endif
'''
        self.assertEqual([], brace_issues(source))

    def test_literal_punctuation_does_not_affect_condition_or_body_boundaries(self):
        source = 'if (text == ")" && Match("(")) Send(";", "}");'
        self.assertEqual(['if'], [issue.details['keyword'] for issue in brace_issues(source)])

    def test_interpolated_lambda_body_is_executable_code(self):
        source = 'string s = $"{Run(() => { if (ready) return 1; return 0; })}";'
        self.assertEqual(['if'], [issue.details['keyword'] for issue in brace_issues(source)])

    def test_unchanged_legacy_body_is_not_a_cleanup_request(self):
        before = 'if (ready) Run("a b");'
        self.assertEqual([], brace_issues('\nif ( ready ) /* same */ Run("a b");', before))

    def test_swapping_an_old_body_for_a_new_one_is_not_hidden_by_equal_counts(self):
        self.assertEqual(1, len(brace_issues('if (other) Run();', 'if (ready) Run();')))
        self.assertEqual(1, len(brace_issues('if (ready) Run("ab");', 'if (ready) Run("a b");')))

    def test_duplicate_new_statement_is_reported_once_at_its_actual_line(self):
        before = 'if (ready) Run();'
        found = brace_issues(before + '\n\n' + before, before)
        self.assertEqual(1, len(found))
        self.assertEqual(3, found[0].line)

    def test_empty_while_body_is_reviewed_except_for_a_do_tail(self):
        self.assertEqual(['while'], [issue.details['keyword'] for issue in brace_issues('while (Read());')])
        self.assertEqual([], brace_issues('do { Run(); } while (Read());'))

    def test_incomplete_fragments_do_not_invent_a_body_or_crash(self):
        for source in ['if (ready)', 'if (', 'if (ready) }', 'do', 'while (Read()', 'if (ready) Run(']:
            with self.subTest(source=source):
                self.assertEqual([], brace_issues(source))


if __name__ == '__main__':
    unittest.main()
