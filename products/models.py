from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']

class Config(models.Model):
    bucket_name = models.CharField(max_length=100, default='jfm02')
    backup_bucket = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Config - Bucket: {self.bucket_name}"
    
    class Meta:
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"
