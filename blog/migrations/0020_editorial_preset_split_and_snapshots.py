from django.db import migrations


def update_editorial_presets(apps, schema_editor):
    Article = apps.get_model('blog', 'Article')
    ArticleRevision = apps.get_model('blog', 'ArticleRevision')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    def permission(model, codename):
        return Permission.objects.get(
            content_type=ContentType.objects.get(app_label='blog', model=model),
            codename=codename,
        )

    writer, _ = Group.objects.get_or_create(name='OEF Writers')
    reviewer, _ = Group.objects.get_or_create(name='OEF Reviewers')
    publisher, _ = Group.objects.get_or_create(name='OEF Publishers')
    # Existing reviewers used to inherit writer permissions. Retain that
    # capability explicitly before making each preset independently assignable.
    for user in reviewer.user_set.all().iterator():
        user.groups.add(writer)
    writer.permissions.set([
        permission('article', name) for name in (
            'add_article', 'change_article', 'view_article', 'submit_article',
        )
    ] + [permission('articlerevision', 'view_articlerevision')] + [
        permission('mediaasset', name) for name in (
            'add_mediaasset', 'change_mediaasset', 'view_mediaasset',
        )
    ])
    reviewer.permissions.set([
        permission('article', 'view_article'),
        permission('article', 'review_article'),
        permission('articlerevision', 'view_articlerevision'),
        permission('articlerevision', 'change_articlerevision'),
        permission('mediaasset', 'view_mediaasset'),
        permission('mediaasset', 'approve_mediaasset'),
    ])
    publisher.permissions.set([
        permission('article', 'view_article'),
        permission('article', 'publish_article'),
        permission('articlerevision', 'view_articlerevision'),
        permission('articlerevision', 'change_articlerevision'),
    ])

    for article in Article._base_manager.select_related(
        'published_revision', 'pending_revision',
    ).all().iterator():
        # Historical revisions never captured slug, author, crop or taxonomy.
        # Copying mutable Article fields here could publish an unreviewed draft.
        # Preserve the legacy public projection until explicit reconciliation.
        if article.published_revision_id:
            published = article.published_revision
            published.legacy_metadata_unverified = True
            if article.is_published:
                published.status = 'published'
            published.save(update_fields=('legacy_metadata_unverified', 'status'))
        if article.pending_revision_id:
            pending = article.pending_revision
            pending.status = 'changes_requested'
            pending.save(update_fields=('status',))
            article.pending_revision_id = None
            article.workflow_status = 'draft' if article.is_published else 'changes_requested'
            article.save(update_fields=('pending_revision', 'workflow_status'))


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0019_article_draft_contributors_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [migrations.RunPython(update_editorial_presets, migrations.RunPython.noop)]
