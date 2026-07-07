from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Article, Categories
from events.models import Events
from user.models import UserProfile


class Command(BaseCommand):
    help = "Seed/update OEF grant-readiness events and articles without creating duplicates."

    def handle(self, *args, **options):
        author = self._get_editorial_author()
        categories = {
            title: Categories.objects.get_or_create(title=title)[0]
            for title in ("Impact", "Feed Someone", "Transparency", "Programmes")
        }

        event_count = self._seed_events()
        article_count = self._seed_articles(author, categories)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded/updated {event_count} event records and {article_count} article records."
            )
        )

    def _get_editorial_author(self):
        author, created = UserProfile.objects.get_or_create(
            email="info@oluwafemiebenezerfoundation.org",
            defaults={
                "username": "oef-editorial",
                "first_name": "OEF",
                "last_name": "Editorial",
                "is_active": True,
            },
        )
        changed = False
        if not author.username:
            author.username = "oef-editorial"
            changed = True
        if not author.first_name:
            author.first_name = "OEF"
            changed = True
        if not author.last_name:
            author.last_name = "Editorial"
            changed = True
        if not author.is_active:
            author.is_active = True
            changed = True
        if created or changed:
            author.set_unusable_password()
            author.save()
        return author

    def _seed_events(self):
        events = [
            {
                "title": "Feed Someone 1.0",
                "event_slug": "feed-someone-1-0",
                "event_date": date(2019, 12, 27),
                "time": "Community outreach",
                "location": "Akure, Ondo State",
                "description": (
                    "The first Feed Someone outreach, providing meals and drinks "
                    "to an underserved street-connected community."
                ),
                "content": (
                    "Feed Someone 1.0 took place on 27 December 2019 in Akure, Ondo State. "
                    "Friends and volunteers prepared meals, bought drinks, and distributed "
                    "support to an underserved street-connected community. "
                    "The outreach reached approximately 150+ people and became the beginning "
                    "of the movement now formalised as Oluwafemi Ebenezer Foundation."
                ),
                "feature_img": "event_feature_img/placeholder.jpg",
                "budget": None,
            },
            {
                "title": "Feed Someone 2.0",
                "event_slug": "feed-someone-2-0",
                "event_date": date(2020, 12, 27),
                "time": "Orphanage and community relief",
                "location": "Akure, Ondo State",
                "description": (
                    "Expanded outreach supporting two children's homes and an underserved "
                    "community with foodstuffs, infant supplies, toiletries, clothing and "
                    "other essentials."
                ),
                "content": (
                    "Feed Someone 2.0 expanded the work from community feeding into orphanage relief. "
                    "Two children's homes and an underserved street-connected community received "
                    "foodstuffs, milk, noodles, rice, gari, beans, diapers, toiletries, washing "
                    "items, clothing, shoes and other essentials. "
                    "Exact institution names and beneficiary counts are still being consolidated "
                    "from available records."
                ),
                "feature_img": "event_feature_img/placeholder.jpg",
                "budget": None,
            },
            {
                "title": "Founder-led Abuja Orphanage Outreach",
                "event_slug": "founder-led-abuja-orphanage-outreach",
                "event_date": date(2022, 8, 9),
                "time": "Birthday outreach",
                "location": "Lugbe / Airport Road axis, Abuja",
                "description": (
                    "A founder-funded visit delivered noodles, beverages and related supplies "
                    "to a children's home."
                ),
                "content": (
                    "On 9 August 2022, the founder led a small birthday outreach around the "
                    "Lugbe / Airport Road axis in Abuja. "
                    "The visit delivered noodles, beverages and related supplies to a "
                    "children's home with support from a small group of friends. "
                    "The institution name and beneficiary count are pending confirmation."
                ),
                "feature_img": "event_feature_img/placeholder.jpg",
                "budget": None,
            },
        ]

        for event_data in events:
            Events.objects.update_or_create(
                event_slug=event_data["event_slug"],
                defaults=event_data,
            )
        return len(events)

    def _seed_articles(self, author, categories):
        articles = [
            {
                "article_title": "From Feed Someone to Oluwafemi Ebenezer Foundation",
                "article_excerpt": "How a grassroots hunger-relief movement became a registered Nigerian foundation.",
                "article_slug": "from-feed-someone-to-oluwafemi-ebenezer-foundation",
                "article_content": (
                    "<p>Feed Someone did not begin as an institution. It began as a burden: "
                    "hunger, hardship and visible deprivation in communities where practical "
                    "support could restore dignity even for a day.</p>"
                    "<p>In 2019, friends and volunteers came together in Akure to prepare meals, "
                    "buy drinks and serve an underserved street-connected community. That first "
                    "outreach became the beginning of a wider conviction.</p>"
                    "<p>Today, the work continues through Oluwafemi Ebenezer Foundation, a "
                    "registered Nigerian nonprofit. Feed Someone remains the foundation's flagship "
                    "outreach programme while OEF builds broader work in relief, health, safety, "
                    "learning and opportunity.</p>"
                ),
                "category": ["Feed Someone", "Transparency"],
                "tags": ["feed-someone", "oef", "origin-story"],
            },
            {
                "article_title": "Feed Someone 1.0: The First Outreach That Started the Movement",
                "article_excerpt": (
                    "The 27 December 2019 Akure outreach that became the beginning of OEF's "
                    "public service work."
                ),
                "article_slug": "feed-someone-1-0-first-outreach",
                "article_content": (
                    "<p>Feed Someone 1.0 took place in Akure, Ondo State on 27 December 2019. "
                    "The founder gathered friends and volunteers, food was prepared, drinks were "
                    "bought, and support was delivered to an underserved street-connected "
                    "community.</p>"
                    "<p>The outreach reached approximately 150+ people. It was founder-led, "
                    "volunteer-supported and practical: food, drinks and direct human presence.</p>"
                    "<p>That small beginning remains important because it shows the foundation's "
                    "core conviction: immediate relief matters, but dignity and opportunity must "
                    "remain the larger goal.</p>"
                ),
                "category": ["Impact", "Feed Someone"],
                "tags": ["feed-someone-1-0", "impact", "akure"],
            },
            {
                "article_title": "Feed Someone 2.0: Expanding From Community Feeding to Orphanage Relief",
                "article_excerpt": (
                    "How the 2020 outreach added orphanage relief and practical supplies to the "
                    "Feed Someone model."
                ),
                "article_slug": "feed-someone-2-0-orphanage-relief",
                "article_content": (
                    "<p>Feed Someone 2.0 expanded the work from community feeding into orphanage "
                    "relief. The outreach served two children's homes in Akure and returned to an "
                    "underserved street-connected community.</p>"
                    "<p>Support included foodstuffs, milk, noodles, rice, gari, beans, diapers, "
                    "toiletries, washing items, clothing, shoes and other essentials collected "
                    "through volunteer and community mobilisation.</p>"
                    "<p>OEF is still consolidating exact institution names and beneficiary counts "
                    "before publishing stronger claims. This is part of our commitment to "
                    "evidence-safe reporting as we prepare for responsible partnerships and first "
                    "grants.</p>"
                ),
                "category": ["Impact", "Feed Someone"],
                "tags": ["feed-someone-2-0", "orphanage-relief", "impact"],
            },
        ]

        for article_data in articles:
            category_titles = article_data.pop("category")
            tag_names = article_data.pop("tags")
            article, _ = Article.objects.update_or_create(
                article_slug=article_data["article_slug"],
                defaults={
                    **article_data,
                    "article_author": author,
                    "is_published": True,
                    "is_deleted": False,
                    "publish_date": timezone.now(),
                },
            )
            article.category.set([categories[title] for title in category_titles])
            article.tags.clear()
            article.tags.add(*tag_names)
        return len(articles)
