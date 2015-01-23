# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common functions used for syncing Chrome."""

from __future__ import print_function

import os
import pprint

from chromite.cbuildbot import constants
from chromite.lib import cros_build_lib
from chromite.lib import git
from chromite.lib import osutils

CHROME_COMMITTER_URL = 'https://chromium.googlesource.com/chromium/src'
STATUS_URL = 'https://chromium-status.appspot.com/current?format=json'


def FindGclientFile(path):
  """Returns the nearest higher-level gclient file from the specified path.

  Args:
    path: The path to use. Defaults to cwd.
  """
  return osutils.FindInPathParents(
      '.gclient', path, test_func=os.path.isfile)


def FindGclientCheckoutRoot(path):
  """Get the root of your gclient managed checkout."""
  gclient_path = FindGclientFile(path)
  if gclient_path:
    return os.path.dirname(gclient_path)
  return None


def _GetGclientURLs(internal, rev):
  """Get the URLs and deps_file values to use in gclient file.

  See WriteConfigFile below.
  """
  results = []

  if rev is None or git.IsSHA1(rev):
    # Regular chromium checkout; src may float to origin/master or be pinned.
    url = constants.CHROMIUM_GOB_URL
    if rev:
      url += ('@' + rev)
    # TODO(szager): .DEPS.git will eventually be deprecated in favor of DEPS.
    # When that happens, this could should continue to work, because gclient
    # will fall back to DEPS if .DEPS.git doesn't exist.  Eventually, this
    # code should be cleaned up to stop referring to non-existent .DEPS.git.
    results.append(('src', url, '.DEPS.git'))
    if internal:
      results.append(
          ('src-internal', constants.CHROME_INTERNAL_GOB_URL, '.DEPS.git'))
  elif internal:
    # Internal buildspec: check out the buildspec repo and set deps_file to
    # the path to the desired release spec.
    url = constants.INTERNAL_GOB_URL + '/chrome/tools/buildspec.git'
    results.append(('CHROME_DEPS', url, 'releases/%s/.DEPS.git' % rev))
  else:
    # External buildspec: use the main chromium src repository, pinned to the
    # release tag, with deps_file set to .DEPS.git (which is created by
    # publish_deps.py).
    url = constants.CHROMIUM_GOB_URL + '@refs/tags/' + rev
    results.append(('src', url, '.DEPS.git'))

  return results


def _GetGclientSolutions(internal, rev):
  """Get the solutions array to write to the gclient file.

  See WriteConfigFile below.
  """
  urls = _GetGclientURLs(internal, rev)
  solutions = []
  for (name, url, deps_file) in urls:
    solution = {
        'name': name,
        'url': url,
        'custom_deps': {},
        'custom_vars': {},
    }
    if deps_file:
      solution['deps_file'] = deps_file
    solutions.append(solution)
  return solutions


def _GetGclientSpec(internal, rev):
  """Return a formatted gclient spec.

  See WriteConfigFile below.
  """
  solutions = _GetGclientSolutions(internal=internal, rev=rev)
  result = 'solutions = %s\n' % pprint.pformat(solutions)

  # Horrible hack, I will go to hell for this.  The bots need to have a git
  # cache set up; but how can we tell whether this code is running on a bot
  # or a developer's machine?
  if cros_build_lib.HostIsCIBuilder():
    result += "cache_dir = '/b/git-cache'\n"

  return result

def WriteConfigFile(gclient, cwd, internal, rev):
  """Initialize the specified directory as a gclient checkout.

  For gclient documentation, see:
    http://src.chromium.org/svn/trunk/tools/depot_tools/README.gclient

  Args:
    gclient: Path to gclient.
    cwd: Directory to sync.
    internal: Whether you want an internal checkout.
    rev: Revision or tag to use.
        - If None, use the latest from trunk.
        - If this is a sha1, use the specified revision.
        - Otherwise, treat this as a chrome version string.
  """
  spec = _GetGclientSpec(internal=internal, rev=rev)
  cmd = [gclient, 'config', '--spec', spec]
  cros_build_lib.RunCommand(cmd, cwd=cwd)


def Revert(gclient, cwd):
  """Revert all local changes.

  Args:
    gclient: Path to gclient.
    cwd: Directory to revert.
  """
  cros_build_lib.RunCommand([gclient, 'revert', '--nohooks'], cwd=cwd)


def Sync(gclient, cwd, reset=False):
  """Sync the specified directory using gclient.

  Args:
    gclient: Path to gclient.
    cwd: Directory to sync.
    reset: Reset to pristine version of the source code.
  """
  cmd = [gclient, 'sync', '--verbose', '--nohooks', '--transitive',
         '--with_branch_heads', '--with_tags']

  if reset:
    cmd += ['--reset', '--force', '--delete_unversioned_trees']
  cros_build_lib.RunCommand(cmd, cwd=cwd)