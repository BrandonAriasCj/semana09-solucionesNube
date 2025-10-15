from django.contrib import admin
from .models import Product, Config

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']

@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ['bucket_name', 'backup_bucket']
