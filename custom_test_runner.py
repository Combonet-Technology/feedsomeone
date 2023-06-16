import os
import shutil

import xmlrunner
from django.conf import settings
from django.test.runner import DiscoverRunner

from ext_libs.slack.api import send_slack_message
from parse_test_results import build_xml_report, combine_xml


class TestRunner(DiscoverRunner):

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        xml_result = []
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        databases = self.get_databases(suite)
        verbosity = getattr(settings, 'TEST_OUTPUT_VERBOSE', 1)
        if isinstance(verbosity, bool):
            verbosity = (1, 2)[verbosity]
        descriptions = getattr(settings, 'TEST_OUTPUT_DESCRIPTIONS', False)
        output = getattr(settings, 'TEST_OUTPUT_DIR', '.')
        # Verify that output is not the current directory
        if output != '.':
            # Delete existing output folder
            if os.path.exists(output):
                shutil.rmtree(output)

        with self.time_keeper.timed('Total database setup'):
            old_config = self.setup_databases(aliases=databases)
        run_failed = False
        try:
            self.run_checks(databases)
            xml_result = xmlrunner.XMLTestRunner(
                verbosity=verbosity, descriptions=descriptions,
                output=output).run(suite)
        except Exception:
            run_failed = True
            raise
        finally:
            try:
                with self.time_keeper.timed('Total database teardown'):
                    self.teardown_databases(old_config)
                self.teardown_test_environment()
            except Exception:
                if not run_failed:
                    raise
        self.time_keeper.print_results()

        file_results = combine_xml(output)
        build_xml_report(file_results)
        send_slack_message(f"Test Results:\n\n"
                           f"Success: {len(file_results[0])}\n"
                           f"Failure: {len(file_results[1])}\n"
                           f"Errors: {len(file_results[2])}\n"
                           f"Logs: {len(file_results[3])}")
        return self.suite_result(suite, xml_result)
