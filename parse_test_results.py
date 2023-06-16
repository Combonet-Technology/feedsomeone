import glob
import os
import xml.etree.ElementTree as ET


def parse_results(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    successes, failures, errors, logs = [], [], [], []
    for testcase in root.iter('testcase'):
        classname = testcase.get('classname')
        test_name = testcase.get('name')
        time = float(testcase.get('time', 0))

        # Get failure information if available
        failure_elem = testcase.find('failure')
        error_elem = testcase.find('error')
        debug_logs = testcase.find('system-err')
        result = 'passed'
        if failure_elem is not None:
            result = 'failed'
            reason = failure_elem.text
            failures.append({
                'result': result,
                'classname': classname,
                'name': test_name,
                'time': time,
                'details': reason
            })
        elif error_elem is not None:
            result = 'error'
            reason = error_elem.text
            errors.append({
                'result': result,
                'classname': classname,
                'name': test_name,
                'time': time,
                'details': reason
            })
        elif debug_logs is not None:
            result = 'logs'
            reason = debug_logs.text
            logs.append({
                'result': result,
                'classname': classname,
                'name': test_name,
                'time': time,
                'details': reason
            })
        else:
            successes.append({
                'result': result,
                'classname': classname,
                'name': test_name,
                'time': time
            })
    return successes, failures, errors, logs


def build_xml_report(test_results):
    root = ET.Element('coverage')
    packages_elem = ET.SubElement(root, 'packages')
    successes, failures, errors, logs = test_results

    for success in successes:
        result = success['result']
        classname = success['classname']
        test_name = success['name']
        time = str(success['time'])

        package_elem = ET.SubElement(packages_elem, 'package', name=classname)
        classes_elem = ET.SubElement(package_elem, 'classes')
        class_elem = ET.SubElement(classes_elem, 'class', name=classname)
        methods_elem = ET.SubElement(class_elem, 'methods')

        test_elem = ET.SubElement(methods_elem, 'test', name=test_name)
        test_elem.set('classname', classname)
        test_elem.set('result', result)
        test_elem.set('time', time)

    for failure in failures:
        result = failure['result']
        classname = failure['classname']
        test_name = failure['name']
        time = str(failure['time'])
        details = failure['details']

        package_elem = ET.SubElement(packages_elem, 'package', name=classname)
        classes_elem = ET.SubElement(package_elem, 'classes')
        class_elem = ET.SubElement(classes_elem, 'class', name=classname)
        methods_elem = ET.SubElement(class_elem, 'methods')

        test_elem = ET.SubElement(methods_elem, 'test', name=test_name)
        test_elem.set('classname', classname)
        test_elem.set('result', result)
        test_elem.set('time', time)
        test_elem.set('failure_details', details)

    for error in errors:
        result = error['result']
        classname = error['classname']
        test_name = error['name']
        time = str(error['time'])
        details = error['details']

        package_elem = ET.SubElement(packages_elem, 'package', name=classname)
        classes_elem = ET.SubElement(package_elem, 'classes')
        class_elem = ET.SubElement(classes_elem, 'class', name=classname)
        methods_elem = ET.SubElement(class_elem, 'methods')

        test_elem = ET.SubElement(methods_elem, 'test', name=test_name)
        test_elem.set('classname', classname)
        test_elem.set('result', result)
        test_elem.set('time', time)
        test_elem.set('error_details', details)

    for log in logs:
        result = log['result']
        classname = log['classname']
        test_name = log['name']
        time = str(log['time'])
        details = log['details']

        package_elem = ET.SubElement(packages_elem, 'package', name=classname)
        classes_elem = ET.SubElement(package_elem, 'classes')
        class_elem = ET.SubElement(classes_elem, 'class', name=classname)
        methods_elem = ET.SubElement(class_elem, 'methods')

        test_elem = ET.SubElement(methods_elem, 'test', name=test_name)
        test_elem.set('classname', classname)
        test_elem.set('result', result)
        test_elem.set('time', time)
        test_elem.text = details

    tree = ET.ElementTree(root)
    report_file = 'coverage.xml'
    tree.write(report_file, encoding='utf-8', xml_declaration=True)
    print(f"Report generated: {report_file}")


def combine_xml(output):
    parsed_result = None
    xml_files = glob.glob(os.path.join(output, '*.xml'))
    success, failure, error, logs = [], [], [], []

    for xml_file in xml_files:
        parsed_result = parse_results(xml_file)
        successes, failures, errors, debug_logs = parsed_result
        # file_results = parse_test_results(xml_file, group_by_app)
        if successes is not None:
            success.extend(successes)
        if failures is not None:
            failure.extend(failures)
        if errors is not None:
            error.extend(errors)
        if debug_logs is not None:
            logs.extend(debug_logs)

    return success, failure, error, logs
