from django.contrib import admin
from .models import User, Category, Listing, Bid, Comment


class ListingAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "creator", "starting_bid", "is_active", "category", "created_at")
    list_filter = ("is_active", "category", "created_at")
    search_fields = ("title", "description")


class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "bidder", "amount", "created_at")
    list_filter = ("created_at",)
    search_fields = ("listing__title", "bidder__username")


class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("listing__title", "author__username", "content")


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


admin.site.register(User)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Listing, ListingAdmin)
admin.site.register(Bid, BidAdmin)
admin.site.register(Comment, CommentAdmin)
