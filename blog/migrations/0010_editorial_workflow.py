import django.db.models.deletion
import django.utils.timezone
import markdown
import nh3
from django.conf import settings
from django.db import migrations, models

WRITER_GROUP = 'OEF Writers'
REVIEWER_GROUP = 'OEF Reviewers'

WRITER_PERMISSIONS = (
    ('article', 'add_article', 'Can add article'),
    ('article', 'change_article', 'Can change article'),
    ('article', 'view_article', 'Can view article'),
    ('article', 'submit_article', 'Can submit articles for editorial review'),
    ('articlerevision', 'view_articlerevision', 'Can view article revision'),
    ('mediaasset', 'add_mediaasset', 'Can add media asset'),
    ('mediaasset', 'change_mediaasset', 'Can change media asset'),
    ('mediaasset', 'view_mediaasset', 'Can view media asset'),
)

REVIEWER_ONLY_PERMISSIONS = (
    ('article', 'review_article', 'Can review article revisions'),
    ('article', 'publish_article', 'Can publish approved article revisions'),
    ('articlerevision', 'change_articlerevision', 'Can change article revision'),
    ('mediaasset', 'approve_mediaasset', 'Can approve editorial media for publication'),
)


def _sanitise_legacy_content(value):
    html = markdown.markdown(value or '', extensions=('extra', 'sane_lists'))
    return nh3.clean(
        html,
        tags={
            'p', 'br', 'strong', 'em', 'u', 's', 'h2', 'h3', 'h4',
            'ul', 'ol', 'li', 'blockquote', 'hr', 'a', 'figure',
            'figcaption', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        },
        attributes={
            'a': {'href', 'target'},
            'img': {'src', 'alt', 'width', 'height'},
            'figure': {'class'},
        },
        url_schemes={'http', 'https', 'mailto'},
    )


def create_groups_and_snapshot_articles(apps, schema_editor):
    Article = apps.get_model('blog', 'Article')
    ArticleRevision = apps.get_model('blog', 'ArticleRevision')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    def permission_for(model, codename, name):
        content_type, _ = ContentType.objects.get_or_create(
            app_label='blog',
            model=model,
        )
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={'name': name},
        )
        return permission

    writer, _ = Group.objects.get_or_create(name=WRITER_GROUP)
    writer_permissions = [permission_for(*values) for values in WRITER_PERMISSIONS]
    writer.permissions.set(writer_permissions)

    reviewer, _ = Group.objects.get_or_create(name=REVIEWER_GROUP)
    reviewer_permissions = writer_permissions + [
        permission_for(*values) for values in REVIEWER_ONLY_PERMISSIONS
    ]
    reviewer.permissions.set(reviewer_permissions)

    # Article's historical migration state serialises only its named
    # ``published`` manager, so use the base manager to include every row.
    for article in Article._base_manager.all().iterator():
        content = _sanitise_legacy_content(article.article_content)
        article.article_content = content
        if article.is_published:
            try:
                feature_image_url = article.feature_img.url if article.feature_img else ''
            except (ValueError, AttributeError):
                feature_image_url = ''
            revision = ArticleRevision._base_manager.create(
                article=article,
                number=1,
                title=article.article_title,
                excerpt=article.article_excerpt or '',
                content=content,
                feature_image_url=feature_image_url,
                status='approved',
                created_by_id=article.article_author_id,
                reviewed_by_id=article.article_author_id,
                submitted_at=article.date_created or article.publish_date,
                reviewed_at=article.publish_date,
                published_at=article.publish_date,
            )
            article.published_revision_id = revision.pk
            article.workflow_status = 'published'
        else:
            article.workflow_status = 'draft'
        article.save(update_fields=(
            'article_content',
            'published_revision',
            'workflow_status',
        ))


def remove_editorial_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=(WRITER_GROUP, REVIEWER_GROUP)).delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('blog', '0009_article_tags'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='article',
            options={
                'permissions': (
                    ('submit_article', 'Can submit articles for editorial review'),
                    ('review_article', 'Can review article revisions'),
                    ('publish_article', 'Can publish approved article revisions'),
                ),
            },
        ),
        migrations.CreateModel(
            name='MediaAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_id', models.CharField(max_length=255, unique=True)),
                ('public_id', models.CharField(max_length=500, unique=True)),
                ('secure_url', models.URLField(max_length=1000, unique=True)),
                ('original_filename', models.CharField(max_length=255)),
                ('format', models.CharField(max_length=20)),
                ('width', models.PositiveIntegerField()),
                ('height', models.PositiveIntegerField()),
                ('bytes', models.PositiveBigIntegerField()),
                ('alt_text', models.CharField(blank=True, max_length=255)),
                ('caption', models.CharField(blank=True, max_length=500)),
                ('approved_for_publication', models.BooleanField(default=False, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='editorial_media_uploads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
                'permissions': (('approve_mediaasset', 'Can approve editorial media for publication'),),
            },
        ),
        migrations.CreateModel(
            name='ArticleRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('title', models.CharField(max_length=100)),
                ('excerpt', models.CharField(blank=True, max_length=255)),
                ('content', models.TextField()),
                ('feature_image_url', models.URLField(blank=True, max_length=1000)),
                ('status', models.CharField(choices=[('in_review', 'In review'), ('approved', 'Approved'), ('changes_requested', 'Changes requested'), ('superseded', 'Superseded')], default='in_review', max_length=24)),
                ('review_notes', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='blog.article')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='article_revisions_created', to=settings.AUTH_USER_MODEL)),
                ('media_assets', models.ManyToManyField(blank=True, related_name='article_revisions', to='blog.mediaasset')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='article_revisions_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='articlerevision',
            constraint=models.UniqueConstraint(fields=('article', 'number'), name='unique_article_revision_number'),
        ),
        migrations.AddField(
            model_name='article',
            name='workflow_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('in_review', 'In review'), ('changes_requested', 'Changes requested'), ('published', 'Published')], default='draft', max_length=24),
        ),
        migrations.AddField(
            model_name='article',
            name='pending_revision',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='blog.articlerevision'),
        ),
        migrations.AddField(
            model_name='article',
            name='published_revision',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='published_articles', to='blog.articlerevision'),
        ),
        migrations.RunPython(
            create_groups_and_snapshot_articles,
            reverse_code=remove_editorial_groups,
        ),
        migrations.AlterModelManagers(
            name='article',
            managers=[
                ('objects', models.Manager()),
                ('published', models.Manager()),
            ],
        ),
        migrations.AlterModelOptions(
            name='article',
            options={
                'base_manager_name': 'objects',
                'default_manager_name': 'objects',
                'permissions': (
                    ('submit_article', 'Can submit articles for editorial review'),
                    ('review_article', 'Can review article revisions'),
                    ('publish_article', 'Can publish approved article revisions'),
                ),
            },
        ),
    ]
