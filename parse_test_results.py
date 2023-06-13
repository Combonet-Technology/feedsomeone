import glob
import os
import sys
import xml.etree.ElementTree as ET


def parse_test_results(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    test_results = {}
    reason = None
    for testcase in root.iter('testcase'):
        classname = testcase.get('classname')
        test_name = testcase.get('name')
        time = float(testcase.get('time', 0))

        # Get failure information if available
        failure_elem = testcase.find('failure')
        error_elem = testcase.find('error')
        result = 'passed'
        if failure_elem is not None:
            result = 'failed'
            reason = failure_elem.text
        elif error_elem is not None:
            result = 'error'
            reason = error_elem.text

        # Group results by classname or test name
        group_key = classname if group_by_app else test_name

        if group_key not in test_results:
            test_results[group_key] = {
                'tests': [],
                'total_time': 0,
                'passed': 0,
                'failed': 0,
                'errors': 0
            }

        # Add test result to the corresponding group
        output = {
            'name': test_name,
            'classname': classname,
            'result': result,
            'time': time,
        }

        if reason:
            output.update({'details': reason})

        system_out_elem = testcase.find('system-err')

        if system_out_elem is not None:
            system_out = system_out_elem.text.strip()
            output.update({'system_out': system_out})
        test_results[group_key]['tests'].append(output)

        # Update overall statistics
        test_results[group_key]['total_time'] += time
        if result == 'passed':
            test_results[group_key]['passed'] += 1
        elif result == 'failed':
            test_results[group_key]['failed'] += 1
        elif result == 'error':
            test_results[group_key]['errors'] += 1
    return test_results


def generate_xml_report(test_results):
    root = ET.Element('coverage')
    packages_elem = ET.SubElement(root, 'packages')
    for test_result in test_results:
        classnames = test_result.keys()
        for classname in classnames:
            class_data = test_result[classname]

            package_elem = ET.SubElement(packages_elem, 'package', name=classname)
            classes_elem = ET.SubElement(package_elem, 'classes')
            class_elem = ET.SubElement(classes_elem, 'class', name=classname)
            methods_elem = ET.SubElement(class_elem, 'methods')
            for test in class_data['tests']:
                test_name = test['name']
                test_classname = test['classname']
                test_result = test['result']
                test_time = str(test['time'])
                test_system_out = test.get('system_out')

                test_elem = ET.SubElement(methods_elem, 'test', name=test_name)
                test_elem.set('classname', test_classname)
                test_elem.set('result', test_result)
                test_elem.set('time', test_time)
                if test_result == 'error':
                    test_elem.set('error_details', test.get('details'))
                elif test_result == 'failed':
                    test_elem.set('failure_details', test.get('details'))
                if test_system_out is not None:
                    test_elem.set('system-out', test_system_out)

    tree = ET.ElementTree(root)
    report_file = 'coverage.xml'
    tree.write(report_file, encoding='utf-8', xml_declaration=True)
    print(f"Report generated: {report_file}")


if __name__ == '__main__':
    folder_path = sys.argv[1]
    group_by_app = True
    xml_files = glob.glob(os.path.join(folder_path, '*.xml'))

    test_results = []
    for xml_file in xml_files:
        file_results = parse_test_results(xml_file)
        test_results.append(file_results)
    generate_xml_report(test_results)
