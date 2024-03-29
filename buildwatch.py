#! /usr/bin/python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla Build Watch.
#
# The Initial Developer of the Original Code is
#   Dave Townsend <dtownsend@oxymoronical.com>
#
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Nick Thomas <nrthomas@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
#
# Pretty prints a Mozilla build log
#
# How to use:
# - Configuration:
#     OSX requires mk_add_options MOZ_MAKE_FLAGS="-w"
# - When building:
#     make -f client.mk 2>&1 build | tee <logfile> | python /path/to/buildwatch.py
#
# Version history:
# - 1.1.0   Nov 22 2009
#     Support windows and pymake
# - 1.0.1   Nov 22 2009
#     Fix object dir detection and directory entries on Linux
# - 1.0.0   Nov 22 2009
#     Initial implementation. Design, terminal codes and certain regular
#     regular expressions taken from the original gawk script available at
#     http://svn.oxymoronical.com/dave/mozilla/BuildWatch/trunk/buildwatch

import os, sys, re, time
from datetime import datetime
from console import Console

# The Output receives signals during the build process so it can update its
# display.
class ConsoleOutput:
  PENDING = 0
  INPROGRESS = 1
  COMPLETE = 2

  start = None
  fp = None
  console = None
  pos = 0
  tier = None
  dirs = None
  export_counts = None
  libs_counts = None
  failed = False
  lines = []
  throbber = ['-', '\\', '|', '/']
  throbpos = 0

  def __init__(self, fp):
    self.console = Console(fp)
    self.fp = fp
    # Reset the display
    self.console.clear_title()
    self.console.reset_color()
    self.console.clear()
    # Clear the screen and go to the top left
    self.start = datetime.now()
    self.fp.write("Build started at %s\n" % self.start.strftime("%H:%M:%S"))
    self.console.go_right(79)

  def destroy(self):
    now = datetime.now()
    delta = (now - self.start).seconds
    delta, seconds = divmod(delta, 60)
    hours, minutes = divmod(delta, 60)
    if not self.failed:
      self._go_to_end();
      self.console.clear_title()
      self.console.reset_color();
      self.fp.write("\nBuild completed at %s taking %d:%02d:%02d\n\n" % (now.strftime("%H:%M:%S"), hours, minutes, seconds))
    else:
      self.fp.write("\nBuild failed at %s taking %d:%02d:%02d\n\n" % (now.strftime("%H:%M:%S"), hours, minutes, seconds))

  def _go_to_pos(self, pos):
    self._clear_throbber()
    self.console.go_to_pos(pos)
    self.console.go_linehome()

  def _go_to_end(self):
    self._go_to_pos(0)

  def _color_for_state(self, state, count = 0):
    if state == self.COMPLETE:
      return self.console.GREEN
    if state == self.INPROGRESS or count > 0:
      return self.console.YELLOW
    return self.console.RED

  def _print_tier_line(self, export_state, export_count, libs_state, libs_count, name):
    self.console.set_color(self._color_for_state(export_state, export_count))
    self.fp.write("  export ")
    if export_count > 0:
      self.fp.write("[%2s]      " % export_count)
    else:
      self.fp.write("          ")
    self.console.set_color(self._color_for_state(libs_state, libs_count))
    self.fp.write("libs ")
    if libs_count > 0:
      self.fp.write("[%2s]      " % libs_count)
    else:
      self.fp.write("          ")
    self.console.reset_color()
    self.fp.write("%-45s" % name)
    self._draw_throbber()

  def _print_tools_line(self, state, count, name):
    self.console.set_color(self._color_for_state(state, count))
    self.fp.write("  %s " % name)
    if count > 0:
      self.fp.write("[%2s]" % count)
    else:
      self.fp.write("    ")
    self.console.reset_color()
    self.console.go_right(79 - (7 + len(name)))
    self._draw_throbber()

  def _draw_throbber(self):
    self.console.go_left(1)
    self.fp.write(self.throbber[self.throbpos])
    self.throbpos = (self.throbpos + 1) % len(self.throbber)

  def _clear_throbber(self):
    self.console.go_left(1)
    self.fp.write(" ")

  def start_prebuild(self):
    self._go_to_end()
    self.console.reset_color()
    self.fp.write("\nprebuild:\n")

  def start_configure(self, name):
    self._go_to_end()
    self.console.set_title("prebuild %s" % name)
    self.console.set_color(self._color_for_state(self.INPROGRESS, 0))
    self.fp.write("  %s\n" % name)
    self.console.reset_color()
    self.console.go_up(1)
    self.console.go_right(79)
    self._draw_throbber()

  def finish_configure(self, name):
    self.console.go_linehome()
    self.console.set_color(self._color_for_state(self.COMPLETE))
    self.fp.write("  %-77s" % name)
    self.console.reset_color()
    self._draw_throbber()

  def start_tier(self, name, dirs):
    self._go_to_end()
    self.console.reset_color()
    self.fp.write("\ntier %s - %s dirs:\n" % (name, len(dirs)))
    self.tier = name
    self.dirs = dirs
    self.export_counts = dict()
    self.libs_counts = dict()
    for dir in dirs:
      self.export_counts[dir] = 0
      self.libs_counts[dir] = 0
      self._print_tier_line(self.PENDING, 0, self.PENDING, 0, dir)
      self._clear_throbber()
      self.fp.write("\n")
    self.console.go_up(len(dirs))
    self.console.go_right(79)

  def start_exports(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.console.set_title("%s export [%d/%d] %s" % (self.tier, pos + 1, len(self.dirs), dir))
    self._print_tier_line(self.INPROGRESS, self.export_counts[dir], self.PENDING, self.libs_counts[dir], dir)

  def start_export_subdir(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.export_counts[dir] += 1
    self._print_tier_line(self.INPROGRESS, self.export_counts[dir], self.PENDING, self.libs_counts[dir], dir)

  def finish_exports(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self._print_tier_line(self.COMPLETE, self.export_counts[dir], self.PENDING, self.libs_counts[dir], dir)

  def start_libs(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.console.set_title("%s libs [%d/%d] %s" % (self.tier, pos + 1, len(self.dirs), dir))
    self._print_tier_line(self.COMPLETE, self.export_counts[dir], self.INPROGRESS, self.libs_counts[dir], dir)

  def start_libs_subdir(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.libs_counts[dir] += 1
    self._print_tier_line(self.COMPLETE, self.export_counts[dir], self.INPROGRESS, self.libs_counts[dir], dir)

  def finish_libs(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self._print_tier_line(self.COMPLETE, self.export_counts[dir], self.COMPLETE, self.libs_counts[dir], dir)

  def start_tools(self, name, dirs):
    self._go_to_end()
    self.console.reset_color()
    self.fp.write("\ntools tier %s - %s dirs:\n" % (name, len(dirs)))
    self.tier = name
    self.dirs = dirs
    self.libs_counts = dict()
    for dir in dirs:
      self.libs_counts[dir] = 0
      self._print_tools_line(self.PENDING, 0, dir)
      self._clear_throbber()
      self.fp.write("\n")
    self.console.go_up(len(dirs))
    self.console.go_right(79)
    self._draw_throbber()

  def start_tools_dir(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.console.set_title("%s tools [%d/%d] %s" % (self.tier, pos + 1, len(self.dirs), dir))
    self._print_tools_line(self.INPROGRESS, self.libs_counts[dir], dir)

  def start_tools_subdir(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self.libs_counts[dir] += 1
    self._print_tools_line(self.INPROGRESS, self.libs_counts[dir], dir)

  def finish_tools_dir(self, dir):
    pos = self.dirs.index(dir)
    self._go_to_pos(pos - len(self.dirs))
    self._print_tools_line(self.COMPLETE, self.libs_counts[dir], dir)

  def error(self):
    if self.failed:
      return
    self.failed = True
    self._go_to_end();
    self.console.clear_title()
    self.console.reset_color();
    self.fp.write("\n")
    for line in self.lines:
      self.fp.write(line)

  def build_log(self, line):
    self.fp.flush()
    #time.sleep(0.005)
    if self.failed:
      self.fp.write(line)
    else:
      self._draw_throbber()
      if len(self.lines) == 5:
        self.lines.pop(0)
      self.lines.append(line)

# The LogParser parses a log file and sends signals to an Output
class LogParser:
  output = None
  errorreg = re.compile("^g?make(?:\\.py)?\\[\\d\\]: .+ Error \d+$")
  tierreg = re.compile("^tier_([^:]+): (.+)$")
  toolsreg = re.compile("^tools_tier_(.+)$")
  enterreg = None
  donereg = None
  complete = False

  def __init__(self, output):
    self.output = output

  def error(self, fp):
    self.output.error()
    line = fp.readline()
    while line != "":
      self.output.build_log(line)
      line = fp.readline()
    return line

  # Detects the directories in a tier based on makefile generation
  def detect_dirs(self, fp):
    dirparse = re.compile("^g?make(?:\\.py)?\\[\\d+\\]: `(.+)/Makefile' is up to date.$")
    leavedir = re.compile("^g?make(?:\\.py)?\\[\\d+\\]: Leaving directory.*$")
    dirs = []
    line = fp.readline()
    while line != "":
      self.output.build_log(line)
      if self.errorreg.search(line):
        self.error(fp)
        return None
      if self.donereg.search(line):
        self.complete = True
      if leavedir.search(line):
        return dirs
      if dirparse.search(line):
        match = dirparse.search(line)
        dirs.append(match.group(1))
      line = fp.readline()
    return None

  # Parses a full tier
  def parse_tier(self, fp, tier, dirs):
    exports = True
    curdir = None

    def finish_last():
      if curdir:
        if exports:
          self.output.finish_exports(curdir)
        else:
          self.output.finish_libs(curdir)

    libsreg = re.compile("^libs_tier_%s$" % tier)
    self.output.start_tier(tier, dirs)
    line = fp.readline()
    while line != "":
      self.output.build_log(line)
      if self.errorreg.search(line):
        return self.error(fp)
      if self.donereg.search(line):
        self.complete = True
      if self.tierreg.search(line):
        finish_last()
        return line
      if self.toolsreg.search(line):
        finish_last()
        return line
      if libsreg.search(line):
        finish_last()
        curdir = None
        exports = False
      elif self.enterreg.search(line):
        match = self.enterreg.search(line)
        dir = match.group(1)
        if dir in dirs:
          finish_last()
          if exports:
            self.output.start_exports(dir)
          else:
            self.output.start_libs(dir)
          curdir = dir
        elif curdir:
          if exports:
            self.output.start_export_subdir(curdir)
          else:
            self.output.start_libs_subdir(curdir)
      line = fp.readline()
    finish_last()
    return line

  # Parses a tools tier
  def parse_tools(self, fp, tier):
    dirs = self.detect_dirs(fp)

    if dirs is None:
      return ""
    if len(dirs) == 0:
      return fp.readline()
    curdir = None

    def finish_last():
      if curdir:
        self.output.finish_tools_dir(curdir)

    self.output.start_tools(tier, dirs)
    line = fp.readline()
    while line != "":
      self.output.build_log(line)
      if self.errorreg.search(line):
        return self.error(fp)
      if self.donereg.search(line):
        self.complete = True
      if self.tierreg.search(line):
        finish_last()
        return line
      if self.toolsreg.search(line):
        finish_last()
        return line
      if self.enterreg.search(line):
        match = self.enterreg.search(line)
        dir = match.group(1)
        if dir in dirs:
          finish_last()
          self.output.start_tools_dir(dir)
          curdir = dir
        elif curdir:
          self.output.start_tools_subdir(curdir)
      line = fp.readline()
    finish_last()
    return line

  # Parses a build log
  def parse(self, fp):
    try:
      # First parse the configure calls and detect the object directory
      lastconfig = None
      basereg = re.compile("^(?:g?make .*-C (.+)|make\\.py\\[0\\]: Entering directory .(.+)')$")
      mainconfig = re.compile("^Adding configure options from")
      subconfig = re.compile("^configuring in (.+)$")
      line = fp.readline()
      while line != "":
        self.output.build_log(line)
        if self.errorreg.search(line):
          return self.error(fp)
        if mainconfig.search(line):
          self.output.start_prebuild()
          lastconfig = "configure"
          self.output.start_configure(lastconfig)
        elif subconfig.search(line):
          match = subconfig.search(line)
          if lastconfig:
            self.output.finish_configure(lastconfig)
          else:
            self.output.start_prebuild()
          lastconfig = "%s/configure" % match.group(1)
          self.output.start_configure(lastconfig)
        elif basereg.search(line):
          match = basereg.search(line)
          objdir = match.group(1)
          if not objdir:
            objdir = match.group(2)
          separator = "/"
          if not objdir.startswith("/"):
            separator = "\\\\"
            objdir = objdir.replace("\\", "\\\\")
          self.enterreg = re.compile("make(?:\\.py)?\\[\\d+\\]: Entering directory .%s%s(.+).$" % (objdir, separator))
          self.donereg = re.compile("(?:g?make\\[1\\]|make\\.py\\[0\\]): Leaving directory .%s." % objdir)
          break
        line = fp.readline()

      if line == "":
        self.output.destroy()
        return

      if lastconfig:
        self.output.finish_configure(lastconfig)

      # Now parse for the tiers
      line = fp.readline()
      while line != "":
        self.output.build_log(line)
        if self.errorreg.search(line):
          return self.error(fp)
        if self.donereg.search(line):
          self.complete = True
        if self.tierreg.search(line):
          match = self.tierreg.search(line)
          tier = match.group(1)
          dirs = match.group(2).split()
          line = self.parse_tier(fp, tier, dirs)
        elif self.toolsreg.search(line):
          match = self.toolsreg.search(line)
          tier = match.group(1)
          line = self.parse_tools(fp, tier)
        else:
          line = fp.readline()
      if not self.complete:
        self.output.error()
      self.output.destroy()
    except:
      self.output.error()
      self.output.destroy()
      raise

LogParser(ConsoleOutput(sys.stdout)).parse(sys.stdin)
