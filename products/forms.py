from django import forms
from django.core.exceptions import ValidationError
from .models import Product, Config
import os

class ProductForm(forms.ModelForm):
    """
    Formulario para crear y editar productos con validación de imágenes
    """
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del producto'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del producto'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
        labels = {
            'name': 'Nombre',
            'description': 'Descripción',
            'price': 'Precio',
            'image': 'Imagen'
        }
    
    def clean_image(self):
        """
        Validación personalizada para archivos de imagen
        """
        image = self.cleaned_data.get('image')
        
        if image:
            # Validar tipo de archivo por extensión
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            ext = os.path.splitext(image.name)[1].lower()
            
            if ext not in valid_extensions:
                raise ValidationError(
                    f'Tipo de archivo no válido. Solo se permiten: {", ".join(valid_extensions)}'
                )
            
            # Validar tipo MIME
            valid_mime_types = [
                'image/jpeg', 'image/jpg', 'image/png', 
                'image/gif', 'image/webp'
            ]
            
            if hasattr(image, 'content_type') and image.content_type not in valid_mime_types:
                raise ValidationError(
                    'El archivo no es una imagen válida.'
                )
            
            # Validar tamaño del archivo (máximo 5MB)
            max_size = 5 * 1024 * 1024  # 5MB en bytes
            if image.size > max_size:
                raise ValidationError(
                    'El archivo es demasiado grande. Tamaño máximo: 5MB'
                )
        
        return image
    
    def clean_price(self):
        """
        Validación para el precio
        """
        price = self.cleaned_data.get('price')
        
        if price is not None and price < 0:
            raise ValidationError('El precio no puede ser negativo.')
        
        return price


class ConfigForm(forms.ModelForm):
    """
    Formulario para configuración de buckets S3
    """
    
    class Meta:
        model = Config
        fields = ['bucket_name', 'backup_bucket']
        widgets = {
            'bucket_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del bucket principal'
            }),
            'backup_bucket': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del bucket de backup (opcional)'
            })
        }
        labels = {
            'bucket_name': 'Bucket Principal',
            'backup_bucket': 'Bucket de Backup'
        }
        help_texts = {
            'bucket_name': 'Nombre del bucket S3 donde se almacenarán las imágenes',
            'backup_bucket': 'Bucket S3 para respaldos (opcional)'
        }
    
    def clean_bucket_name(self):
        """
        Validación para el nombre del bucket principal
        """
        bucket_name = self.cleaned_data.get('bucket_name')
        
        if not bucket_name:
            raise ValidationError('El nombre del bucket principal es obligatorio.')
        
        # Validar formato básico del nombre del bucket S3
        if not bucket_name.replace('-', '').replace('.', '').isalnum():
            raise ValidationError(
                'El nombre del bucket solo puede contener letras, números, guiones y puntos.'
            )
        
        if len(bucket_name) < 3 or len(bucket_name) > 63:
            raise ValidationError(
                'El nombre del bucket debe tener entre 3 y 63 caracteres.'
            )
        
        return bucket_name.lower()
    
    def clean_backup_bucket(self):
        """
        Validación para el nombre del bucket de backup
        """
        backup_bucket = self.cleaned_data.get('backup_bucket')
        
        if backup_bucket:
            # Aplicar las mismas validaciones que al bucket principal
            if not backup_bucket.replace('-', '').replace('.', '').isalnum():
                raise ValidationError(
                    'El nombre del bucket de backup solo puede contener letras, números, guiones y puntos.'
                )
            
            if len(backup_bucket) < 3 or len(backup_bucket) > 63:
                raise ValidationError(
                    'El nombre del bucket de backup debe tener entre 3 y 63 caracteres.'
                )
            
            return backup_bucket.lower()
        
        return backup_bucket
    
    def clean(self):
        """
        Validación a nivel de formulario
        """
        cleaned_data = super().clean()
        bucket_name = cleaned_data.get('bucket_name')
        backup_bucket = cleaned_data.get('backup_bucket')
        
        # Verificar que los buckets no sean iguales
        if bucket_name and backup_bucket and bucket_name == backup_bucket:
            raise ValidationError(
                'El bucket principal y el bucket de backup no pueden ser el mismo.'
            )
        
        return cleaned_data