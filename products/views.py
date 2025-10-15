from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from .models import Product, Config
from .forms import ProductForm
from services.s3_service import S3Service
from django.conf import settings
import os
import uuid


def handle_image_upload(image_file, product):
    """
    Handle image upload ONLY to S3 - no local fallback
    """
    try:
        # Generate unique filename for S3
        file_extension = os.path.splitext(image_file.name)[1]
        unique_filename = f"products/{uuid.uuid4()}{file_extension}"
        
        # Read file content into memory to avoid "closed file" issues
        image_file.seek(0)  # Reset to beginning
        file_content = image_file.read()
        
        # Create a new BytesIO object with the content
        import io
        file_buffer = io.BytesIO(file_content)
        file_buffer.name = image_file.name  # Preserve original filename for content type detection
        
        # Initialize S3 service
        s3_service = S3Service()
        
        # Upload to S3 using the buffer
        upload_success = s3_service.upload_file(file_buffer, unique_filename)
        
        if upload_success:
            # Save S3 path to product
            product.image.name = unique_filename
            return True, "S3", None
        else:
            return False, "S3_upload_failed", "No se pudo subir la imagen a S3. Verifica las credenciales y permisos."
            
    except Exception as e:
        return False, "S3_error", f"Error de S3: {str(e)}"


def handle_local_upload(image_file, product):
    """
    Handle local file upload as fallback
    """
    try:
        # Save to local media directory
        product.image = image_file
        return True, "local", None
    except Exception as e:
        return False, "error", str(e)


def get_image_url(product):
    """
    Get image URL from S3 ONLY
    """
    if not product.image:
        return None
        
    try:
        # Always use S3 URLs
        s3_service = S3Service()
        return s3_service.get_file_url(product.image.name)
    except Exception as e:
        return None


def product_list(request):
    """
    Vista para mostrar todos los productos con paginación.
    Requirements: 1.1 - Mostrar lista de todos los productos
    """
    products = Product.objects.all()
    
    # Paginación - 12 productos por página
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Generar URLs para las imágenes (S3 o local)
    for product in page_obj:
        product.image_url = get_image_url(product)
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,
        'total_products': products.count()
    }
    
    return render(request, 'product_list.html', context)


def product_create(request):
    """
    Vista para crear un nuevo producto con imagen.
    Requirements: 1.2 - Permitir crear producto y subir imagen a S3
    """
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Crear el producto sin guardar aún
                    product = form.save(commit=False)
                    
                    # Si hay imagen, subirla
                    if form.cleaned_data.get('image'):
                        image_file = form.cleaned_data['image']
                        
                        success, storage_type, error = handle_image_upload(image_file, product)
                        
                        if success:
                            product.save()
                            storage_msg = "a S3" if storage_type == "S3" else "localmente"
                            messages.success(request, f'Producto "{product.name}" creado exitosamente. Imagen guardada {storage_msg}.')
                            return redirect('product_list')
                        else:
                            messages.error(request, f'Error al subir la imagen: {error}. Intente nuevamente.')
                    else:
                        # Guardar producto sin imagen
                        product.save()
                        messages.success(request, f'Producto "{product.name}" creado exitosamente.')
                        return redirect('product_list')
                        
            except Exception as e:
                messages.error(request, f'Error al crear el producto: {str(e)}')
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Crear Producto',
        'submit_text': 'Crear Producto'
    }
    
    return render(request, 'product_form.html', context)


def product_update(request, pk):
    """
    Vista para editar un producto existente.
    Requirements: 1.3 - Permitir actualizar información y cambiar imagen
    """
    product = get_object_or_404(Product, pk=pk)
    old_image_name = product.image.name if product.image else None
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    s3_service = S3Service()
                    
                    # Si se subió una nueva imagen
                    if form.cleaned_data.get('image') and hasattr(form.cleaned_data['image'], 'read'):
                        image_file = form.cleaned_data['image']
                        
                        # Generar nombre único para el nuevo archivo
                        file_extension = os.path.splitext(image_file.name)[1]
                        unique_filename = f"products/{uuid.uuid4()}{file_extension}"
                        
                        # Subir nueva imagen a S3
                        upload_success = s3_service.upload_file(image_file, unique_filename)
                        
                        if upload_success:
                            # Eliminar imagen anterior si existe
                            if old_image_name:
                                s3_service.delete_file(old_image_name)
                            
                            # Actualizar producto con nueva imagen
                            product = form.save(commit=False)
                            product.image.name = unique_filename
                            product.save()
                            
                            messages.success(request, f'Producto "{product.name}" actualizado exitosamente.')
                            return redirect('product_list')
                        else:
                            messages.error(request, 'Error al subir la nueva imagen a S3. Intente nuevamente.')
                    else:
                        # Solo actualizar datos sin cambiar imagen
                        product = form.save()
                        messages.success(request, f'Producto "{product.name}" actualizado exitosamente.')
                        return redirect('product_list')
                        
            except Exception as e:
                messages.error(request, f'Error al actualizar el producto: {str(e)}')
    else:
        form = ProductForm(instance=product)
    
    # Generar URL de la imagen actual para mostrar en el formulario
    current_image_url = get_image_url(product)
    
    context = {
        'form': form,
        'product': product,
        'current_image_url': current_image_url,
        'title': f'Editar Producto: {product.name}',
        'submit_text': 'Actualizar Producto'
    }
    
    return render(request, 'product_form.html', context)


def product_delete(request, pk):
    """
    Vista para eliminar un producto y su imagen de S3.
    Requirements: 1.4 - Remover producto y su imagen asociada de S3
    """
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Eliminar imagen de S3 si existe
                if product.image:
                    s3_service = S3Service()
                    delete_success = s3_service.delete_file(product.image.name)
                    
                    if not delete_success:
                        messages.warning(request, 
                            f'Producto "{product.name}" eliminado, pero hubo un problema al eliminar la imagen de S3.')
                
                product_name = product.name
                product.delete()
                
                messages.success(request, f'Producto "{product_name}" eliminado exitosamente.')
                return redirect('product_list')
                
        except Exception as e:
            messages.error(request, f'Error al eliminar el producto: {str(e)}')
            return redirect('product_list')
    
    # Generar URL de la imagen para mostrar en la confirmación
    image_url = get_image_url(product)
    
    context = {
        'product': product,
        'image_url': image_url
    }
    
    return render(request, 'product_confirm_delete.html', context)


def admin_panel(request):
    """
    Vista para mostrar el panel de administración con opciones de backup.
    Requirements: 3.1 - Panel de administración para backup
    """
    try:
        config = Config.objects.first()
        if not config:
            # Crear configuración por defecto si no existe
            config = Config.objects.create()
    except Exception as e:
        messages.error(request, f'Error al cargar configuración: {str(e)}')
        config = None
    
    context = {
        'config': config
    }
    
    return render(request, 'admin/admin_panel.html', context)


def admin_backup(request):
    """
    Vista para iniciar el proceso de backup de imágenes.
    Requirements: 3.1, 3.2, 3.3 - Copiar todas las imágenes del bucket principal a backup
    """
    if request.method == 'POST':
        try:
            # Obtener configuración
            config = Config.objects.first()
            if not config:
                return JsonResponse({
                    'success': False,
                    'error': 'No se encontró configuración del sistema'
                })
            
            if not config.backup_bucket:
                return JsonResponse({
                    'success': False,
                    'error': 'No se ha configurado un bucket de backup'
                })
            
            # Inicializar servicio S3
            s3_service = S3Service()
            
            # Ejecutar backup
            results = s3_service.copy_all_files(
                source_bucket=config.bucket_name,
                target_bucket=config.backup_bucket
            )
            
            # Preparar respuesta
            if results['failed_files']:
                return JsonResponse({
                    'success': True,
                    'warning': True,
                    'message': f'Backup completado con advertencias: {results["success_count"]}/{results["total_processed"]} archivos copiados',
                    'results': results
                })
            else:
                return JsonResponse({
                    'success': True,
                    'message': f'Backup completado exitosamente: {results["success_count"]} archivos copiados',
                    'results': results
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error durante el backup: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido'
    })
