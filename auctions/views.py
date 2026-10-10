from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .forms import BidForm, CommentForm, ListingForm
from .models import Bid, Category, Comment, Listing, User


def index(request):
    active_listings = Listing.objects.filter(is_active=True).select_related("creator", "category")
    return render(request, "auctions/index.html", {
        "listings": active_listings
    })


@login_required
def create_listing(request):
    if request.method == "POST":
        form = ListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.creator = request.user
            listing.save()
            messages.success(request, f'Listing "{listing.title}" created successfully!')
            return HttpResponseRedirect(reverse("listing", args=[listing.id]))
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = ListingForm()

    return render(request, "auctions/create.html", {
        "form": form
    })


def listing_view(request, listing_id):
    listing = get_object_or_404(Listing.objects.select_related("creator", "category", "winner"), pk=listing_id)
    is_watchlist = False
    if request.user.is_authenticated:
        is_watchlist = listing.watchers.filter(pk=request.user.pk).exists()

    highest_bid = listing.highest_bid
    is_creator = request.user.is_authenticated and (listing.creator == request.user)
    is_winner = request.user.is_authenticated and (listing.winner == request.user)
    is_leading_bidder = request.user.is_authenticated and (highest_bid is not None) and (highest_bid.bidder == request.user)

    bid_form = BidForm()
    comment_form = CommentForm()
    comments = listing.comments.select_related("author").all()

    return render(request, "auctions/listing.html", {
        "listing": listing,
        "is_watchlist": is_watchlist,
        "is_creator": is_creator,
        "is_winner": is_winner,
        "is_leading_bidder": is_leading_bidder,
        "highest_bid": highest_bid,
        "bid_form": bid_form,
        "comment_form": comment_form,
        "comments": comments
    })


@login_required
def place_bid(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method != "POST":
        return HttpResponseRedirect(reverse("listing", args=[listing_id]))

    if not listing.is_active:
        messages.error(request, "This auction is closed and no longer accepting bids.")
        return HttpResponseRedirect(reverse("listing", args=[listing_id]))

    form = BidForm(request.POST)
    if form.is_valid():
        bid_amount = form.cleaned_data["amount"]
        highest_bid = listing.highest_bid

        if highest_bid is None:
            if bid_amount < listing.starting_bid:
                messages.error(
                    request,
                    f"Your bid (${bid_amount:.2f}) must be at least as large as the starting bid (${listing.starting_bid:.2f})."
                )
                return HttpResponseRedirect(reverse("listing", args=[listing_id]))
        else:
            if bid_amount <= highest_bid.amount:
                messages.error(
                    request,
                    f"Your bid (${bid_amount:.2f}) must be greater than the current highest bid (${highest_bid.amount:.2f})."
                )
                return HttpResponseRedirect(reverse("listing", args=[listing_id]))

        Bid.objects.create(
            listing=listing,
            bidder=request.user,
            amount=bid_amount
        )
        messages.success(request, f"Your bid of ${bid_amount:.2f} was placed successfully!")
    else:
        messages.error(request, "Please enter a valid bid amount.")

    return HttpResponseRedirect(reverse("listing", args=[listing_id]))


@login_required
def close_auction(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method != "POST":
        return HttpResponseRedirect(reverse("listing", args=[listing_id]))

    if listing.creator != request.user:
        messages.error(request, "You are not authorized to close this auction.")
        return HttpResponseRedirect(reverse("listing", args=[listing_id]))

    if not listing.is_active:
        messages.info(request, "This auction is already closed.")
        return HttpResponseRedirect(reverse("listing", args=[listing_id]))

    highest_bid = listing.highest_bid
    if highest_bid:
        listing.winner = highest_bid.bidder
        messages.success(
            request,
            f"Auction closed successfully! The winner is {highest_bid.bidder.username} with a bid of ${highest_bid.amount:.2f}."
        )
    else:
        messages.info(request, "Auction closed with no bids placed.")

    listing.is_active = False
    listing.save()
    return HttpResponseRedirect(reverse("listing", args=[listing_id]))


@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method == "POST":
        if listing.watchers.filter(pk=request.user.pk).exists():
            listing.watchers.remove(request.user)
            messages.success(request, f'Removed "{listing.title}" from your Watchlist.')
        else:
            listing.watchers.add(request.user)
            messages.success(request, f'Added "{listing.title}" to your Watchlist.')

    next_url = request.POST.get("next") or reverse("listing", args=[listing_id])
    return HttpResponseRedirect(next_url)


@login_required
def add_comment(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data["content"].strip()
            if content:
                Comment.objects.create(
                    listing=listing,
                    author=request.user,
                    content=content
                )
                messages.success(request, "Comment added successfully.")
            else:
                messages.error(request, "Comment cannot be empty.")
        else:
            messages.error(request, "Failed to submit comment.")

    return HttpResponseRedirect(reverse("listing", args=[listing_id]))


@login_required
def watchlist_view(request):
    watchlist_items = request.user.watchlist.select_related("creator", "category").all()
    return render(request, "auctions/watchlist.html", {
        "listings": watchlist_items
    })


def categories_view(request):
    categories = Category.objects.annotate(
        active_count=Count("listings", filter=Q(listings__is_active=True))
    ).order_by("name")
    return render(request, "auctions/categories.html", {
        "categories": categories
    })


def category_listings(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    listings = category.listings.filter(is_active=True).select_related("creator", "category")
    return render(request, "auctions/category_listings.html", {
        "category": category,
        "listings": listings
    })


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url:
                return HttpResponseRedirect(next_url)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")
