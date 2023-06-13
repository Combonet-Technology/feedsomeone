import os

import xmlrunner
from coverage import Coverage
from django.conf import settings
from django.test.runner import (DiscoverRunner, filter_tests_by_tags,
                                is_discoverable, reorder_suite)


class TestRunner(DiscoverRunner):

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        suite = self.test_suite()
        test_labels = test_labels or ['.']
        extra_tests = extra_tests or []
        self.test_loader.testNamePatterns = self.test_name_patterns

        discover_kwargs = {}
        if self.pattern is not None:
            discover_kwargs['pattern'] = self.pattern
        if self.top_level is not None:
            discover_kwargs['top_level_dir'] = self.top_level

        for label in test_labels:
            kwargs = discover_kwargs.copy()
            tests = None

            label_as_path = os.path.abspath(label)

            if not os.path.exists(label_as_path):
                tests = self.test_loader.loadTestsFromName(label)
            elif os.path.isdir(label_as_path) and not self.top_level:
                top_level = label_as_path
                while True:
                    init_py = os.path.join(top_level, '__init__.py')
                    if os.path.exists(init_py):
                        try_next = os.path.dirname(top_level)
                        if try_next == top_level:
                            break
                        top_level = try_next
                        continue
                    break
                kwargs['top_level_dir'] = top_level

            if not (tests and tests.countTestCases()) and is_discoverable(label):
                tests = self.test_loader.discover(start_dir=label, **kwargs)
                self.test_loader._top_level_dir = None

            suite.addTests(tests)

        for test in extra_tests:
            suite.addTest(test)

        if self.tags or self.exclude_tags:
            if self.verbosity >= 2:
                if self.tags:
                    print('Including test tag(s): %s.' % ', '.join(sorted(self.tags)))
                if self.exclude_tags:
                    print('Excluding test tag(s): %s.' % ', '.join(sorted(self.exclude_tags)))
            suite = filter_tests_by_tags(suite, self.tags, self.exclude_tags)
        suite = reorder_suite(suite, self.reorder_by, self.reverse)

        if self.parallel > 1:
            parallel_suite = self.parallel_test_suite(suite, self.parallel, self.failfast)
            parallel_units = len(parallel_suite.subsuites)
            self.parallel = min(self.parallel, parallel_units)

            if self.parallel > 1:
                suite = parallel_suite

        return suite

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        cov = Coverage()
        cov.start()
        xml_result = []
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        databases = self.get_databases(suite)
        verbosity = getattr(settings, 'TEST_OUTPUT_VERBOSE', 1)
        if isinstance(verbosity, bool):
            verbosity = (1, 2)[verbosity]
        descriptions = getattr(settings, 'TEST_OUTPUT_DESCRIPTIONS', False)
        output = getattr(settings, 'TEST_OUTPUT_DIR', '.')
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
        cov.stop()
        cov.save()
        cov.html_report(directory='htmlcov')

        self.time_keeper.print_results()
        return self.suite_result(suite, xml_result)
