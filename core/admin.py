from django.contrib import admin
from .models import User, Product, Cart, FullChat

admin.site.register(User)
admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(FullChat)
