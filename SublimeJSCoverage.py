import os
import sys
import json
import fnmatch

import sublime
import sublime_plugin

debug = lambda *args: sys.stdout.write("\n%s" % " ".join(map(str, args)))

REGION_KEY_COVERED = 'SublimeJSCoverageCovered'
REGION_KEY_UNCOVERED = 'SublimeJSCoverageUnCovered'

def getCoverageDir():
    settings = sublime.load_settings("JSCoverage.sublime-settings")

    return settings.get("coverageDir") or 'coverage'

def find_project_root(file_path):
    """
        Project Root is defined as the parent directory
        that contains a directory called 'coverage'
    """
    if os.access(os.path.join(file_path, getCoverageDir()), os.R_OK):
        return file_path
    parent, current = os.path.split(file_path)
    if current:
        return find_project_root(parent)


def find_coverage_filename(coverage_dir):
    """
        Returns latest coverage json for specifed file or None if cannot find it
        in specifed coverage direcotry
    """
    files = []
    for root, dirnames, filenames in os.walk(coverage_dir):
    	for filename in fnmatch.filter(filenames, '*.json'):
      		files.append(os.path.join(root, filename))
    debug("discovered files: " + ",".join(files or []))
    getmtime = lambda key: os.path.getmtime(os.path.join(coverage_dir, key))
    coverage_file_name = None
    if files:
        files.sort(key=getmtime, reverse=True)
        coverage_file_name = files.pop(0)

    return coverage_file_name


def read_coverage_report(file_path):
    with open(file_path, 'r', encoding='utf-8') as coverage_file:
        try:
            coverage_json = json.load(coverage_file)
            return coverage_json
        except IOError:
            return None

class ShowJsCoverageCommand(sublime_plugin.TextCommand):

    """
        Highlight uncovered lines in the current file
        based on a previous coverage run.
    """

    def run(self, edit):
        view = self.view
        # get name of currently opened file
        filename = view.file_name()
        if not filename:
            return
        project_root = find_project_root(filename)

        if not project_root:
            if view.window():
                sublime.status_message("Could not find coverage directory.")
            return

        relative_filename = filename.replace(project_root + "/", "")
        coverage_dir = os.path.join(project_root, getCoverageDir())
        coverage_filename = find_coverage_filename(coverage_dir)

        debug("Display js coverage report for file", filename)
        debug("project_root", project_root)
        debug("relative_filename", relative_filename)
        debug("coverage_dir", coverage_dir)
        debug("coverage_filename", coverage_filename)

        if not coverage_filename:
            if view.window():
                return sublime.status_message(
                    "Can't find the coverage file in project root: " + str(project_root))
            return

        # Clean up
        view.erase_status("SublimeJSCoverage")
        view.erase_regions("SublimeJSCoverage")

        outlines = {}

        report = read_coverage_report(
            os.path.join(coverage_dir, coverage_filename))
        if report is None:
            if view.window():
                sublime.status_message(
                    "Can't read coverage report from file: " + str(coverage_filename))
            return
        debug("Found report for the following number of files: " + str(len(report)))

        if not report:
            view.set_status("SublimeJSCoverage", "UNCOVERED!")
            if view.window():
                sublime.status_message(
                    "Can't find the coverage json file in project root: " + project_root)

        for tested_file_name in report:
            tested_file_name2 = tested_file_name.replace("./", "")
            if not tested_file_name2.endswith(relative_filename):
                continue
            debug("Found test report for file " + str(relative_filename))

            fileReport = report.get(tested_file_name)

            lines = fileReport.get("l")

            for lineNumber in lines:
                lineExecutionTimes = int(lines.get(lineNumber))

                outlines[lineNumber] = lineExecutionTimes > 0

        badOutlines = []
        goodOutlines = []

        for lineNumber in outlines:
            region = view.full_line(view.text_point(int(lineNumber) - 1, 0))

            if outlines[lineNumber]:
                goodOutlines.append(region)
            else:
                badOutlines.append(region)

        if goodOutlines:
            view.add_regions(REGION_KEY_COVERED, goodOutlines,
                'markup.inserted.diff', 'dot', sublime.HIDDEN)

        if badOutlines:
            view.add_regions(REGION_KEY_UNCOVERED, badOutlines,
                'markup.deleted.diff', 'dot', sublime.DRAW_OUTLINED)

class ClearJsCoverageCommand(sublime_plugin.TextCommand):

    """
        Remove highlights created by plugin.
    """

    def run(self, edit):
        view = self.view
        view.erase_regions(REGION_KEY_COVERED)
        view.erase_regions(REGION_KEY_UNCOVERED)
