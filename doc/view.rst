=======
view.py
=======

Introduction
============

``view.py`` is a tool for managing collections of git repositories.

A *view* is a git repository containing metadata that lists the other
repositories contained in the view. When a view is cloned with ``view.py``, this
metadata is used to checkout these repositories into subdirectories.

Comparison with git-submodule
=============================

Like git submodules, ``view.py`` lets you manage git repositories in
subdirectories of your repository. However unlike git submodules, ``view.py``
doesn't require an exact revision for each repository. A view can be used to
checkout a repository at the head of a branch. This is useful for managing
collections of repositories that are developed together where you typically want
the latest revision of each repository.

Viewfile format
===============

A view contains a file named ``view.txt`` in the top level directory. This file
is known as a *viewfile*. The viewfile contains a list of viewfile entries where
each viewfile entry is specified on a separate line.

A viewfile entry is a list of five values that specify what to checkout and
where, for example::

  foo git://example.org/path/to/repo.git GIT master HEAD

The fives values are:

1. The subdirectory where the repository should be cloned.
2. The URL of the git remote.
3. The name of the source control system. ``GIT`` is the only currently supported
   source control system.
4. The branch to checkout.
5. The revision to checkout. If the ref is ``HEAD`` then the head of the branch
   is checked out.

Viewfiles can contain blank lines or comments, both of which are ignored. A
comment starts with the hash character, ``#``, and extends to the end of the line.

An example viewfile is shown below::

  # Checkout the head of the master branch
  foo git://example.org/foo GIT master HEAD
  
  # Checkout using a git hash
  bar git://example.org/bar GIT master 59cd37f
  
  # Checkout using a tag
  baz git://example.org/baz GIT release_3_3 release_3_3_0

Subcommands
===========

clone
-----

Views are cloned using the ``clone`` subcommand::

  view.py clone git://example.org/path/to/repo

This creates a new directory and checks out the specified view repository to
that directory. Repositories contained in the view are checked out to
subdirectories of the newly created directory.

pull
----

Once a view has been cloned it can be kept up to date using the ``pull``
subcommand::

  view.py pull

The ``pull`` command must be run in a directory inside the view. It performs a
``git pull`` on the view repository, updating the list of repositories in the
view. Any newly introduced repositories are cloned and each repository is
updated to match the revision and branch specified in the viewfile. Finally a
``git pull`` is performed on any repositories that are tracking the head of a
branch.

status
------

The ``status`` subcommand lists repositories in the view that contain local
changes::

  $ view.py status
  foo: has unpushed changes
  bar: has staged changes
  baz: has unstaged changes

checkout
--------

The ``checkout`` command can be used to checkout a particular revision of the
view::

  # Checkout the release_2_1 branch of the view
  view.py checkout release_2_1
  # Checkout the previous revision of the view
  view.py checkout HEAD^

clean
-----

The ``clean`` command removes all files in the view that are not tracked by
git::

  view.py clean

update
------

The ``update`` command updates each repository in the view to match its entry in
the viewfile without pulling from the view repository::

  view.py update

foreach
-------

The ``foreach`` command is used to run a command in each repository contained in
a view. For example, to stash the changes in each repository::

  # Stash the changes in each repository
  view.py foreach git stash

Pushing changes to a view
=========================

``view.py`` has no dedicated command for pushing changes. To push a change to a
repository use git push inside that repository. To add or remove repositories,
edit the viewfile and commit and push the change.
