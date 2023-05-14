from django import forms, template

from contact.forms import NewsletterForm

register = template.Library()

css_classes = {
    'textarea': 'form-control',
    'input': 'form-control',
    'file': 'form-control-file',
}

field_labels = {
    'firstname': 'First Name',
    'lastname': 'Last Name',
    'subject': 'Enter Subject',
    'message': 'Enter Message',
    'email': 'Enter email address',
    'state_of_residence': 'Enter your current state of residence',
    'short_bio': 'What made you join as a volunteer',
    'image': 'Upload your profile picture',
    'phone_number': 'Enter your phone number (preferably one on whatsapp)',
    'ethnicity': 'Enter your tribe',
    'religion': 'Enter your religion',
    'profession': 'Enter your profession',
}


@register.filter(name='add_attrib')
@register.filter(name='add_attrib_profile')
def add_attrib(field, css=None):
    attrs = {
        'class': css_classes.get(field.field.widget.__class__.__name__.lower(), 'form-control'),
        'placeholder': field_labels.get(field.name, ''),
        'onfocus': "this.placeholder = ''",
        'onblur': f"this.placeholder = '{field_labels.get(field.name, '')}'",
        'id': '',
        'name': '',
    }

    if isinstance(field.field.widget, forms.Textarea):
        attrs['cols'] = '30'
        attrs['rows'] = '9'
    if css:
        for style in css.split(','):
            print(style)
            if ':' not in style:
                attrs[style] = True
            else:
                key, val = style.split(':')
                attrs[key] = attrs[key] + ' ' + val if key == 'class' else val
    errors = field.errors.as_text().strip()
    if errors:
        attrs['placeholder'] = errors

    return field.as_widget(attrs=attrs)


@register.inclusion_tag('newsletter_form.html')
def newsletter_form(form=None):
    if form is None:
        form = NewsletterForm()
    return {'form': form}
