from django import forms, template

from contact.forms import NewsletterForm

register = template.Library()


@register.filter(name='add_attrib')
def add_attrib(field, css):
    name_to_id = {
        'firstname': 'First Name',
        'lastname': 'Last Name',
        'subject': 'Enter Subject',
        'message': 'Enter Message',
        'email': 'Enter email address'
    }
    onblur = f"this.placeholder = '{name_to_id[field.name]}'"
    placeholder = f"{name_to_id[field.name]}"

    errors = field.errors.as_text().strip()

    attrs = {'onfocus': "this.placeholder = ''",
             'onblur': onblur,
             'placeholder': errors if errors else placeholder,
             'id': "",
             'name': ""}

    definition = css.split(',')

    if isinstance(field.field.widget, forms.Textarea):
        if 'cols' not in attrs:
            attrs['cols'] = '30'
        if 'rows' not in attrs:
            attrs['rows'] = '9'

    for d in definition:
        if ':' not in d:
            attrs['class'] = d
        else:
            key, val = d.split(':')
            attrs[key] = val

    return field.as_widget(attrs=attrs)


@register.inclusion_tag('newsletter_form.html')
def newsletter_form(form=None):
    if form is None:
        form = NewsletterForm()
    return {'form': form}