import json

from django.utils.html import escape


def build_vacancy_meta(request, vacancy):
    """Build reusable metadata and Google for Jobs JobPosting JSON-LD for vacancy detail pages."""
    canonical_url = request.build_absolute_uri(vacancy.get_absolute_url())

    structured_data_json = None
    if vacancy.is_open:
        description_sections = []

        if vacancy.about_oef:
            description_sections.append(
                f'<h3>About OEF</h3><p>{escape(vacancy.about_oef)}</p>'
            )

        if vacancy.description:
            description_sections.append(
                f'<h3>About the Opportunity</h3><p>{escape(vacancy.description)}</p>'
            )

        if vacancy.who_we_are_looking_for:
            paragraphs = [
                p.strip()
                for p in vacancy.who_we_are_looking_for.split('\n\n')
                if p.strip()
            ]
            paragraphs_html = ''.join(f'<p>{escape(p)}</p>' for p in paragraphs)
            description_sections.append(
                f'<h3>Who We Are Looking For</h3>{paragraphs_html}'
            )

        if vacancy.responsibility_items:
            items_html = ''.join(
                f'<li>{escape(item)}</li>' for item in vacancy.responsibility_items
            )
            description_sections.append(
                f'<h3>Core Responsibilities</h3><ul>{items_html}</ul>'
            )

        if vacancy.expectation_items:
            items_html = ''.join(
                f'<li>{escape(item)}</li>' for item in vacancy.expectation_items
            )
            description_sections.append(
                f'<h3>Expectations</h3><ul>{items_html}</ul>'
            )

        if vacancy.benefit_items:
            items_html = ''.join(
                f'<li>{escape(item)}</li>' for item in vacancy.benefit_items
            )
            description_sections.append(
                f'<h3>Benefits and Experience</h3><ul>{items_html}</ul>'
            )

        full_description_html = ''.join(description_sections)

        employment_type_map = {
            'volunteer': 'VOLUNTEER',
            'internship': 'INTERN',
            'contract': 'CONTRACTOR',
            'staff': 'FULL_TIME',
        }
        employment_type = employment_type_map.get(vacancy.engagement_type, 'VOLUNTEER')

        date_posted = (
            vacancy.published_at.isoformat()
            if vacancy.published_at
            else vacancy.created_at.isoformat()
        )

        logo_url = request.build_absolute_uri('/static/img/logo/oef-logo.svg')

        structured_data = {
            '@context': 'https://schema.org',
            '@type': 'JobPosting',
            'title': vacancy.title,
            'description': full_description_html,
            'identifier': {
                '@type': 'PropertyValue',
                'name': 'Oluwafemi Ebenezer Foundation',
                'value': vacancy.slug,
            },
            'datePosted': date_posted,
            'employmentType': employment_type,
            'hiringOrganization': {
                '@type': 'Organization',
                'name': 'Oluwafemi Ebenezer Foundation',
                'sameAs': 'https://www.oluwafemiebenezerfoundation.org/',
                'logo': logo_url,
            },
            'url': canonical_url,
            'directApply': True,
        }

        if vacancy.work_mode in ('remote', 'hybrid'):
            structured_data['jobLocationType'] = 'TELECOMMUTE'
            structured_data['applicantLocationRequirements'] = {
                '@type': 'Country',
                'name': 'Nigeria',
            }

        structured_data['jobLocation'] = {
            '@type': 'Place',
            'address': {
                '@type': 'PostalAddress',
                'addressLocality': 'Abuja',
                'addressRegion': 'FCT',
                'addressCountry': 'NG',
            },
        }

        data_json = json.dumps(structured_data, ensure_ascii=False)
        structured_data_json = (
            data_json
            .replace('&', '\\u0026')
            .replace('<', '\\u003c')
            .replace('>', '\\u003e')
        )

    return {
        'canonical_url': canonical_url,
        'description': vacancy.summary,
        'structured_data': structured_data_json,
    }
