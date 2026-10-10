from django import forms
from .models import Listing, Category


class ListingForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ["title", "description", "starting_bid", "image_url", "category"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g., Apple iPhone 15 Pro, Vintage Watch..."
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Detailed description of the item..."
            }),
            "starting_bid": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.01"
            }),
            "image_url": forms.URLInput(attrs={
                "class": "form-control",
                "placeholder": "https://example.com/item.jpg"
            }),
            "category": forms.Select(attrs={
                "class": "form-control"
            }),
        }
        labels = {
            "title": "Title",
            "description": "Description",
            "starting_bid": "Starting Bid ($)",
            "image_url": "Image URL (optional)",
            "category": "Category (optional)",
        }


class BidForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your bid ($)",
            "step": "0.01",
            "min": "0.01"
        }),
        label="Bid Amount"
    )


class CommentForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Leave a comment about this listing..."
        }),
        label="Comment"
    )
