""" Library for listing changes to a view"""

import base64
import contextlib
import os
import shutil
import StringIO
import subprocess
import tempfile

from view import gitutils
from view import viewfile

class Commit(object):
    """
    A class describing a commit.

    Attributes:
      filenames: A list of filenames affected by the commit.
      who: The author of the commit.
      repository: The respository the commit applies to.
      branch: The branch the commit applies to.
      revision: The revision after the commit.
      comments: The commit message for the commit.
      when: The UNIX timestamp of the commit.
    """
    def __init__(self, filenames=None, who=None, repository=None, branch=None,
                 revision=None, comments=None, when=None, view_repository=None,
                 view_branch=None):
        if filenames is None:
            filenames = []
        self.filenames = filenames
        self.who = who
        self.repository = repository
        self.branch = branch
        self.revision = revision
        self.comments = comments
        self.when = when
        self.view_repository = view_repository
        self.view_branch = view_branch

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)

def read_view_from_repo(repo, rev):
    """
    Read a viewfile from a repository without affecting the working tree.

    This function will work even with bare git repositories.
    """
    filename = viewfile.DEFAULT_FILENAME
    cmd = ['git', 'show', ':'.join([rev, filename])]
    view_string = subprocess.check_output(cmd, cwd=repo)
    with contextlib.closing(StringIO.StringIO(view_string)) as f:
        return viewfile.parse(f, filename=filename)

class ViewDiffer(object):
    """
    A class that is used to list changes made to a view.

    This class automatically checks out repositories in order to get commit
    information. Checked out respositories are not deleted immediately, instead
    they are cached in a cache directory, speeding up subsequent queries.
    """
    def __init__(self, cache_dir=None):
        remove_cache = False
        if cache_dir is None:
            cache_dir = tempfile.mkdtemp()
            remove_cache = True
        else:
            remove_cache = False
        self._cache_dir = cache_dir
        self._remove_cache = remove_cache

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._remove_cache:
            shutil.rmtree(self._cache_dir, ignore_errors=True)

    def _repo_cache_path(self, url):
        """Return the path for a respository in the cache directory"""
        return os.path.join(self._cache_dir, base64.urlsafe_b64encode(url))

    def _ensure_repo(self, url, required_hashes=None):
        """
        Ensure the specified repository exists in the cache directory

        Args:
          url: The URL of the repository
          required_hashes: The list of hashes that are required to exist in the
            repository.
        """
        if required_hashes is None:
            required_hashes = []
        path = self._repo_cache_path(url)
        # Nothing to do if the hashes are already present
        if os.path.exists(path) and \
           gitutils.commits_exist(path, required_hashes):
            return path

        # Otherwise try updating the existing repo.
        if os.path.exists(path):
            try:
                cmd = ['git', 'fetch', '-n', '-p', '-q']
                subprocess.check_call(cmd, cwd=path)
                if gitutils.commits_exist(path, required_hashes):
                    return path
            except subprocess.CalledProcessError:
                pass

        # Otherwise clone the repo.
        shutil.rmtree(path, ignore_errors=True)
        cmd = ['git', 'clone', '-q', '--bare', url, path]
        subprocess.check_call(cmd)
        return path

    def _get_repo_commits(self, url, old_hash, new_hash):
        """ Get a list of commits made to a repository between two hashes"""
        repo = self._ensure_repo(url, [old_hash, new_hash])
        cmd = ['git', 'log', '--format=%H', new_hash, '^' + old_hash]
        commits = subprocess.check_output(cmd, cwd=repo).split()
        # Process oldest change first
        commits.reverse()
        return commits

    def get_commit_hashes(self, view_url, view_branch, view_old_hash,
                          view_new_hash):
        """
        Return a list of commits made to repositories in the view.

        Args:
          view_url: The URL of the view.
          view_branch: The path of the view.
          old_hash: The hash of the view to compare from.
          new_hash: The hash of the view to compare to.

        Returns: A list of tuples of the form (url, branch, commit)
          where url and branch are the URL and branch of the repository that
          the commit applies to and hash is the hash of the commit.
        """
        repo = self._ensure_repo(view_url, [view_old_hash, view_new_hash])
        old_view = read_view_from_repo(repo, view_old_hash)
        new_view = read_view_from_repo(repo, view_new_hash)
        changes = viewfile.diff(old_view, new_view)

        def is_same_branch(a, b):
            return a is not None and b is not None and \
                (a.vcs, a.url, a.branch) == (b.vcs, b.url, b.branch)

        updated = [(old.url, old.branch, old.revision, new.revision)
                   for (_, (old, new)) in changes.iteritems()
                   if is_same_branch(old, new)]
        updated.append((view_url, view_branch, view_old_hash, view_new_hash))

        commits = []
        for (url, branch, old_hash, new_hash) in updated:
            repo_commits = self._get_repo_commits(url, old_hash, new_hash)
            commits.extend([(url, branch, commit) for commit in repo_commits])
        return commits

    def get_commits(self, view_url, view_branch, old_hash, new_hash):
        """
        Return detailed information on commits made to repositories in the view.

        Args:
          view_url: The URL of the view.
          view_branch: The path of the view.
          old_hash: The hash of the view to compare from.
          new_hash: The hash of the view to compare to.

        Returns: A list of Commit objects.
        """

        def _get_commit_info(url, branch, hash_):
            """Create a Commit object using information from a respository."""
            path = self._repo_cache_path(url)

            def read_git_log(format_string):
                cmd = ['git', 'log', '--no-walk', '--format=' + format_string,
                       hash_, '--']
                return subprocess.check_output(cmd, cwd=path)

            def read_changed_files():
                cmd = ['git', 'log', '--name-only', '--no-walk', '--format=%n',
                       hash_, '--']
                files = subprocess.check_output(cmd, cwd=path).splitlines()
                files = [line for line in files if line]
                return files

            filenames = read_changed_files()
            who = read_git_log('%aN <%aE>')
            comments = read_git_log('%s%n%b')
            when = read_git_log('%ct')
            is_view_commit = (url, branch) == (view_url, view_branch)
            parent_url = None if is_view_commit else view_url
            parent_branch = None if is_view_commit else view_branch
            return Commit(
                filenames=filenames,
                who=who,
                comments=comments,
                repository=url,
                branch=branch,
                revision=hash_,
                when=when,
                view_repository = parent_url,
                view_branch = parent_branch)

        hashes = self.get_commit_hashes(view_url, view_branch, old_hash,
                                        new_hash)
        commits = [_get_commit_info(url, branch, hash_)
                   for (url, branch, hash_) in hashes]
        return commits
