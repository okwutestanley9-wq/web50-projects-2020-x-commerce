from decimal import Decimal
from django.contrib.admin.sites import site
from django.test import Client, TestCase
from django.urls import reverse

from .models import Bid, Category, Comment, Listing, User


class CommerceTests(TestCase):
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(username="alice", email="alice@example.com", password="password123")
        self.user2 = User.objects.create_user(username="bob", email="bob@example.com", password="password123")
        self.user3 = User.objects.create_user(username="charlie", email="charlie@example.com", password="password123")

        # Create category
        self.category_electronics = Category.objects.create(name="Electronics")
        self.category_books = Category.objects.create(name="Books")

        # Create listings
        self.listing1 = Listing.objects.create(
            title="Laptop Pro",
            description="High performance laptop in pristine condition.",
            starting_bid=Decimal("500.00"),
            image_url="https://example.com/laptop.jpg",
            category=self.category_electronics,
            creator=self.user1,
            is_active=True
        )

        self.listing2 = Listing.objects.create(
            title="Vintage Book",
            description="Rare first edition.",
            starting_bid=Decimal("25.00"),
            creator=self.user2,
            category=self.category_books,
            is_active=False
        )

        self.client = Client()

    def test_models_representation(self):
        """Test string representations and properties of models."""
        self.assertEqual(str(self.category_electronics), "Electronics")
        self.assertEqual(self.listing1.current_price, Decimal("500.00"))
        self.assertEqual(self.listing1.bid_count, 0)
        self.assertIsNone(self.listing1.highest_bid)

        bid = Bid.objects.create(listing=self.listing1, bidder=self.user2, amount=Decimal("550.00"))
        self.assertEqual(self.listing1.current_price, Decimal("550.00"))
        self.assertEqual(self.listing1.bid_count, 1)
        self.assertEqual(self.listing1.highest_bid, bid)
        self.assertIn("550.00", str(bid))

        comment = Comment.objects.create(listing=self.listing1, author=self.user2, content="Great laptop!")
        self.assertIn("Comment by bob", str(comment))

    def test_active_listings_index(self):
        """Active listings page shows active listings and hides inactive ones."""
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop Pro")
        self.assertContains(response, "500.00")
        self.assertNotContains(response, "Vintage Book")

    def test_create_listing_requires_login(self):
        """Unauthenticated users cannot access create listing page."""
        response = self.client.get(reverse("create_listing"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_create_listing_authenticated(self):
        """Authenticated users can successfully create a new listing."""
        self.client.login(username="alice", password="password123")
        response = self.client.post(reverse("create_listing"), {
            "title": "Smartphone",
            "description": "Brand new smartphone.",
            "starting_bid": "300.00",
            "image_url": "https://example.com/phone.jpg",
            "category": self.category_electronics.id
        })
        self.assertEqual(response.status_code, 302)
        new_listing = Listing.objects.get(title="Smartphone")
        self.assertEqual(new_listing.creator, self.user1)
        self.assertEqual(new_listing.starting_bid, Decimal("300.00"))
        self.assertTrue(new_listing.is_active)

    def test_listing_view(self):
        """Listing page displays all details."""
        response = self.client.get(reverse("listing", args=[self.listing1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop Pro")
        self.assertContains(response, "High performance laptop")
        self.assertContains(response, "500.00")
        self.assertContains(response, "Electronics")

    def test_watchlist_functionality(self):
        """Test adding and removing items from watchlist."""
        self.client.login(username="bob", password="password123")

        # Add to watchlist
        response = self.client.post(reverse("toggle_watchlist", args=[self.listing1.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.user2.watchlist.filter(id=self.listing1.id).exists())

        # Check watchlist page
        response = self.client.get(reverse("watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop Pro")

        # Remove from watchlist
        response = self.client.post(reverse("toggle_watchlist", args=[self.listing1.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.user2.watchlist.filter(id=self.listing1.id).exists())

    def test_bidding_rules(self):
        """Test all bid validation rules."""
        self.client.login(username="bob", password="password123")

        # First bid must be >= starting bid (starting_bid = 500.00)
        # Attempt bid below starting bid
        response = self.client.post(reverse("place_bid", args=[self.listing1.id]), {"amount": "450.00"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.listing1.bids.count(), 0)
        self.assertContains(response, "must be at least as large as the starting bid")

        # Valid first bid equal to starting bid
        response = self.client.post(reverse("place_bid", args=[self.listing1.id]), {"amount": "500.00"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.listing1.bids.count(), 1)
        self.assertEqual(self.listing1.current_price, Decimal("500.00"))

        # Subsequent bid must be GREATER than current highest bid
        self.client.login(username="charlie", password="password123")
        # Equal bid rejected
        response = self.client.post(reverse("place_bid", args=[self.listing1.id]), {"amount": "500.00"}, follow=True)
        self.assertEqual(self.listing1.bids.count(), 1)
        self.assertContains(response, "must be greater than the current highest bid")

        # Lower bid rejected
        response = self.client.post(reverse("place_bid", args=[self.listing1.id]), {"amount": "499.00"}, follow=True)
        self.assertEqual(self.listing1.bids.count(), 1)

        # Higher bid accepted
        response = self.client.post(reverse("place_bid", args=[self.listing1.id]), {"amount": "520.00"}, follow=True)
        self.assertEqual(self.listing1.bids.count(), 2)
        self.assertEqual(self.listing1.current_price, Decimal("520.00"))

    def test_closing_auction_and_winner(self):
        """Test creator closing auction and winner declaration."""
        # Charlie places winning bid
        Bid.objects.create(listing=self.listing1, bidder=self.user3, amount=Decimal("600.00"))

        # Non-creator (bob) cannot close auction
        self.client.login(username="bob", password="password123")
        response = self.client.post(reverse("close_auction", args=[self.listing1.id]), follow=True)
        self.listing1.refresh_from_db()
        self.assertTrue(self.listing1.is_active)
        self.assertContains(response, "not authorized")

        # Creator (alice) closes auction
        self.client.login(username="alice", password="password123")
        response = self.client.post(reverse("close_auction", args=[self.listing1.id]), follow=True)
        self.listing1.refresh_from_db()
        self.assertFalse(self.listing1.is_active)
        self.assertEqual(self.listing1.winner, self.user3)

        # Winner visits page and sees congratulations
        self.client.login(username="charlie", password="password123")
        response = self.client.get(reverse("listing", args=[self.listing1.id]))
        self.assertContains(response, "Congratulations, charlie!")

        # Another user visits and sees winner notice
        self.client.login(username="bob", password="password123")
        response = self.client.get(reverse("listing", args=[self.listing1.id]))
        self.assertContains(response, "Winner: <strong>charlie</strong>")

    def test_comments(self):
        """Test adding comments to listing."""
        self.client.login(username="bob", password="password123")
        response = self.client.post(reverse("add_comment", args=[self.listing1.id]), {
            "content": "Does this have a charger included?"
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Does this have a charger included?")
        self.assertEqual(self.listing1.comments.count(), 1)

    def test_categories_pages(self):
        """Test categories listing and category detail filtering."""
        response = self.client.get(reverse("categories"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Electronics")
        self.assertContains(response, "Books")

        # Electronics has 1 active listing
        response = self.client.get(reverse("category_listings", args=[self.category_electronics.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop Pro")

        # Books has only 1 inactive listing, so none active
        response = self.client.get(reverse("category_listings", args=[self.category_books.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Vintage Book")
        self.assertContains(response, "No active listings in Books")

    def test_admin_registration(self):
        """Check all required models are registered in Django admin."""
        self.assertIn(User, site._registry)
        self.assertIn(Category, site._registry)
        self.assertIn(Listing, site._registry)
        self.assertIn(Bid, site._registry)
        self.assertIn(Comment, site._registry)
