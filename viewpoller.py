#!/usr/bin/env python

import argparse
import contextlib
import logging
import os
import StringIO
import subprocess
import sys
import time

import buildbot
from view import gitutils
from view import diff as view_diff
from view import viewfile

VIEW_DIRECTORY = 'view'

log = logging.getLogger(__name__)

def get_remote_head_reference(url, branch='master'):
    """Return the hash of the specified branch on the specified remote URL"""
    output = subprocess.check_output(['git', 'ls-remote', url, '--heads',
                                      branch])
    # TODO Error handling
    return output.split()[0]

def lock_revisions(view):
    """Fill in specific revision for each repository in a view"""
    for entry in view.entries:
        if not entry.has_revision():
            entry.revision = get_remote_head_reference(entry.url, entry.branch)

def is_empty_dir(path):
    """Return whether the path specifies an empty directory"""
    return os.path.isdir(path) and not os.listdir(path)

def read_view_from_repo(repo, rev):
    filename = viewfile.DEFAULT_FILENAME
    cmd = ['git', 'show', ':'.join([rev, filename])]
    view_string = subprocess.check_output(cmd, cwd=repo)
    with contextlib.closing(StringIO.StringIO(view_string)) as f:
        return viewfile.parse(f, filename=filename)

class ViewPoller(object):
    def __init__(self, dir, url, poll_interval=60, branch='master',
                 listener=None):
        self.basedir = dir
        self.viewdir = os.path.join(dir, VIEW_DIRECTORY)
        self.listener = listener
        self.url = url
        self.branch = branch
        self.poll_interval = poll_interval

    def _ensure_view(self):
        if not os.path.exists(self.viewdir):
            log.info("Cloning view into '%s'...", self.viewdir)
            subprocess.check_call(['git', 'clone', '-n', '-q', self.url,
                                   self.viewdir])
        subprocess.check_call(['git', 'config', 'user.email',
                               'noreply@example.com'],
                              cwd=self.viewdir)
        subprocess.check_call(['git', 'config', 'user.name', 'viewpoller.py'],
                              cwd=self.viewdir)

    def run(self):
        remote = 'origin'
        branch = self.branch
        dest_branch = 'versioned/' + branch
        self._ensure_view()
        viewfile_path = os.path.join(self.viewdir, viewfile.DEFAULT_FILENAME)
        while True:
            log.debug("Fetching...")
            subprocess.check_call(['git', 'fetch', '-n', '-p', '-q'],
                                  cwd=self.viewdir)
            hash = gitutils.get_hash(self.viewdir, '/'.join([remote, branch]))
            v = read_view_from_repo(self.viewdir, hash)
            log.debug("Locking revisions...")
            lock_revisions(v)
            entry = viewfile.ViewFileEntry('.unversioned_view', self.url, 'GIT',
                                           branch, hash)
            v.entries.append(entry)
            log.debug("Checking out...")
            is_orphan = False
            if gitutils.branch_exists(self.viewdir, dest_branch, remote=True):
                subprocess.check_call(['git', 'checkout', '-q', '-f',
                                       dest_branch],
                                      cwd=self.viewdir)
                subprocess.check_call(['git', 'reset', '--hard', '-q',
                                       '/'.join([remote, dest_branch])],
                                      cwd=self.viewdir)
            else:
                subprocess.check_call(['git', 'checkout', '-q', '-f',
                                       '--orphan', dest_branch],
                                      cwd=self.viewdir)
                is_orphan = True
            with open(viewfile_path, 'w') as f:
                v.dump(f)
            subprocess.check_call(
                ['git', 'add', viewfile.DEFAULT_FILENAME], cwd=self.viewdir)
            if is_orphan or gitutils.has_staged_changes(self.viewdir):
                log.info("Change detected")
                msg = 'Automatic commit'
                subprocess.check_call(['git', 'commit', '-m', msg],
                                      cwd=self.viewdir)
                subprocess.check_call(['git', 'push', '-q', remote,
                                       dest_branch],
                                      cwd=self.viewdir)
                if self.listener:
                    self.listener(self.url, dest_branch,
                                  gitutils.get_hash(self.viewdir, ref='HEAD^'),
                                  gitutils.get_hash(self.viewdir, ref='HEAD'))
            else:
                log.debug("No changes")
            time.sleep(self.poll_interval)

def create_poller(args):
    dir = os.path.abspath(args.directory)
    url = args.url
    branch = args.branch
    poll_interval = args.poll_interval
    buildbot_master = args.buildbot_master
    cache_dir = os.path.join(dir, 'cache')

    differ = view_diff.ViewDiffer(cache_dir=cache_dir)
    notifier = buildbot.BuildbotNotifier(master=buildbot_master)
    def listener(view_url, view_branch, old_hash, new_hash):
        commits = differ.get_commits(view_url, view_branch, old_hash, new_hash)
        notifier.notify(commits)

    return ViewPoller(dir, url=url, branch=branch, poll_interval=poll_interval,
                      listener=listener)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    # Create the top level parser.
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('url')
    parser.add_argument('-b', '--branch', default='master')
    parser.add_argument('--poll-interval', metavar='N', type=int,
                               default=60)
    parser.add_argument('--buildbot-master')

    args = parser.parse_args()

    create_poller(args).run()
    return 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
    sys.exit(main())
