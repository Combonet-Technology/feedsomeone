import os
import sys
import xml.etree.ElementTree as ET


def parse_test_results(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    failed_tests = []

    for testcase in root.iter('testcase'):
        if testcase.find('failure') is not None:
            test_name = testcase.get('classname') + '.' + testcase.get('name')
            failed_tests.append(test_name)

    return failed_tests


if __name__ == '__main__':
    xml_file = sys.argv[1]
    failed_tests = parse_test_results(xml_file)

    for test in failed_tests:
        print(test)

    # Set the failed tests as an output for GitHub Actions
    output_file = os.environ['GITHUB_WORKSPACE'] + '/failed_tests.txt'
    with open(output_file, 'w') as f:
        for test in failed_tests:
            f.write(test + '\n')
    print(f"::set-output name=failed_tests::{output_file}")
