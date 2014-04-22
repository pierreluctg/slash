# pylint: disable=import-error,no-name-in-module
import itertools
import sys

from py.io import TerminalWriter

from .._compat import iteritems
from ..log import VERBOSITIES
from ..utils.iteration import iteration
from ..utils.python import wraps
from .reporter_interface import ReporterInterface


def from_verbosity(level):
    def decorator(func):
        @wraps(func)
        def new_func(self, *args, **kwargs):
            if self._level <= level:  # pylint: disable=protected-access
                return func(self, *args, **kwargs)

        return new_func
    return decorator

class ConsoleReporter(ReporterInterface):

    def __init__(self, level, stream=sys.stderr):
        super(ConsoleReporter, self).__init__()
        self._level = level
        self._stream = stream
        self._terminal = TerminalWriter(file=stream)

    def _is_verbose(self, level):
        return self._level <= level

    @from_verbosity(VERBOSITIES.ERROR)
    def report_session_start(self, session):
        self._terminal.sep("=", "Session starts".format(self._level), white=True, bold=True)

    def report_session_end(self, session):

        if self._level > VERBOSITIES.WARNING:
            self._terminal.write("\n")  # for concise outputs we need to break the sequence of dots...

        if self._level <= VERBOSITIES.ERROR:
            self._report_failures(session)
            self._report_errors(session)
        elif self._level <= VERBOSITIES.CRITICAL:
            self._report_failures_and_errors_concise(session)

        msg = "Session ended."
        kwargs = {"bold": True}
        if session.results.is_success():
            kwargs.update(green=True)
        else:
            kwargs.update(red=True)
            msg += " {0} failures, {1} errors.".format(session.results.get_num_failures(), session.results.get_num_errors())

        msg += " Total duration: {0}".format(self._format_duration(session.duration))
        self._terminal.sep("=", msg, **kwargs)  # pylint: disable=star-args

    def _report_failures(self, session):
        self._report_error_objects("FAILURES", session.results.iter_all_failures(), "F")

    def _report_errors(self, session):
        self._report_error_objects("ERRORS", session.results.iter_all_errors(), "E")

    def _report_error_objects(self, title, iterator, marker):
        self._terminal.sep("=", title)
        for result, errors in iterator:
            location = self._get_location(result)
            for error in errors:
                self._terminal.sep("_", location)
                self._report_error(error, marker)

    def _report_failures_and_errors_concise(self, session):
        for result in session.results.iter_all_results():
            if result.get_errors() or result.get_failures():
                self._terminal.write(self._get_location(result))
                self._terminal.write(":")
                if result.get_errors():
                    self._terminal.write(" {0} errors".format(len(result.get_errors())))
                if result.get_failures():
                    self._terminal.write(" {0} failures".format(len(result.get_failures())))
                self._terminal.write("\n")

    def _get_location(self, result):
        return str(result.test_metadata.fqn) if result.test_metadata else "**global**"

    def _report_error(self, error, marker):
        line = ""
        if not error.traceback:
            frames = []
        elif self._level > VERBOSITIES.WARNING:
            frames = [error.traceback.frames[-1]]
        else:
            frames = error.traceback.frames
        for frame_iteration, frame in iteration(frames):
            if not frame_iteration.first:
                self._terminal.sep("- ")
            line = ""
            self._write_frame_locals(frame)
            self._write_frame_code(frame)
            if frame_iteration.last:
                self._terminal.write(marker, red=True, bold=True)
                self._terminal.write("".join(itertools.takewhile(str.isspace, line)))
                self._terminal.write(error.message, red=True, bold=True)
                self._terminal.write("\n")
            self._terminal.write("{0}:{1}:\n".format(frame.filename, frame.lineno))

    @from_verbosity(VERBOSITIES.WARNING)
    def _write_frame_locals(self, frame):
        if not frame.locals and not frame.globals:
            return
        for index, (name, value) in enumerate(itertools.chain(iteritems(frame.locals), iteritems(frame.globals))):
            if index > 0:
                self._terminal.write(", ")
            self._terminal.write("{0}: ".format(name), cyan=True, blink=True)
            self._terminal.write(value["value"])
        self._terminal.write("\n\n")

    def _write_frame_code(self, frame):
        if frame.code_string:
            if self._level <= VERBOSITIES.WARNING:
                code_lines = frame.code_string.splitlines()
            else:
                code_lines = [frame.code_line]
            line = ""
            for line_iteration, line in iteration(code_lines):
                if line_iteration.last:
                    self._terminal.write(">", white=True, bold=True)
                else:
                    self._terminal.write(" ")
                self._terminal.write(line, white=True, bold=True)
                self._terminal.write("\n")


    @from_verbosity(VERBOSITIES.WARNING)
    def report_file_start(self, filename):
        self._file_failed = False
        self._file_has_skips = False
        self._terminal.write(filename)
        self._terminal.write(" ")

    @from_verbosity(VERBOSITIES.WARNING)
    def report_file_end(self, filename):
        self._terminal.write("  ")
        if self._file_failed:
            self._terminal.line("FAIL", red=True)
        elif self._file_has_skips:
            self._terminal.line("PASS", yellow=True)
        else:
            self._terminal.line("PASS", green=True)

    def report_test_success(self, test, result):
        self._terminal.write(".")

    def report_test_skip(self, test, result):
        self._terminal.write("s", yellow=True)
        self._file_has_skips = True

    def report_test_error(self, test, result):
        self._file_failed = True
        self._terminal.write("E", red=True)

    def report_test_failure(self, test, result):
        self._file_failed = True
        self._terminal.write("F", red=True)

    def _format_duration(self, duration):
        seconds = duration % 60
        duration /= 60
        minutes = duration % 60
        hours = duration / 60
        return "{0:02}:{1:02}:{2:02}".format(int(hours), int(minutes), int(seconds))