"""Library for notifying a buildbot master of changes"""

import subprocess

class BuildbotNotifier(object):
    """
    Class for notifying a buildmaster of changes.

    The buildbot sendchange command is used to send the changes. The buildbot
    command is expected to be available on the current path.

    Attributes:
        master: Location of the buildmaster's PBListener in the form host:port
        auth: Authentication to use in the form username:password
    """
    def __init__(self, master=None, auth=None):
        self.master = master
        self.auth = auth

    def notify(self, commits):
        """Notify the buildmaster of the specified commits"""
        for commit in commits:
            cmd = ['buildbot', 'sendchange']
            def add_option(prefix, value):
                if value is not None:
                    cmd.append('='.join([prefix, value]))
            def add_property(name, value):
                if value is not None:
                    cmd.append('--property={}:{}'.format(name, value))
            add_option('--master', self.master)
            add_option('--auth', self.auth)
            add_option('--who', commit.who)
            add_option('--repository', commit.repository)
            add_option('--branch', commit.branch)
            add_option('--revision', commit.revision)
            add_option('--comments', commit.comments)
            add_option('--when', commit.when)
            add_property('view_repository', commit.view_repository)
            add_property('view_branch', commit.view_branch)
            cmd.extend(commit.filenames)
            subprocess.check_call(cmd)
