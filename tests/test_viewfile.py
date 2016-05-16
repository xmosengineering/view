import copy
import contextlib
import StringIO
import unittest

from view import viewfile

def _make_simple_entry(name, branch='master', revision='HEAD'):
    return viewfile.ViewFileEntry(name, 'git://{0}/{0}'.format(name), 'GIT',
                                  branch, revision)

class TestViewFileEntryMethods(unittest.TestCase):
    def test_has_revision(self):
        unversioned_entry = _make_simple_entry('foo')
        versioned_entry = _make_simple_entry(
          'foo',
          revision='7783ac32d05162f328bba0d64e56b80a9f15bb17')
        self.assertFalse(unversioned_entry.has_revision())
        self.assertTrue(versioned_entry.has_revision())

    def test_eq(self):
        self.assertTrue(_make_simple_entry('foo') == _make_simple_entry('foo'))
        self.assertFalse(_make_simple_entry('foo') == _make_simple_entry('bar'))

class TestViewFileMethods(unittest.TestCase):
    def test_dump(self):
        view = viewfile.ViewFile()
        view.entries.append(_make_simple_entry('foo'))
        with contextlib.closing(StringIO.StringIO()) as f:
            view.dump(f)
            contents = f.getvalue()
        self.assertEqual(contents,
                         'foo git://foo/foo GIT master HEAD\n')

    def test_eq(self):
        foo1 = viewfile.ViewFile([_make_simple_entry('foo')])
        foo2 = viewfile.ViewFile([_make_simple_entry('foo')])
        bar = viewfile.ViewFile([_make_simple_entry('bar')])
        self.assertTrue(foo1 == foo2)
        self.assertFalse(foo1 == bar)

class TestViewFileParse(unittest.TestCase):
    def test_valid(self):
        contents = \
'''
# Comments and whitespace only lines should be ignored
  
foo git://foo/foo GIT master HEAD
'''
        with contextlib.closing(StringIO.StringIO(contents)) as f:
            view = viewfile.parse(f)
        expected = viewfile.ViewFile([_make_simple_entry('foo')])
        self.assertEqual(view, expected)

    def test_invalid(self):
        invalid_views = [
            'foo git://foo/foo GIT master',
            'foo git://foo/foo GIT master HEAD extra'
        ]
        for s in invalid_views:
            with contextlib.closing(StringIO.StringIO(s)) as f:
                with self.assertRaises(viewfile.ParseError):
                    viewfile.parse(f)

class TestViewFileDiff(unittest.TestCase):
    def setUp(self):
        self.foo_entry = _make_simple_entry('foo')
        self.bar_entry = _make_simple_entry('bar')
        self.foo_dev_entry = _make_simple_entry('foo', branch='dev')

        self.empty_view = viewfile.ViewFile()

        self.foo_view = viewfile.ViewFile([copy.copy(self.foo_entry)])
        self.bar_view = viewfile.ViewFile([copy.copy(self.bar_entry)])

        self.foobar_view = viewfile.ViewFile([copy.copy(self.foo_entry),
                                              copy.copy(self.bar_entry)])

        self.foo_dev_view = viewfile.ViewFile([copy.copy(self.foo_dev_entry)])

    def test_no_changes(self):
        diff = viewfile.diff(self.empty_view, self.empty_view)
        self.assertEqual(diff, {})
        diff = viewfile.diff(self.foo_view, self.foo_view)
        self.assertEqual(diff, {})

    def test_added(self):
        diff = viewfile.diff(self.empty_view, self.foo_view)
        self.assertEqual(diff, {'foo': (None, self.foo_entry)})
        diff = viewfile.diff(self.empty_view, self.foobar_view)
        self.assertEqual(diff, {'bar': (None, self.bar_entry),
                                'foo': (None, self.foo_entry)})
        diff = viewfile.diff(self.foo_view, self.foobar_view)
        self.assertEqual(diff, {'bar': (None, self.bar_entry)})

    def test_removed(self):
        diff = viewfile.diff(self.foo_view, self.empty_view)
        self.assertEqual(diff, {'foo': (self.foo_entry, None)})
        diff = viewfile.diff(self.foobar_view, self.empty_view)
        self.assertEqual(diff, {'bar': (self.bar_entry, None),
                                'foo': (self.foo_entry, None)})
        diff = viewfile.diff(self.foobar_view, self.foo_view)
        self.assertEqual(diff, {'bar': (self.bar_entry, None)})

    def test_changed(self):
        diff = viewfile.diff(self.foo_view, self.foo_dev_view)
        self.assertEqual(diff, {'foo': (self.foo_entry, self.foo_dev_entry)})

    def test_complex(self):
        diff = viewfile.diff(self.foobar_view, self.foo_dev_view)
        self.assertEqual(diff, {'foo': (self.foo_entry, self.foo_dev_entry),
                                'bar': (self.bar_entry, None)})
