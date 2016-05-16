#!/usr/bin/env python

"""
Command line tool for working with views.

A view is a collection of repositories and a directory structure to use when
checking out those repositories.
"""

from __future__ import print_function
import argparse
import os
import sys
import subprocess

from view import viewfile
from view import gitutils

def is_empty_dir(path):
    """Return whether the path specifies an empty directory"""
    return os.path.isdir(path) and not os.listdir(path)

class UpdateError(Exception):
    """Raise when a repository can't be updated"""
    pass

def clean_repos(viewdir):
    """Clean all repositories in a view"""
    def get_clean_excludes(entry, entries):
        excludes = []
        for other in entries:
            if other.dir.startswith(entry.dir + "/"):
                excludes.append(other.dir[len(entry.dir)+1:])
        return excludes

    # Read viewfile
    filename = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    with open(filename, 'r') as f:
        view = viewfile.parse(f, filename)

    # Clean viewdir
    cmd = ['git', 'clean','-d','-f','-f','-x']
    for entry in view.entries:
        cmd += ['-e',entry.dir + '/']
    subprocess.check_call(cmd, cwd=viewdir)

    # Clean repositories
    for entry in view.entries:
        repodir = os.path.join(viewdir, entry.dir)
        if not os.path.exists(repodir):
            print("Skipping cleaning {} (not found)".format(repodir))
            continue
        excludes = get_clean_excludes(entry, view.entries)
        cmd = ['git', 'clean','-d','-f','-f','-x']
        for exclude in excludes:
            cmd += ['-e',exclude + '/']
        subprocess.check_call(cmd, cwd=repodir)

def update_repo(viewdir, viewfile_entry, old_viewfile_entry, force):
    """
    Update repository to the latest revision specified in the viewfile entry.

    If the repository doesn't exist locally it will be cloned, otherwise it
    will be updated so long as it doesn't contain local changes.
    """
    if force:
        force_option = ['-f']
    else:
        force_option = []
    entry = viewfile_entry
    repodir = os.path.join(viewdir, entry.dir)
    if os.path.exists(repodir):
        # Check there are no local changes
        if force:
            origin = gitutils.get_remote(repodir)
            if origin != viewfile_entry.url:
                raise UpdateError('has changed origin')
        else:
            status = get_repository_status(repodir, old_viewfile_entry)
            if not isinstance(status, StatusUnchanged):
                raise UpdateError(status.report())
        print('Pulling {}...'.format(entry.dir))
        subprocess.check_call(['git', 'remote', 'set-url', 'origin', entry.url],
                              cwd=repodir)
        if entry.has_revision():
            if not gitutils.commit_exists(repodir, entry.revision):
                subprocess.check_call(['git', 'fetch'], cwd=repodir)
            cmd = ['git', 'checkout', '-q'] + force_option + [entry.revision]
            subprocess.check_call(cmd, cwd=repodir)
        else:
            subprocess.check_call(['git', 'fetch'], cwd=repodir)
            cmd = ['git', 'checkout', '-q'] + force_option + [entry.branch]
            subprocess.check_call(cmd, cwd=repodir)
            subprocess.check_call(['git', 'reset', '--hard','-q',
                                   'origin/'+entry.branch],
                                  cwd=repodir)
    else:
        print('Cloning {}...'.format(entry.dir))
        subprocess.check_call(['git', 'clone', '-n', '-q', entry.url,
                               entry.dir], cwd=viewdir)
        if entry.has_revision():
            subprocess.check_call(['git', 'checkout', '-q', entry.revision],
                                  cwd=repodir)
        else:
            subprocess.check_call(['git', 'checkout', '-q', entry.branch],
                                  cwd=repodir)
    subprocess.check_call(['git', 'submodule', '--quiet', 'update', '--init',
                           '--recursive'], cwd=repodir)

def update_repos(viewdir, old_view=None, force=False):
    """Update all repositories in a view"""
    # Read viewfile
    filename = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    with open(filename, 'r') as f:
        view = viewfile.parse(f, filename)
    old_entries = {entry.dir: entry for entry in view.entries}
    if old_view is not None:
        old_entries.update({entry.dir: entry for entry in old_view.entries})

    # TODO sort so that, in the case of nested repositories, parent repositories
    # are cloned before child directories.

    # Update repositories
    errors = []
    for entry in view.entries:
        try:
            update_repo(viewdir, entry, old_entries[entry.dir], force)
        except UpdateError as error:
            errors.append((entry.dir, error))
    if errors:
        print('\nThe following repositories were not updated:')
        for (dir_, error) in errors:
            print('{}: {}'.format(dir_, str(error)))

def clone_command(args):
    """Clone a view into a new directory"""
    viewdir = args.directory
    if viewdir is None:
        viewdir = gitutils.get_humanish_name(args.repository)
    if os.path.exists(viewdir) and not is_empty_dir(viewdir):
        raise Exception('dir exists and is not an empty directory')

    url = args.repository
    view_basename = os.path.basename(viewdir)
    print('Cloning {}...'.format(view_basename))
    if args.branch:
        subprocess.check_call(['git', 'clone', '-b', args.branch, '-q', url,
                               viewdir])
    else:
        subprocess.check_call(['git', 'clone', '-q', url, viewdir])

    update_repos(viewdir)

def walk_up(current):
    """Generator for walking up a directory structure"""
    current = os.path.realpath(current)
    yield current

    parent = os.path.realpath(os.path.join(current, '..'))

    if parent == current:
        return

    for dir_ in walk_up(parent):
        yield dir_

def is_view_directory(path):
    """Return whether a path is a directory containing a view"""
    return os.path.isfile(os.path.join(path, viewfile.DEFAULT_FILENAME))

def find_enclosing_view(top='.'):
    """Find the innermost parent directory containing a view."""
    for dir_ in walk_up(top):
        if is_view_directory(dir_):
            return dir_

class NotInViewError(Exception):
    """Raise if a directory is not contained inside view"""
    pass

def find_enclosing_view_checked(top='.'):
    """
    Find the innermost parent directory containing a view.

    Raises:
        NotInViewError: If the specified directory is not contained in a view.
    """
    viewdir = find_enclosing_view(top)
    if viewdir is None:
        raise NotInViewError()
    return viewdir

def report_removed_repos(old_viewfile, new_viewfile):
    changes = viewfile.diff(old_viewfile, new_viewfile)
    removed = [dir_ for (dir_, (_, new)) in changes.iteritems() if new is None]
    if removed:
        print('\nThe following repositories are no longer in the view' +
              ' and can be deleted:')
        for dir_ in removed:
            print(dir_)

def update_command(args):
    """Update repositories in a view"""
    viewdir = find_enclosing_view_checked()
    update_repos(viewdir)

def checkout_command(args):
    """Checkout a revision to the working tree"""
    viewdir = find_enclosing_view_checked()
    revision = args.revision
    viewfile_name = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    view_basename = os.path.basename(viewdir)

    with open(viewfile_name, 'r') as f:
        old_viewfile = viewfile.parse(f)

    subprocess.check_call(['git', 'checkout', '-q', args.revision], cwd=viewdir)

    with open(viewfile_name, 'r') as f:
        new_viewfile = viewfile.parse(f)

    update_repos(viewdir, old_viewfile, force = args.force)

    report_removed_repos(old_viewfile, new_viewfile)

def clean_command(args):
    """Clean repositories in a view"""
    viewdir = find_enclosing_view_checked()
    clean_repos(viewdir)

def pull_command(args):
    """Pull changes to a view"""
    viewdir = find_enclosing_view_checked()
    viewfile_name = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    view_basename = os.path.basename(viewdir)

    with open(viewfile_name, 'r') as f:
        old_viewfile = viewfile.parse(f)

    print('Pulling {}...'.format(view_basename))
    subprocess.check_call(['git', 'pull', '-q', '--ff-only'], cwd=viewdir)

    with open(viewfile_name, 'r') as f:
        new_viewfile = viewfile.parse(f)

    update_repos(viewdir, old_viewfile)

    report_removed_repos(old_viewfile, new_viewfile)

class StatusUnchanged(object):
    """A status that indicates that no local changes are present."""
    def report(self):
        """Describe the status as a string."""
        return 'has no changes'

class StatusChanged(object):
    """A status that indicates that local changes are present."""
    def __init__(self, msg):
        self.msg = msg

    def report(self):
        """Describe the status as a string."""
        return self.msg

def get_repository_status(path, viewfile_entry):
    """Return a status indicating whether the repository has local changes"""
    try:
        origin = gitutils.get_remote(path)
        if origin != viewfile_entry.url:
            return StatusChanged('has changed origin')
        revision = gitutils.get_hash(path)
        if viewfile_entry.has_revision():
            if revision != viewfile_entry.revision:
                return StatusChanged('has changed revision')
        else:
            branch = gitutils.get_branch(path)
            if branch != viewfile_entry.branch:
                return StatusChanged('has changed branch')
            if revision != gitutils.get_hash(path, '/'.join(['origin', branch])):
                return StatusChanged('has unpushed changes')
        if gitutils.has_staged_changes(path):
            return StatusChanged('has staged changes')
        if gitutils.has_unstaged_changes(path):
            return StatusChanged('has unstaged changes')
    except subprocess.CalledProcessError:
        return StatusChanged('failed to get status')
    else:
        return StatusUnchanged()

def status_command(args):
    """Show repositories that have local changes"""
    viewdir = find_enclosing_view_checked()
    filename = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    with open(filename, 'r') as f:
        view = viewfile.parse(f, filename)
    had_change = False
    for entry in view.entries:
        repodir = os.path.join(viewdir, entry.dir)
        if not os.path.exists(repodir):
            continue
        status = get_repository_status(repodir, entry)
        if isinstance(status, StatusChanged):
            print('{}: {}'.format(entry.dir, status.report()))
            had_change = True
    if not had_change:
        print('View has no local changes')

def foreach_command(args):
    """Run a command in each repository in the view"""
    viewdir = find_enclosing_view_checked()
    filename = os.path.join(viewdir, viewfile.DEFAULT_FILENAME)
    with open(filename, 'r') as f:
        view = viewfile.parse(f, filename)
    for entry in view.entries:
        repodir = os.path.join(viewdir, entry.dir)
        if not os.path.exists(repodir):
            continue
        status = subprocess.call(args.cmd, cwd=repodir)
        if status != 0:
            print('Command failed with exit status', status)

def print_error(*objs):
    """Print an error message to stderr."""
    print('error:', *objs, file=sys.stderr)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    # Create the top level parser.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands')

    # Create the parser for the checkout command
    parser_checkout = subparsers.add_parser('checkout',
                                         help=checkout_command.__doc__)
    parser_checkout.add_argument('-f', '--force', action='store_true',
        help='force the checkout (remove local modifications)')
    parser_checkout.add_argument('revision', help='The revision to checkout')
    parser_checkout.set_defaults(func=checkout_command)

    # Create the parser for the clean command
    parser_clean = subparsers.add_parser('clean', help=clean_command.__doc__)
    parser_clean.set_defaults(func=clean_command)

    # Create the parser for the clone command
    parser_clone = subparsers.add_parser('clone', help=clone_command.__doc__)
    parser_clone.add_argument('repository', help='The repository to clone from')
    parser_clone.add_argument(
      'directory', nargs='?',
      help='The name of the new directory to clone into')
    parser_clone.add_argument(
      '-b', '--branch', help='The name of the branch to clone')
    parser_clone.set_defaults(func=clone_command)

    # Create the parser for the foreach command
    parser_foreach = subparsers.add_parser('foreach',
                                           help=foreach_command.__doc__,
                                           prefix_chars=' ')
    parser_foreach.add_argument('cmd', nargs='+', help='The command to run')
    parser_foreach.set_defaults(func=foreach_command)

    # Create the parser for the pull command
    parser_pull = subparsers.add_parser('pull', help=pull_command.__doc__)
    parser_pull.set_defaults(func=pull_command)
 
    # Create the parser for the status command
    parser_status = subparsers.add_parser('status', help=status_command.__doc__)
    parser_status.set_defaults(func=status_command)

    # Create the parser for the update command
    parser_update = subparsers.add_parser('update', help=update_command.__doc__)
    parser_update.set_defaults(func=update_command)

    args = parser.parse_args()
    try:
        args.func(args)
    except NotInViewError:
        print_error('not a view (or a subdirectory of a view)')
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
