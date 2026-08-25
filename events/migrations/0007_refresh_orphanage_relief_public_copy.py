from django.db import migrations

OLD_DESCRIPTION = (
    "A founder-funded visit delivered food items and practical relief supplies "
    "to a children's home in Abuja."
)
NEW_DESCRIPTION = (
    "A community visit delivered food items and practical relief supplies "
    "to a children's home in Abuja."
)
OLD_CONTENT = (
    "On 9 August 2022, the founder led a small birthday outreach around the "
    "Lugbe / Airport Road axis in Abuja. "
    "The visit delivered food items and practical relief supplies to a "
    "children's home with support from a small group of friends. "
    "The institution name and beneficiary count are pending confirmation."
)
NEW_CONTENT = (
    "On 9 August 2022, a small birthday outreach took place around the "
    "Lugbe / Airport Road axis in Abuja. "
    "The visit delivered food items and practical relief supplies to a "
    "children's home with support from a small group of friends."
)


def update_public_copy(apps, schema_editor):
    Event = apps.get_model('events', 'Events')
    event = Event.objects.filter(event_slug='founder-led-abuja-orphanage-outreach')
    event.filter(description=OLD_DESCRIPTION).update(description=NEW_DESCRIPTION)
    event.filter(content=OLD_CONTENT).update(content=NEW_CONTENT)


def restore_public_copy(apps, schema_editor):
    Event = apps.get_model('events', 'Events')
    event = Event.objects.filter(event_slug='founder-led-abuja-orphanage-outreach')
    event.filter(description=NEW_DESCRIPTION).update(description=OLD_DESCRIPTION)
    event.filter(content=NEW_CONTENT).update(content=OLD_CONTENT)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0006_alter_events_gallery_is_public'),
    ]

    operations = [
        migrations.RunPython(update_public_copy, restore_public_copy),
    ]
