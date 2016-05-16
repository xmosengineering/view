"""Viewfile handling library"""

from __future__ import print_function
import re

DEFAULT_FILENAME = 'view.txt'

class ParseError(Exception):
    """An exception indicating a parse error"""
    pass

class ViewFileEntry(object):
    """
    An entry in a viewfile.

    Attributes:
      dir: The subdirectory to checkout the repository in.
      url: The location of the remote repository, typically a URL.
      vcs: The version control system the repository is stored in.
      branch: The version control system branch.
      revision: The version control system revision. If set to 'HEAD' the
        latest revision should be used.
    """

    def __init__(self, dir_, url, vcs, branch, revision='HEAD'):
        self.dir = dir_
        self.url = url
        self.vcs = vcs
        self.branch = branch
        self.revision = revision

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def has_revision(self):
        """ Return whether the entry specifies a specific revision. """
        return self.revision != 'HEAD'

class ViewFile(object):
    """
    A viewfile.

    A viewfile describes a directory structure of repositories that should be
    checked out of source control.
    """

    def __init__(self, entries=None):
        self.entries = [] if entries is None else list(entries)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

    def dump(self, fp):
        """Write the contents of the viewfile to a file."""
        for entry in self.entries:
            print(entry.dir, entry.url, entry.vcs, entry.branch,
                  entry.revision, file=fp)

def parse(fp, filename=None):
    """
    Parse a viewfile.

    Raises:
      ParseError: If the viewfile cannot be parsed.
    """
    viewfile = ViewFile()
    if filename is None:
        filename = getattr(fp, 'name', '?')
    for line in fp:
        # Skip empty lines / comment lines.
        if re.match(r"(\s*#|\s*$)", line):
            continue
        words = line.split()
        if len(words) != 5:
            raise ParseError('Parse error!')
        entry = ViewFileEntry(dir_=words[0],
                              url=words[1],
                              vcs=words[2],
                              branch=words[3],
                              revision=words[4])
        viewfile.entries.append(entry)
    return viewfile

def diff(from_, to):
    """
    Compare two viewfiles and return the difference between the two.

    Returns:
      A dictionary where the keys are directories that have changed and the
      values are a tuple containing the old and new viewfile entries.
    """
    # Create dictionaries of entries (indexed by dir)
    from_dict = {entry.dir: entry for entry in from_.entries}
    to_dict = {entry.dir: entry for entry in to.entries}

    # Find the directories that exist in either viewfile.
    all_dirs = set(from_dict).union(set(to_dict))

    # Find directories that have changed
    changes = {
        dir: (from_dict.get(dir), to_dict.get(dir))
        for dir in all_dirs
        if from_dict.get(dir) != to_dict.get(dir)
    }
    return changes
