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
            for title in (
                "Articles",
                "Briefings",
                "Feed Someone",
                "Impact",
                "Transparency",
            )
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
                    "community with staple food items, baby-care supplies, hygiene and "
                    "household essentials, clothing, footwear and other relief materials."
                ),
                "content": (
                    "Feed Someone 2.0 expanded the work from community feeding into orphanage relief. "
                    "The outreach visited Hope Orphanage at Shagari Village and Akure Children's "
                    "Home Orphanage, then returned to the Almajiri community around Old Garage. "
                    "Support included staple food items, baby-care supplies, hygiene and household "
                    "essentials, clothing, footwear and other practical relief materials collected "
                    "through volunteer, workplace and community mobilisation."
                ),
                "feature_img": "event_feature_img/placeholder.jpg",
                "budget": None,
            },
            {
                "title": "Orphanage Relief",
                "event_slug": "founder-led-abuja-orphanage-outreach",
                "event_date": date(2022, 8, 9),
                "time": "Birthday outreach",
                "location": "Lugbe / Airport Road axis, Abuja",
                "description": (
                    "A founder-funded visit delivered food items and practical relief supplies "
                    "to a children's home in Abuja."
                ),
                "content": (
                    "On 9 August 2022, the founder led a small birthday outreach around the "
                    "Lugbe / Airport Road axis in Abuja. "
                    "The visit delivered food items and practical relief supplies to a "
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
                    "Feed Someone did not begin as an institution. It began as a burden: hunger, "
                    "hardship and visible deprivation in communities where practical support could "
                    "restore dignity even for a day.\n\n"
                    "In 2019, friends and volunteers came together in Akure to prepare meals, buy "
                    "drinks and serve an underserved street-connected community. That first outreach "
                    "became the beginning of a wider conviction: relief should not be abstract. It "
                    "should meet people where they are, with care that can be seen and felt.\n\n"
                    "Today, the work continues through Oluwafemi Ebenezer Foundation, a registered "
                    "Nigerian nonprofit. Feed Someone remains the foundation's flagship outreach "
                    "programme while OEF builds broader work across relief, health, safety, learning "
                    "and opportunity.\n\n"
                    "This transition matters because donors and partners need clarity. OEF is the "
                    "legal organisation. Feed Someone is the programme expression that started the "
                    "movement and continues to carry its most practical relief work."
                ),
                "category": ["Briefings", "Feed Someone", "Transparency"],
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
                    "Feed Someone 1.0 took place in Akure, Ondo State on 27 December 2019. The "
                    "founder gathered friends and volunteers, food was prepared in batches, drinks "
                    "were bought, and support was delivered to an underserved street-connected "
                    "community.\n\n"
                    "The outreach reached approximately 150+ people. It was founder-led, "
                    "volunteer-supported and practical: cooked food, drinks, movement, presence and "
                    "a simple decision to respond instead of only feeling concern.\n\n"
                    "That first outreach still shapes OEF's operating philosophy. Immediate relief "
                    "matters because hunger and deprivation are urgent. But relief must also point "
                    "toward dignity, safety and opportunity. Feed Someone 1.0 gave the foundation a "
                    "model it could improve: gather people, mobilise resources, show up in person, "
                    "document the work and keep learning."
                ),
                "category": ["Briefings", "Impact", "Feed Someone"],
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
                    "Feed Someone 2.0 expanded the work from community feeding into orphanage "
                    "relief. The outreach visited children's homes in Akure and returned to the "
                    "Almajiri community around Old Garage.\n\n"
                    "The Akure visits included Hope Orphanage at Shagari Village and Akure "
                    "Children's Home Orphanage. Volunteers also mobilised support from colleagues "
                    "and community members, including staff connected to the Ondo State Internal "
                    "Revenue Service.\n\n"
                    "The relief materials went beyond a single food item. They included staple food "
                    "items, baby-care supplies, hygiene and household essentials, clothing, footwear "
                    "and other practical materials that children's homes could use according to "
                    "their actual needs.\n\n"
                    "OEF is still consolidating exact beneficiary counts before publishing stronger "
                    "claims. This is part of our commitment to evidence-safe reporting as we prepare "
                    "for responsible partnerships and first grants."
                ),
                "category": ["Briefings", "Impact", "Feed Someone"],
                "tags": ["feed-someone-2-0", "orphanage-relief", "impact"],
            },
            {
                "article_title": "Why Food, Hygiene and Learning Support Matter for Vulnerable Children",
                "article_excerpt": (
                    "A practical Q&A on why relief work should connect food, hygiene, safety "
                    "and learning opportunity."
                ),
                "article_slug": "why-food-hygiene-and-learning-support-matter",
                "article_content": (
                    "Poverty rarely affects only one part of a child's life. A child who lacks "
                    "regular meals may also lack hygiene supplies, safe spaces, books, trusted "
                    "adults and exposure to opportunities that make the future feel possible. "
                    "That is why effective community support should be practical, connected and "
                    "dignity-first.\n\n"
                    "## What is dignity-first relief?\n\n"
                    "Dignity-first relief means support is not only about handing out items. It is "
                    "about recognising the person receiving support as someone with worth, agency "
                    "and a future. Food items, baby-care supplies, hygiene essentials, school "
                    "materials and safe conversations all become more meaningful when they are "
                    "delivered with respect.\n\n"
                    "## Why do food and hygiene supplies matter together?\n\n"
                    "Food helps address immediate hunger, but hygiene supplies protect health and "
                    "daily dignity. For children's homes and underserved communities, practical "
                    "materials such as staple foods, infant supplies, toiletries, diapers and "
                    "cleaning essentials reduce pressure on caregivers and help children live in "
                    "safer environments.\n\n"
                    "Global organisations often connect relief with longer-term resilience. The "
                    "World Food Programme's Nigeria work, for example, combines emergency food "
                    "assistance with nutrition, livelihoods, capacity strengthening and logistics. "
                    "That pattern is useful for small NGOs too: solve today's urgent need while "
                    "building toward tomorrow's stability.\n\n"
                    "## How does water, sanitation and hygiene affect education?\n\n"
                    "Clean water and hygiene are not separate from education. When children are "
                    "sick, unsafe or spending time around preventable sanitation problems, learning "
                    "suffers. charity: water explains the connection clearly: access to clean water "
                    "supports health, education, income and dignity, especially for women and "
                    "children.\n\n"
                    "For OEF, this is one reason future programmes include health-and-dignity "
                    "sensitisation, menstrual equity, school support and eventually community "
                    "learning or digital opportunity hubs.\n\n"
                    "## Why should an NGO combine relief with opportunity?\n\n"
                    "Relief responds to urgent pressure. Opportunity changes what comes next. A "
                    "family may need food today, but a child also needs learning materials, safe "
                    "adults, protection from abuse, digital exposure and the confidence to imagine "
                    "a different future.\n\n"
                    "This is why OEF's long-term vision goes beyond annual outreach. Feed Someone "
                    "remains the flagship relief programme, but the wider foundation vision includes "
                    "health dignity, safe lives, learning access and digital hope hubs.\n\n"
                    "## How can donors evaluate a young NGO?\n\n"
                    "A young NGO may not yet have major grants or audited multi-year programmes. "
                    "That does not automatically mean the work lacks value. Donors can look for "
                    "clear legal identity, consistent public presence, cautious impact claims, "
                    "evidence galleries, transparent contact channels, and a realistic plan for "
                    "governance and reporting.\n\n"
                    "OEF is building exactly that: a public record of completed outreach, clearer "
                    "programme categories, approved media evidence, transparency notes and a "
                    "responsible path toward first institutional grants.\n\n"
                    "## Further reading\n\n"
                    "- World Food Programme Nigeria: https://www.wfp.org/countries/nigeria\n"
                    "- charity: water on the global water crisis: "
                    "https://www.charitywater.org/global-water-crisis"
                ),
                "category": ["Articles"],
                "tags": [
                    "child-welfare",
                    "food-relief",
                    "hygiene",
                    "education",
                    "ngo-impact",
                ],
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
