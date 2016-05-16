"""Utility functions for operating on GIT repositories"""

import os
import subprocess
import re

def get_remote(repo, name='origin'):
    """Return the URL of the specified remote."""
    config_name = 'remote.{}.url'.format(name)
    return subprocess.check_output(['git', 'config', '--get',
                                    config_name], cwd=repo).rstrip()

def get_hash(repo, ref='HEAD'):
    """Return the git hash of the specified git reference."""
    return subprocess.check_output(['git', 'rev-parse', '--verify', ref],
                                   cwd=repo).rstrip()

def get_branch(repo, ref='HEAD'):
    """Return the branch the specified git reference is on."""
    return subprocess.check_output(['git', 'rev-parse', '--verify',
                                    '--abbrev-ref', ref], cwd=repo).rstrip()

def branch_exists(repo, branch, remote=False):
    """Return whether the specified branch exists."""
    ref = 'refs/remotes/origin/' + branch if remote else 'refs/heads/' + branch
    return subprocess.call(['git', 'show-ref', '-q', '--verify', ref],
                           cwd=repo) == 0

def has_staged_changes(repo):
    """Return whether there are changes staged in the index."""
    return subprocess.call(['git', 'diff-index', '--cached', '--quiet', 'HEAD'],
                           cwd=repo) != 0

def has_unstaged_changes(repo):
    """Return whether there are unstaged changes in the working tree."""
    subprocess.check_call(['git', 'update-index', '-q', '--ignore-submodules',
                           '--refresh'], cwd=repo)
    return subprocess.call(['git', 'diff-index', '--quiet', 'HEAD'],
                           cwd=repo) != 0

def commit_exists(repo, commit):
    """Return whether a commit exists in a repository."""
    cmd = ['git', 'cat-file', '-t', commit]
    try:
        devnull = open(os.devnull, 'wb')
        output = subprocess.check_output(cmd, cwd=repo,
                                         stderr=devnull)
        return output.rstrip() == 'commit'
    except subprocess.CalledProcessError:
        return False

def commits_exist(repo, commits):
    """
    Return whether all of a list of commits exist in a repository.
    """
    for commit in commits:
        if not commit_exists(repo, commit):
            return False
    return True

def get_humanish_name(url):
    """
    Return the 'humanish' part of a git repository's URL.

    A 'humanish' name is the name of the directory git clone would checkout the
    repository to if no destination directory is specified.
    """
    name = re.sub(r'/$', '', url)
    name = re.sub(r':*/*\.git$', '', name)
    name = re.sub(r'.*[/:]', '', name)
    return name
